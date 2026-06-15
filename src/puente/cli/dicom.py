# pyright: reportUnknownMemberType=false
"""DICOM loading and conversion primitives.

Loads single-frame MR Image Storage instances from a directory,
a .tar.zst archive, or a .zip archive. The zip path is the
canonical format used by the CLI demo — metadata is read from
the first DICOM file inside the zip, and the raw zip bytes are
forwarded as the ``dicom_zip`` payload.
"""

import zipfile
from io import BytesIO
from pathlib import Path

import pydicom

from puente.domain.models import DicomStudy


def get_source_info(path: Path) -> tuple[int, str]:
    """Return (slice_count, source_label) for CLI display."""
    if not path.exists():
        return 0, f"{path} (not found)"
    if path.is_file() and path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            count = sum(1 for n in zf.namelist() if n.endswith(".dcm"))
        label = f"{path.name} ({count} MR slices)"
    else:
        count = 0
        label = f"{path} (unsupported)"
    return count, label


def extract_study_from_zip(zip_bytes: bytes) -> DicomStudy:
    """Read the first DICOM file in a zip and extract study metadata."""
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        dcm_names = sorted(n for n in zf.namelist() if n.endswith(".dcm"))
        if not dcm_names:
            raise ValueError("No DICOM files found in zip archive")
        ds = pydicom.dcmread(BytesIO(zf.read(dcm_names[0])))
    return DicomStudy(
        patient_id=str(ds.PatientID),
        accession_number=str(ds.AccessionNumber),
        study_description=str(ds.StudyDescription),
    )
