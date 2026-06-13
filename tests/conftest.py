"""Global test configuration and shared fixtures.

All external HTTP calls are captured by ``respx`` so the suite runs fully
offline. The Idonia and Recog adapters use ``httpx.AsyncClient``, which is
transparently routed by the ``respx_mock`` fixture provided by the ``respx``
pytest plugin.
"""

import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest import mock
from urllib.parse import urljoin

import httpx
import pytest
import respx
from fastapi import FastAPI

# Environment safety: pre-seed before the first get_settings() call.
os.environ["PUENTE_HUMANIZED_MOCK"] = "false"
os.environ["PUENTE_PRESIDIO_MOCK"] = "false"
os.environ["PUENTE_RECOG_API_KEY"] = "test-recog-key"
os.environ["PUENTE_IDONIA_API_KEY"] = "test-idonia-key"
os.environ["PUENTE_IDONIA_API_SECRET"] = (
    "S2dGVzdHNlY3JldC0zMi1ieXRlcy1rZXktMDEyMzQ1Njc="
)
os.environ["PUENTE_IDONIA_BASE_URL"] = "https://idonia.test"
os.environ["PUENTE_RECOG_URL"] = (
    "https://recog.test/relisten/dictation/process/report-results"
)

# Safe to import puente modules now.
from puente.audit.worker import get_worker
from puente.bootstrap import get_pipeline
from puente.config import Settings, get_settings
from puente.domain.models import MedicalRecordUpload
from tests.support.data import build_simple_pdf, build_simple_record
from tests.support.mocks import IdoniaMock, RecogMock

get_settings.cache_clear()
get_worker.cache_clear()


@pytest.fixture(autouse=True)
def _reset_caches() -> Generator[None]:
    """Reset all lru_cached factories between tests for a clean slate."""
    yield
    get_settings.cache_clear()
    get_pipeline.cache_clear()
    get_worker.cache_clear()


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Fresh test settings with safe defaults."""
    return get_settings()


@pytest.fixture
def humanized_pdf() -> bytes:
    """A minimal valid PDF representing the humanized report from Recog."""
    return build_simple_pdf("Humanized patient-friendly report text.")


@pytest.fixture
def medical_record() -> MedicalRecordUpload:
    """A complete medical record with a valid PDF report.

    Re-uses the shared data builder so the same helpers are used by both
    tests and the CLI demo.
    """
    return build_simple_record(
        patient_id="PT-001",
        accession_number="ACC-2024-001",
        study_description="Chest CT",
    )


# API client


@pytest.fixture(scope="module")
async def api_client(settings: Settings) -> AsyncGenerator[httpx.AsyncClient]:
    """Async HTTP client wired to the FastAPI ASGI app.

    The FastAPI app configures logs and traces at module level.
    We patch them so the test suite stays silent.
    """
    with (
        mock.patch("puente.telemetry.setup.configure_logging", lambda: None),
        mock.patch("puente.telemetry.setup.configure_tracing", lambda: None),
    ):
        from puente.api.app import app  # noqa: PLC0415

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=urljoin("http://test/", settings.api_root),
    ) as client:
        yield client


# External API mock helpers


@pytest.fixture
def idonia_mock(
    respx_mock: respx.MockRouter, settings: Settings
) -> IdoniaMock:
    """Pre-configured Idonia mock with default happy-path responses."""
    return IdoniaMock(respx_mock, settings.idonia_base_url)


@pytest.fixture
def recog_mock(respx_mock: respx.MockRouter, settings: Settings) -> RecogMock:
    """Pre-configured Recog mock.

    Call ``respond_with_pdf`` before the request to set the exact response.
    """
    return RecogMock(respx_mock, settings.recog_url)


# Audit fixtures


@pytest.fixture
def audit_worker() -> object:
    """In-memory worker for audit API tests."""

    class _MockWorker:
        def __init__(self) -> None:
            self._bucket: dict = {}

        def put(self, event: bytes, data_type: object) -> None:
            self._bucket.setdefault(data_type, []).append(event)

        async def flush_loop(self) -> None:
            pass

        async def close(self) -> None:
            pass

    return _MockWorker()


@pytest.fixture
async def audit_api_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    audit_worker: object,
) -> AsyncGenerator[httpx.AsyncClient]:
    """Async HTTP client wired to a fresh audit FastAPI app.

    Mounts the v1 router with the real dependency overridden by a mock
    worker so no background flush loop or database I/O runs.
    """
    monkeypatch.setenv(
        "PUENTE_AUDIT_PRIVATE_KEY_FILE",
        str(tmp_path / "signing_key.pem"),
    )
    monkeypatch.setenv(
        "PUENTE_AUDIT_PUBLIC_KEY_FILE",
        str(tmp_path / "signing_key.pub"),
    )
    monkeypatch.setenv(
        "PUENTE_AUDIT_SQLITE_FILE",
        str(tmp_path / "audit.db"),
    )
    get_settings.cache_clear()

    with mock.patch(
        "puente.audit.worker.get_worker",
        return_value=audit_worker,
    ):
        from puente.audit.api.lifespan import get_worker  # noqa: PLC0415
        from puente.audit.api.v1 import router as audit_router  # noqa: PLC0415

        audit_app = FastAPI()
        audit_app.include_router(audit_router)
        audit_app.dependency_overrides[get_worker] = lambda: audit_worker

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=audit_app),
            base_url="http://test/v1",
        ) as client:
            yield client
