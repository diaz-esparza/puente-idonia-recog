import asyncio
from hashlib import sha256
from typing import override

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from puente.config import get_settings
from puente.domain.models import DicomStudy, MagicLink, MedicalRecordUpload
from puente.domain.ports import (
    MedicalStoragePort,
    PdfToTextPort,
    PipelinePort,
    ReportHumanizationPort,
)
from puente.telemetry.getters import get_logger

_logger = get_logger(__name__)
_tracer = trace.get_tracer(__name__)


class BridgePipeline(PipelinePort):
    """Orchestrates the three-phase Idonia-Recog bridge workflow."""

    def __init__(
        self,
        storage: MedicalStoragePort,
        pdf_to_text: PdfToTextPort,
        humanization: ReportHumanizationPort,
    ) -> None:
        settings = get_settings()
        self.__storage = storage
        self.__pdf_to_text = pdf_to_text
        self.__humanization = humanization
        self.__humanized_suffix = settings.humanized_suffix

    @staticmethod
    def _privacy_hash(attribute: str) -> str:
        return sha256(attribute.encode()).hexdigest()

    @classmethod
    def _trace_study(cls, span: trace.Span, study: DicomStudy) -> None:
        span.set_attributes(
            {
                "study.sha256.patient_id": cls._privacy_hash(study.patient_id),
                "study.sha256.accession_number": cls._privacy_hash(
                    study.accession_number
                ),
                "study.sha256.description": cls._privacy_hash(
                    study.study_description
                ),
            }
        )

    async def _humanize_and_upload(
        self,
        study: DicomStudy,
        report: bytes,
    ) -> str:
        root_span = trace.get_current_span()
        with _tracer.start_as_current_span("phase_humanize"):
            decoded_report = self.__pdf_to_text.convert(report)
            humanized_report = await self.__humanization.humanize(
                decoded_report
            )
            root_span.set_attribute("tasks.humanize.generated", True)

            humanized_study = DicomStudy(
                patient_id=study.patient_id,
                accession_number=study.accession_number,
                study_description=study.study_description
                + self.__humanized_suffix,
            )
            result = await self.__storage.upload_report(
                humanized_study,
                humanized_report,
            )
            root_span.set_attribute("tasks.humanize.uploaded", True)
            return result

    @override
    async def run(self, record: MedicalRecordUpload) -> MagicLink:
        study = record.study

        with _tracer.start_as_current_span("pipeline_run") as span:
            self._trace_study(span, study)

            tasks = [
                self.__storage.upload_dicom(study, record.dicom_file),
                self.__storage.upload_report(study, record.report_file),
                self._humanize_and_upload(study, record.report_file),
            ]
            done, pending = await asyncio.wait(
                (asyncio.create_task(t) for t in tasks),
                return_when=asyncio.FIRST_COMPLETED,
            )

            try:
                _ = await asyncio.gather(*done)
                span.set_attribute("tasks.patient_folder_created", True)

                with _tracer.start_as_current_span("phase_deliver"):
                    magic_link = await self.__storage.create_magic_link(study)
                span.set_attribute("tasks.magic_link_created", True)

                _ = await asyncio.gather(*pending)
                span.set_attribute("tasks.uploaded_all_files", True)

                _logger.info(
                    "pipeline_complete",
                    magic_url=magic_link.url,
                )
                return magic_link

            except Exception as e:
                _logger.exception("pipeline_failed")
                span.record_exception(e)
                span.set_status(StatusCode.ERROR)
                raise

            finally:
                for task in pending:
                    _ = task.cancel()
                # Avoids "Task exception was never retrieved" issues
                if pending:
                    _ = await asyncio.gather(
                        *pending,
                        return_exceptions=True,
                    )
