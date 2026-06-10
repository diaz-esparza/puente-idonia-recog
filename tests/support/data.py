"""Shared test data builders.

Re-uses the production mock generators from ``puente.cli.mocks`` whenever
possible to avoid duplication.
"""

import base64

import pymupdf

from puente.cli.mocks import build_demo_record as _build_demo_record
from puente.domain.models import DicomStudy, MedicalRecordUpload


def build_demo_record() -> MedicalRecordUpload:
    """Return the full synthetic record used by the CLI demo."""
    return _build_demo_record()


def build_simple_pdf(text: str = "Original clinical report text.") -> bytes:
    """Generate a minimal valid PDF containing *text*."""
    doc = pymupdf.open()
    page = doc.new_page()
    _ = page.insert_text((72, 72), text, fontsize=12)
    return doc.tobytes()


def build_multipage_pdf() -> bytes:
    doc = pymupdf.open()
    p1 = doc.new_page()
    _ = p1.insert_text((72, 72), "Page one.", fontsize=12)
    p2 = doc.new_page()
    _ = p2.insert_text((72, 72), "Page two.", fontsize=12)
    return doc.tobytes()


def build_simple_dicom() -> bytes:
    """Minimal fake DICOM binary for tests."""
    return b"fake-dicom-binary"


def build_simple_record(
    *,
    patient_id: str = "PT-001",
    accession_number: str = "ACC-2024-001",
    study_description: str = "Chest CT",
    report_text: str = "Original clinical report text.",
) -> MedicalRecordUpload:
    """Create a minimal ``MedicalRecordUpload`` for unit tests.

    The PDF and DICOM content are base64-encoded so the model validates
    without needing ``model_construct``.
    """
    study = DicomStudy(
        patient_id=patient_id,
        accession_number=accession_number,
        study_description=study_description,
    )
    report_pdf = build_simple_pdf(report_text)
    dicom_file = build_simple_dicom()
    return MedicalRecordUpload(
        study=study,
        report_file=base64.b64encode(report_pdf),
        dicom_file=base64.b64encode(dicom_file),
    )
