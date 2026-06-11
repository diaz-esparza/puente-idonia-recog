from typing import Annotated

from fastapi import APIRouter, Depends

from puente.bootstrap import get_pipeline
from puente.config import Settings, get_settings
from puente.domain.models import MagicLink, MedicalRecordUpload
from puente.service.pipeline import BridgePipeline
from puente.telemetry.getters import get_logger

_logger = get_logger(__name__)

router = APIRouter(prefix="/v1")


@router.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    _logger.debug("health_check")
    return {"status": "ok", "version": settings.version}


@router.post("/pipeline/run")
async def pipeline_run(
    record: MedicalRecordUpload,
    pipeline: Annotated[BridgePipeline, Depends(get_pipeline)],
) -> MagicLink:
    """Run the full bridge pipeline for a medical record."""
    return await pipeline.run(record)
