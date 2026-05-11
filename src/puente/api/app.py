from typing import Annotated

from fastapi import Depends, FastAPI

from puente.bootstrap import get_pipeline
from puente.config import Settings, get_settings
from puente.domain.models import MagicLink, MedicalRecordUpload
from puente.service.pipeline import BridgePipeline

app = FastAPI(title="Puente Idonia-Recog", version=get_settings().version)


@app.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    return {"status": "ok", "version": settings.version}


@app.post("/pipeline/run")
async def pipeline_run(
    record: MedicalRecordUpload,
    pipeline: Annotated[BridgePipeline, Depends(get_pipeline)],
) -> MagicLink:
    """Run the full bridge pipeline for a medical record."""
    return await pipeline.run(record)
