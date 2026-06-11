from abc import ABC, abstractmethod

from puente.domain.models import DicomStudy, MagicLink, MedicalRecordUpload


class MedicalStoragePort(ABC):
    """Outbound port for external medical information storage service
    (e.g. Idonia middleware).
    """

    @abstractmethod
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        """Upload DICOM file, return file id."""

    @abstractmethod
    async def upload_report(self, study: DicomStudy, content: bytes) -> str:
        """Upload a report file, return file id."""

    @abstractmethod
    async def create_magic_link(self, study: DicomStudy) -> MagicLink:
        """Create magic link to access the study container."""


class PiiRedactionPort(ABC):
    """Outbound port for PII de-identification in clinical text
    (e.g. Microsoft Presidio).

    Runs *before* humanization so the external AI service never sees
    personally identifiable information.
    """

    @abstractmethod
    def redact(self, text: str) -> str:
        """De-identify PII from clinical text. Returns de-identified text."""


class ReportHumanizationPort(ABC):
    """Outbound port for external medical report humanization service
    (e.g. Recog AI).
    """

    @abstractmethod
    async def humanize(self, report: str) -> bytes:
        """Send report to external service as a string, return PDF file with
        humanized report.
        """


class PdfToTextPort(ABC):
    """Outbound port for PDF to plain text conversion service."""

    @abstractmethod
    def convert(self, pdf_file: bytes) -> str:
        """Converts PDF file to plain text. Synchronous as it's expected to not
        be IO bound.
        """


class PipelinePort(ABC):
    """Inbound port for operating the bridge pipeline, via CLI, API or
    otherwise.
    """

    @abstractmethod
    async def run(self, record: MedicalRecordUpload) -> MagicLink:
        """Upload the medical record, create humanized report, and return
        access link.
        """
