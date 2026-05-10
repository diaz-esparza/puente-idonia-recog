import asyncio
from typing import override

from puente.config import get_settings
from puente.domain.models import DicomStudy, MagicLink, MedicalRecordUpload
from puente.domain.ports import (
    MedicalStoragePort,
    PdfToTextPort,
    PipelinePort,
    ReportHumanizationPort,
)


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

    async def manage_humanized_report(
        self,
        study: DicomStudy,
        report: bytes,
    ) -> str:
        """Humanize and upload the report under a derivative description."""
        decoded_report = self.__pdf_to_text.convert(report)
        humanized_report = await self.__humanization.humanize(decoded_report)
        humanized_study = DicomStudy(
            patient_id=study.patient_id,
            accession_number=study.accession_number,
            study_description=study.study_description
            + self.__humanized_suffix,
        )
        return await self.__storage.upload_report(
            humanized_study,
            humanized_report,
        )

    @override
    async def run(self, record: MedicalRecordUpload) -> MagicLink:
        # Do all the uploads in parallel.
        tasks = [
            self.__storage.upload_dicom(record.study, record.dicom_file),
            self.__storage.upload_report(record.study, record.report_file),
            self.manage_humanized_report(record.study, record.report_file),
        ]
        # Wait for at least one run to be completed before generating the magic
        # link. This ensures that the location actually exists.
        done, pending = await asyncio.wait(
            (asyncio.create_task(i) for i in tasks),
            return_when=asyncio.FIRST_COMPLETED,
        )
        try:
            _ = await asyncio.gather(*done)
            magic_link = await self.__storage.create_magic_link(record.study)
            # Wait for everything to finish before returning for future
            # traceability. This _could_ possibly be optimized out
            _ = await asyncio.gather(*pending)
            return magic_link
        finally:
            # Avoids dangling background tasks
            for task in pending:
                _ = task.cancel()
