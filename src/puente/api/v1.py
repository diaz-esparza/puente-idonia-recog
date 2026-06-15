import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import SecretStr

from puente.bootstrap import get_pipeline
from puente.config import Settings, get_settings
from puente.domain.models import DicomStudy, MagicLink, MedicalRecordUpload
from puente.service.pipeline import BridgePipeline
from puente.telemetry.getters import get_logger

_logger = get_logger(__name__)

router = APIRouter(prefix="/v1")


type DepPipeline = Annotated[BridgePipeline, Depends(get_pipeline)]


@router.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    _logger.debug("health_check")
    return {"status": "ok", "version": settings.version}


@router.post("/pipeline/run/form")
async def pipeline_run_form(
    dicom_study_json: Annotated[str, Form()],
    report_file: Annotated[UploadFile, File()],
    dicom_file: Annotated[UploadFile, File()],
    pipeline: DepPipeline,
    password: Annotated[SecretStr | None, Form()] = None,
) -> MagicLink:
    report_file_bytes, dicom_file_bytes = await asyncio.gather(
        report_file.read(), dicom_file.read()
    )
    study = DicomStudy.model_validate_json(dicom_study_json)
    record = MedicalRecordUpload(
        study=study,
        report_file=report_file_bytes,
        dicom_zip=dicom_file_bytes,
        password=password,
    )
    return await pipeline_run(record, pipeline)


@router.post("/pipeline/run/json")
async def pipeline_run(
    record: MedicalRecordUpload,
    pipeline: DepPipeline,
) -> MagicLink:
    """Run the full bridge pipeline for a medical record."""
    return await pipeline.run(record)
