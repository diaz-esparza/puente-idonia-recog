"""End-to-end tests covering basic functionality for the full
Idonia-Recog bridge."""

import base64
import hashlib

import httpx
import pytest

from puente.domain.models import MagicLink, MedicalRecordUpload
from tests.e2e.common import post_pipeline
from tests.support.mocks import IdoniaMock, RecogMock


@pytest.mark.parametrize(
    "endpoint", ["/pipeline/run/form", "/pipeline/run/json"]
)
async def test_pipeline_run_completes_and_returns_magic_link(
    endpoint: str,
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
    idonia_mock: IdoniaMock,
    recog_mock: RecogMock,
    humanized_pdf: bytes,
) -> None:
    recog_mock.respond_with_pdf(humanized_pdf)

    response = await post_pipeline(api_client, endpoint, medical_record)

    assert response.status_code == 200
    magic_link = MagicLink.model_validate(response.json())
    assert magic_link.url == "https://magic.test/123"
    assert magic_link.pin == "5678"

    idonia_mock.assert_dicom_uploaded(times=1)
    idonia_mock.assert_report_uploaded(times=2)
    idonia_mock.assert_magic_link_created()
    recog_mock.assert_humanization_requested()

    recog_body = recog_mock.latest_request_body()
    assert recog_body["dictationReport"] == "Original clinical report text.\n"


async def test_pipeline_run_form_with_password_hashes_password_for_magic_link(
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
    idonia_mock: IdoniaMock,
    recog_mock: RecogMock,
    humanized_pdf: bytes,
) -> None:
    recog_mock.respond_with_pdf(humanized_pdf)
    password = "patient-password"

    response = await post_pipeline(
        api_client, "/pipeline/run/form", medical_record, password=password
    )

    assert response.status_code == 200
    idonia_mock.assert_magic_link_created()

    expected_hash = base64.b64encode(
        hashlib.sha256(password.encode()).hexdigest().encode()
    ).decode()
    assert idonia_mock.latest_magic_password() == expected_hash


async def test_health_endpoint_reports_service_status(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
