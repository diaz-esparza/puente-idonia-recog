"""End-to-end tests covering the full Idonia-Recog bridge."""

import httpx
import pytest

from puente.domain.models import MagicLink, MedicalRecordUpload
from tests.support.mocks import IdoniaMock, RecogMock


async def test_pipeline_run_completes_and_returns_magic_link(
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
    idonia_mock: IdoniaMock,
    recog_mock: RecogMock,
    humanized_pdf: bytes,
) -> None:
    recog_mock.respond_with_pdf(humanized_pdf)

    response = await api_client.post(
        "/pipeline/run",
        content=medical_record.model_dump_json(by_alias=False),
        headers={"Content-Type": "application/json"},
    )

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


async def test_health_endpoint_reports_service_status(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.parametrize("failing_service", ["recog", "idonia"])
async def test_pipeline_returns_error_on_external_failure(
    failing_service: str,
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
    idonia_mock: IdoniaMock,
    recog_mock: RecogMock,
) -> None:
    """External service failures propagate through the pipeline to the API.

    The mock returns errors synchronously, so the failing task completes first
    and ``FIRST_COMPLETED`` catches it before the magic
    link is created.  See the integration suite for the delayed-failure
    path where sibling uploads finish first.
    """
    if failing_service == "recog":
        recog_mock.respond_with_error(500)
    else:
        idonia_mock.respond_dicom_error(500)

    with pytest.raises(httpx.HTTPStatusError):
        _ = await api_client.post(
            "/pipeline/run",
            content=medical_record.model_dump_json(by_alias=False),
            headers={"Content-Type": "application/json"},
        )

    recog_mock.assert_humanization_requested()


async def test_pipeline_run_rejects_invalid_body(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/pipeline/run",
        content=b"not valid json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
