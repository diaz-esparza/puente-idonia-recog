"""In-memory fake port implementations for integration tests.

Exceptions raise self.__class__.__name__ to identify its source class.
"""

import asyncio
from typing import override

from pydantic import SecretStr

from puente.domain.models import DicomStudy, MagicLink
from puente.domain.ports import (
    MedicalStoragePort,
    PdfToTextPort,
    PiiRedactionPort,
    ReportHumanizationPort,
)


class FakeStorage(MedicalStoragePort):
    """In-memory storage that records every upload and returns stable IDs."""

    def __init__(self) -> None:
        self.uploads: list[tuple[str, DicomStudy, bytes]] = []
        self.magic_link = MagicLink(URL="https://fake.test/123", PIN="9999")
        self.magic_requested = False
        self.last_password: SecretStr | None = None

    @override
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        self.uploads.append(("dicom", study, content))
        return "fake-dicom-id"

    @override
    async def upload_report(self, study: DicomStudy, content: bytes) -> str:
        self.uploads.append(("report", study, content))
        return "fake-report-id"

    @override
    async def create_magic_link(
        self,
        study: DicomStudy,
        password: SecretStr | None,
    ) -> MagicLink:
        self.magic_requested = True
        self.last_password = password
        return self.magic_link


class FailingDicomStorage(FakeStorage):
    """Storage whose ``upload_dicom`` always raises synchronously."""

    @override
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        raise RuntimeError(self.__class__.__name__)


class FailingReportStorage(FakeStorage):
    """Storage whose ``upload_dicom`` always raises synchronously."""

    @override
    async def upload_report(self, study: DicomStudy, content: bytes) -> str:
        raise RuntimeError(self.__class__.__name__)


class DelayedFailingDicomStorage(FakeStorage):
    """Storage whose ``upload_dicom`` raises after a simulated network delay.

    The delay lets sibling upload tasks finish first, which tests the
    ``FIRST_COMPLETED`` path: the pipeline creates the magic link before
    the slow upload's failure is observed.
    """

    @override
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        await asyncio.sleep(0.01)
        raise RuntimeError(self.__class__.__name__)


class FailingMagicLinkStorage(FakeStorage):
    """Storage whose ``create_magic_link`` always raises."""

    @override
    async def create_magic_link(
        self,
        study: DicomStudy,
        password: SecretStr | None,
    ) -> MagicLink:
        raise RuntimeError(self.__class__.__name__)


class FakePdfToText(PdfToTextPort):
    """In-memory PDF extractor that returns a fixed string."""

    def __init__(self, text: str = "extracted text") -> None:
        self.text = text

    @override
    def convert(self, pdf_file: bytes) -> str:
        return self.text


class FakeHumanization(ReportHumanizationPort):
    """In-memory humanizer that returns a fixed PDF."""

    def __init__(self, pdf: bytes = b"humanized-pdf") -> None:
        self.pdf = pdf

    @override
    async def humanize(self, report: str) -> bytes:
        return self.pdf


class FailingHumanization(FakeHumanization):
    """Humanizer that always raises."""

    @override
    async def humanize(self, report: str) -> bytes:
        raise RuntimeError(self.__class__.__name__)


class FakePiiRedaction(PiiRedactionPort):
    """In-memory PII redactor that returns a fixed de-identified string."""

    def __init__(self, redacted: str = "de-identified text") -> None:
        self.redacted = redacted

    @override
    def redact(self, text: str) -> str:
        return self.redacted


class FailingPiiRedaction(FakePiiRedaction):
    """PII redactor that always raises."""

    @override
    def redact(self, text: str) -> str:
        raise RuntimeError(self.__class__.__name__)
