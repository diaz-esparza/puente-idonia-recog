# pyright: reportUnknownMemberType=false
"""Temporary mock data generators for CLI demo commands.

These helpers are slated for removal once the project migrates to
proper pytest-based fixtures and integration tests.
"""

from functools import lru_cache

import pymupdf
from pydantic import SecretStr

from puente.cli.dicom import extract_study_from_zip, get_source_info
from puente.config import get_settings
from puente.domain.models import DicomStudy, MedicalRecordUpload

DEMO_PASSWORD = SecretStr("password-1234")


@lru_cache(maxsize=1)
def _build_demo_data() -> tuple[DicomStudy, bytes, bytes]:
    """Build and cache the expensive demo data (DICOM zip + PDF)."""
    settings = get_settings()
    zip_bytes = settings.cli_dicom_path.read_bytes()
    study = extract_study_from_zip(zip_bytes)
    report_pdf = _create_demo_report_pdf()
    return study, report_pdf, zip_bytes


def build_demo_record() -> MedicalRecordUpload:
    """Build the demo patient record from pre-bundled DICOM zip."""
    study, report_pdf, dicom_zip = _build_demo_data()
    return MedicalRecordUpload(
        study=study,
        report_file=report_pdf,
        dicom_zip=dicom_zip,
        password=DEMO_PASSWORD,
    )


def get_demo_source_info() -> tuple[int, str]:
    """Return (slice_count, source_label) for CLI display."""
    settings = get_settings()
    return get_source_info(settings.cli_dicom_path)


DEMO_REPORT_TEXT = (
    "INFORME QUIRÚRGICO\n\n"
    "Paciente: Clara Martínez López\n"
    "NHC: 7845321\n"
    "DNI: 12345678Z\n"
    "Fecha: 2024-03-15\n\n"
    "CIRUGÍA DE RODILLA DERECHA\n\n"
    "Se realizó artroscopia de rodilla derecha con resección de "
    "menisco medial roto.\nProcedimiento sin incidencias. "
    "El paciente evolucionó favorablemente en el postoperatorio "
    "inmediato.\n\n"
    "Recomendaciones:\n"
    "- Reposo relativo 48h\n"
    "- Fisioterapia desde la semana siguiente\n"
    "- Revisión en 15 días"
)


def _create_demo_report_pdf() -> bytes:
    """Generate a synthetic surgical report PDF for the demo."""
    doc = pymupdf.open()
    page = doc.new_page()
    _ = page.insert_text((72, 72), DEMO_REPORT_TEXT, fontsize=11)
    return doc.tobytes()
