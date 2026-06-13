from typing import Annotated

from fastapi import APIRouter, Depends, Request
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from puente.config import Settings, get_settings
from puente.telemetry.getters import get_logger

from ..worker import AuditDataTypes
from .lifespan import DepWorker

_logger = get_logger(__name__)
router = APIRouter(prefix="/v1")


@router.post("/traces")
async def ingest_traces(request: Request, worker: DepWorker) -> dict[str, str]:
    body = await request.body()
    worker.put(body, AuditDataTypes.TRACES)
    try:
        export_request = ExportTraceServiceRequest.FromString(body)
        trace_count = sum(
            len(scope.spans)
            for resource in export_request.resource_spans
            for scope in resource.scope_spans
        )
        _logger.debug("traces_ingested", trace_count=trace_count)
    except Exception:
        _logger.debug(
            "traces_ingested_raw",
            content_type=request.headers.get("content-type"),
            content_encoding=request.headers.get("content-encoding"),
            body_len=len(body),
        )
    return {}


@router.post("/logs")
async def ingest_logs(request: Request, worker: DepWorker) -> dict[str, str]:
    body = await request.body()
    worker.put(body, AuditDataTypes.LOGS)
    try:
        export_request = ExportLogsServiceRequest.FromString(body)
        log_count = sum(
            len(scope.log_records)
            for resource in export_request.resource_logs
            for scope in resource.scope_logs
        )
        _logger.debug("logs_ingested", log_count=log_count)
    except Exception:
        _logger.debug(
            "logs_ingested_raw",
            content_type=request.headers.get("content-type"),
            content_encoding=request.headers.get("content-encoding"),
            body_len=len(body),
        )
    return {}


@router.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    _logger.debug("health_check")
    return {"status": "ok", "version": settings.version}
