"""Basic integration tests for the `BridgePipeline` orchestrator."""

import pytest
from pydantic import SecretStr

from puente.service.pipeline import BridgePipeline
from tests.support.data import build_simple_record
from tests.support.fakes import (
    FakeHumanization,
    FakePdfToText,
    FakePiiRedaction,
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
def pii_redaction() -> FakePiiRedaction:
    return FakePiiRedaction()


@pytest.fixture
def pipeline(
    storage: FakeStorage,
    pdf_to_text: FakePdfToText,
    humanization: FakeHumanization,
    pii_redaction: FakePiiRedaction,
) -> BridgePipeline:
    return BridgePipeline(
        storage=storage,
        pdf_to_text=pdf_to_text,
        humanization=humanization,
        pii_redaction=pii_redaction,
    )


async def test_run_uploads_dicom_and_report(
    pipeline: BridgePipeline,
    storage: FakeStorage,
) -> None:
    record = build_simple_record()
    _ = await pipeline.run(record)

    types = {u[0] for u in storage.uploads}
    assert "dicom" in types
    assert "report" in types


async def test_run_humanizes_report_and_uploads_humanized_version(
    pipeline: BridgePipeline,
    storage: FakeStorage,
    humanization: FakeHumanization,
) -> None:
    record = build_simple_record(study_description="Original Study")
    _ = await pipeline.run(record)

    humanized_uploads = [
        u for u in storage.uploads if "_HUMANIZADO" in u[1].study_description
    ]
    assert len(humanized_uploads) == 1
    _, study, content = humanized_uploads[0]
    assert content == humanization.pdf
    assert study.study_description == "Original Study_HUMANIZADO"


async def test_run_creates_magic_link(
    pipeline: BridgePipeline,
    storage: FakeStorage,
) -> None:
    record = build_simple_record()
    result = await pipeline.run(record)

    assert result == storage.magic_link
    assert result.url == "https://fake.test/123"
    assert result.pin == "9999"


async def test_run_passes_password_to_magic_link(
    pipeline: BridgePipeline,
    storage: FakeStorage,
) -> None:
    password = SecretStr("super-secret-123")
    record = build_simple_record(password=password)

    _ = await pipeline.run(record)

    assert storage.last_password == password


@pytest.mark.parametrize(
    ("patient_id", "accession_number"),
    [
        ("PT-42", "ACC-99"),
        ("12345678A", "MRI-2024-009"),
        ("Z-001", "X-2024-001"),
    ],
)
async def test_run_preserves_study_metadata(
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
