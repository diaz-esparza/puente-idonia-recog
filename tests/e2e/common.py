"""Shared helpers for end-to-end bridge tests."""

import httpx

from puente.domain.models import MedicalRecordUpload


async def post_pipeline(
    api_client: httpx.AsyncClient,
    endpoint: str,
    medical_record: MedicalRecordUpload,
    password: str | None = None,
) -> httpx.Response:
    if endpoint == "/pipeline/run/form":
        data: dict[str, str | None] = {
            "dicom_study_json": medical_record.study.model_dump_json(
                by_alias=False
            ),
            "password": password,
        }
        return await api_client.post(
            endpoint,
            data=data,
            files={
                "report_file": (
                    "report.pdf",
                    medical_record.report_file,
                    "application/pdf",
                ),
                "dicom_file": (
                    "study.dcm",
                    medical_record.dicom_zip,
                    "application/dicom",
                ),
            },
        )
    return await api_client.post(
        endpoint,
        content=medical_record.model_dump_json(by_alias=False),
        headers={"Content-Type": "application/json"},
    )
