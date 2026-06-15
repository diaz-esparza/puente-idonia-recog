"""End-to-end tests covering error management for the full
Idonia-Recog bridge."""

import inspect
import re
from collections.abc import Callable

import httpx
import pytest

from puente.domain.models import MedicalRecordUpload
from tests.e2e.common import post_pipeline
from tests.support.mocks import IdoniaMock, RecogMock


async def _pipeline_returns_error(
    endpoint: str,
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
) -> None:
    with pytest.raises(httpx.HTTPStatusError):
        _ = (
            await post_pipeline(api_client, endpoint, medical_record)
        ).raise_for_status()


@pytest.mark.parametrize(
    "endpoint", ["/pipeline/run/form", "/pipeline/run/json"]
)
@pytest.mark.parametrize(
    ("method_failure"),
    [
        method
        for (name, method) in inspect.getmembers(
            IdoniaMock, predicate=inspect.isfunction
        )
        if re.match("^respond_.+_error$", name)
    ],
)
async def test_pipeline_returns_error_on_idonia_failure(
    endpoint: str,
    method_failure: Callable[[IdoniaMock], None],
    idonia_mock: IdoniaMock,
    recog_mock: RecogMock,
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
) -> None:
    """Idonia service failures propagate through the pipeline to the API."""
    method_failure(idonia_mock)
    await _pipeline_returns_error(endpoint, api_client, medical_record)


@pytest.mark.parametrize(
    "endpoint", ["/pipeline/run/form", "/pipeline/run/json"]
)
@pytest.mark.parametrize(
    ("method_failure"),
    [
        method
        for (name, method) in inspect.getmembers(
            RecogMock, predicate=inspect.isfunction
        )
        if re.match("^respond_.+_error$", name)
    ],
)
async def test_pipeline_returns_error_on_recog_failure(
    endpoint: str,
    method_failure: Callable[[RecogMock], None],
    idonia_mock: IdoniaMock,
    recog_mock: RecogMock,
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
) -> None:
    """Recog service failures propagate through the pipeline to the API."""
    method_failure(recog_mock)
    await _pipeline_returns_error(endpoint, api_client, medical_record)


@pytest.mark.parametrize(
    "endpoint", ["/pipeline/run/form", "/pipeline/run/json"]
)
async def test_pipeline_run_rejects_invalid_body(
    endpoint: str,
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        endpoint,
        content=b"not valid json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
