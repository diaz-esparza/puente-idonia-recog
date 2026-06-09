"""Integration tests for the ``BridgePipeline`` orchestrator."""

import pytest

from puente.service.pipeline import BridgePipeline
from tests.support.data import build_simple_record
from tests.support.fakes import (
    DelayedFailingDicomStorage,
    FailingDicomStorage,
    FailingHumanization,
    FailingMagicLinkStorage,
    FakeHumanization,
    FakePdfToText,
    FakeStorage,
)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def pdf_to_text() -> FakePdfToText:
    return FakePdfToText()


@pytest.fixture
def humanization() -> FakeHumanization:
    return FakeHumanization()


@pytest.fixture
def pipeline(
    storage: FakeStorage,
    pdf_to_text: FakePdfToText,
    humanization: FakeHumanization,
) -> BridgePipeline:
    return BridgePipeline(
        storage=storage,
        pdf_to_text=pdf_to_text,
        humanization=humanization,
    )


class TestBridgePipeline:
    async def test_run_uploads_dicom_and_report(
        self,
        pipeline: BridgePipeline,
        storage: FakeStorage,
    ) -> None:
        record = build_simple_record()
        _ = await pipeline.run(record)

        types = {u[0] for u in storage.uploads}
        assert "dicom" in types
        assert "report" in types

    async def test_run_humanizes_report_and_uploads_humanized_version(
        self,
        pipeline: BridgePipeline,
        storage: FakeStorage,
        humanization: FakeHumanization,
    ) -> None:
        record = build_simple_record(study_description="Original Study")
        _ = await pipeline.run(record)

        humanized_uploads = [
            u
            for u in storage.uploads
            if "_HUMANIZADO" in u[1].study_description
        ]
        assert len(humanized_uploads) == 1
        _, study, content = humanized_uploads[0]
        assert content == humanization.pdf
        assert study.study_description == "Original Study_HUMANIZADO"

    async def test_run_creates_magic_link(
        self, pipeline: BridgePipeline, storage: FakeStorage
    ) -> None:
        record = build_simple_record()
        result = await pipeline.run(record)

        assert result == storage.magic_link
        assert result.url == "https://fake.test/123"
        assert result.pin == "9999"

    @pytest.mark.parametrize(
        ("patient_id", "accession_number"),
        [
            ("PT-42", "ACC-99"),
            ("12345678A", "MRI-2024-009"),
            ("Z-001", "X-2024-001"),
        ],
    )
    async def test_run_preserves_study_metadata(
        self,
        pipeline: BridgePipeline,
        storage: FakeStorage,
        patient_id: str,
        accession_number: str,
    ) -> None:
        record = build_simple_record(
            patient_id=patient_id,
            accession_number=accession_number,
        )
        _ = await pipeline.run(record)

        for _, study, _ in storage.uploads:
            assert study.patient_id == patient_id
            assert study.accession_number == accession_number

    async def test_run_raises_when_dicom_upload_fails(self) -> None:
        pipeline = BridgePipeline(
            storage=FailingDicomStorage(),
            pdf_to_text=FakePdfToText(),
            humanization=FakeHumanization(),
        )
        record = build_simple_record()
        with pytest.raises(RuntimeError, match="DICOM upload failed"):
            _ = await pipeline.run(record)

    async def test_run_magic_link_created_before_slow_upload_fails(
        self,
    ) -> None:
        """A slow-failing upload doesn't block the magic link.

        The pipeline uses ``FIRST_COMPLETED`` to optimize latency: sibling
        uploads that finish quickly allow the magic link to be created even
        while a lagging upload (e.g. Recog) is still in-flight.  The error
        still propagates to the caller.
        """
        storage = DelayedFailingDicomStorage()
        pipeline = BridgePipeline(
            storage=storage,
            pdf_to_text=FakePdfToText(),
            humanization=FakeHumanization(),
        )
        record = build_simple_record()
        with pytest.raises(RuntimeError, match="DICOM upload failed"):
            _ = await pipeline.run(record)
        assert storage.magic_requested

    async def test_run_raises_when_humanization_fails(self) -> None:
        pipeline = BridgePipeline(
            storage=FakeStorage(),
            pdf_to_text=FakePdfToText(),
            humanization=FailingHumanization(),
        )
        record = build_simple_record()
        with pytest.raises(RuntimeError, match="Humanization failed"):
            _ = await pipeline.run(record)

    async def test_run_raises_when_magic_link_fails(self) -> None:
        pipeline = BridgePipeline(
            storage=FailingMagicLinkStorage(),
            pdf_to_text=FakePdfToText(),
            humanization=FakeHumanization(),
        )
        record = build_simple_record()
        with pytest.raises(RuntimeError, match="Magic link creation failed"):
            _ = await pipeline.run(record)
