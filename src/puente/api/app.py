# pyright: reportMissingTypeStubs=false

from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, Request, Response
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.middleware.base import RequestResponseEndpoint

from puente.bootstrap import get_pipeline
from puente.config import Settings, get_settings
from puente.domain.models import MagicLink, MedicalRecordUpload
from puente.service.pipeline import BridgePipeline
from puente.telemetry.getters import get_logger
from puente.telemetry.setup import configure_logging, configure_tracing

configure_logging()
configure_tracing()
app = FastAPI(title="Puente Idonia-Recog", version=get_settings().version)

FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def bind_request_context(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    structlog.contextvars.clear_contextvars()
    request_id = request.headers.get("x-request-id")
    _ = structlog.contextvars.bind_contextvars(
        request_id=request_id,
        http_method=request.method,
        http_path=request.url.path,
        client_ip=request.client.host if request.client else None,
    )
    response = await call_next(request)
    _ = structlog.contextvars.bind_contextvars(
        http_status_code=response.status_code,
    )
    return response


_logger = get_logger(__name__)


@app.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    _logger.debug("health_check")
    return {"status": "ok", "version": settings.version}


@app.post("/pipeline/run")
async def pipeline_run(
    record: MedicalRecordUpload,
    pipeline: Annotated[BridgePipeline, Depends(get_pipeline)],
) -> MagicLink:
    """Run the full bridge pipeline for a medical record."""
    return await pipeline.run(record)
