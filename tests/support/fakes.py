"""In-memory fake port implementations for integration tests."""

import asyncio
from typing import override

from puente.domain.models import DicomStudy, MagicLink
from puente.domain.ports import (
    MedicalStoragePort,
    PdfToTextPort,
    ReportHumanizationPort,
)


class FakeStorage(MedicalStoragePort):
    """In-memory storage that records every upload and returns stable IDs."""

    def __init__(self) -> None:
        self.uploads: list[tuple[str, DicomStudy, bytes]] = []
        self.magic_link = MagicLink(URL="https://fake.test/123", PIN="9999")
        self.magic_requested = False

    @override
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        self.uploads.append(("dicom", study, content))
        return "fake-dicom-id"

    @override
    async def upload_report(self, study: DicomStudy, content: bytes) -> str:
        self.uploads.append(("report", study, content))
        return "fake-report-id"

    @override
    async def create_magic_link(self, study: DicomStudy) -> MagicLink:
        self.magic_requested = True
        return self.magic_link


class FailingDicomStorage(FakeStorage):
    """Storage whose ``upload_dicom`` always raises synchronously."""

    @override
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        raise RuntimeError("DICOM upload failed")


class DelayedFailingDicomStorage(FailingDicomStorage):
    """Storage whose ``upload_dicom`` raises after a simulated network delay.

    The delay lets sibling upload tasks finish first, which tests the
    ``FIRST_COMPLETED`` path: the pipeline creates the magic link before
    the slow upload's failure is observed.
    """

    @override
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        await asyncio.sleep(0.01)
        return await super().upload_dicom(study, content)


class FailingMagicLinkStorage(FakeStorage):
    """Storage whose ``create_magic_link`` always raises."""

    @override
    async def create_magic_link(self, study: DicomStudy) -> MagicLink:
        raise RuntimeError("Magic link creation failed")


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
        raise RuntimeError("Humanization failed")
