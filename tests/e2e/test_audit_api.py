"""End-to-end tests for the audit ingestion API."""

from typing import Any

import httpx

from puente.audit.worker import AuditDataTypes
from puente.config import Settings


async def test_post_traces_returns_empty_json(
    audit_api_client: httpx.AsyncClient,
) -> None:
    response = await audit_api_client.post("/traces", content=b"trace-data")
    assert response.status_code == 200
    assert response.json() == {}


async def test_post_traces_puts_data_into_worker(
    audit_api_client: httpx.AsyncClient,
    audit_worker: Any,
) -> None:
    await audit_api_client.post("/traces", content=b"trace-data")
    assert AuditDataTypes.TRACES in audit_worker._bucket
    assert audit_worker._bucket[AuditDataTypes.TRACES] == [b"trace-data"]


async def test_post_logs_returns_empty_json(
    audit_api_client: httpx.AsyncClient,
) -> None:
    response = await audit_api_client.post("/logs", content=b"log-data")
    assert response.status_code == 200
    assert response.json() == {}


async def test_post_logs_puts_data_into_worker(
    audit_api_client: httpx.AsyncClient,
    audit_worker: Any,
) -> None:
    await audit_api_client.post("/logs", content=b"log-data")
    assert AuditDataTypes.LOGS in audit_worker._bucket
    assert audit_worker._bucket[AuditDataTypes.LOGS] == [b"log-data"]


async def test_get_health_returns_status(
    audit_api_client: httpx.AsyncClient,
    settings: Settings,
) -> None:
    response = await audit_api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == settings.version
