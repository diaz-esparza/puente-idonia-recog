"""End-to-end tests covering basic functionality for the full
Idonia-Recog bridge."""

import inspect
import re
from collections.abc import Callable

import httpx
import pytest

from puente.domain.models import MedicalRecordUpload
from tests.support.mocks import IdoniaMock, RecogMock


async def _pipeline_returns_error(
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
) -> None:
    with pytest.raises(httpx.HTTPStatusError):
        _ = (
            await api_client.post(
                "/pipeline/run",
                content=medical_record.model_dump_json(by_alias=False),
                headers={"Content-Type": "application/json"},
            )
        ).raise_for_status()


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
    method_failure: Callable[[IdoniaMock], None],
    idonia_mock: IdoniaMock,
    recog_mock: RecogMock,
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
) -> None:
    """Idonia service failures propagate through the pipeline to the API."""
    method_failure(idonia_mock)
    await _pipeline_returns_error(api_client, medical_record)


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
    method_failure: Callable[[RecogMock], None],
    idonia_mock: IdoniaMock,
    recog_mock: RecogMock,
    api_client: httpx.AsyncClient,
    medical_record: MedicalRecordUpload,
) -> None:
    """Idonia service failures propagate through the pipeline to the API."""
    method_failure(recog_mock)
    await _pipeline_returns_error(api_client, medical_record)


async def test_pipeline_run_rejects_invalid_body(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/pipeline/run",
        content=b"not valid json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
