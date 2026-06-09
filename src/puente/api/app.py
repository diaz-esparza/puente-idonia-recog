# pyright: reportMissingTypeStubs=false

from typing import Annotated

from fastapi import Depends, FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

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

_logger = get_logger(__name__)
_tracer = trace.get_tracer(__name__)


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
