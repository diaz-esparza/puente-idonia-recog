"""Shared test data builders.

Re-uses the production mock generators from ``puente.cli.mocks`` whenever
possible to avoid duplication.
"""

import tarfile
from compression import zstd
from io import BytesIO
from pathlib import Path

import pydicom
import pymupdf
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import UID, ExplicitVRLittleEndian, generate_uid

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


def build_minimal_dicom_file(path: Path) -> None:
    """Write a minimal valid DICOM file to *path* for unit tests."""
    ds = Dataset()
    ds.PatientName = "Test^Patient"
    ds.PatientID = "PT-001"
    ds.AccessionNumber = "ACC-001"
    ds.StudyDescription = "Test Study"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    sop_class_uid = UID("1.2.840.10008.5.1.4.1.1.2")
    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = generate_uid()
    ds.Modality = "CT"
    ds.Rows = 2
    ds.Columns = 2
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = b"\x00" * 4
    ds.AcquisitionDate = "20240101"
    ds.AcquisitionTime = "120000"

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds.file_meta = file_meta
    pydicom.dcmwrite(str(path), ds, enforce_file_format=True)


def build_minimal_dicom_zst(path: Path, count: int = 2) -> None:
    """Write a .tar.zst with *count* minimal DICOM files to *path*."""
    tar_buf = BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        for i in range(count):
            dcm_buf = BytesIO()
            ds = Dataset()
            ds.PatientName = "Test^Patient"
            ds.PatientID = f"PT-{i:03d}"
            ds.AccessionNumber = f"ACC-{i:03d}"
            ds.StudyDescription = "Test Study"
            ds.StudyInstanceUID = generate_uid()
            ds.SeriesInstanceUID = generate_uid()
            sop_class_uid = UID("1.2.840.10008.5.1.4.1.1.2")
            ds.SOPClassUID = sop_class_uid
            ds.SOPInstanceUID = generate_uid()
            ds.Modality = "CT"
            ds.Rows = 2
            ds.Columns = 2
            ds.SamplesPerPixel = 1
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.BitsAllocated = 8
            ds.BitsStored = 8
            ds.HighBit = 7
            ds.PixelRepresentation = 0
            ds.PixelData = b"\x00" * 4
            file_meta = FileMetaDataset()
            file_meta.MediaStorageSOPClassUID = sop_class_uid
            file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.file_meta = file_meta
            pydicom.dcmwrite(dcm_buf, ds, enforce_file_format=True)
            info = tarfile.TarInfo(name=f"slice{i}.dcm")
            info.size = len(dcm_buf.getvalue())
            dcm_buf.seek(0)
            tar.addfile(info, dcm_buf)

    tar_buf.seek(0)
    path.write_bytes(zstd.compress(tar_buf.read()))


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
        report_file=report_pdf,
        dicom_file=dicom_file,
    )
