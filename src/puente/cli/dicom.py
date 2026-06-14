# pyright: reportUnknownMemberType=false
"""DICOM loading and conversion primitives.

Loads single-frame MR Image Storage instances from a directory or
a .tar.zst archive and converts them into a single DICOM Enhanced
MR Image Storage object suitable for upload via the Idonia adapter.
"""

import tarfile
from compression import zstd
from datetime import date, time
from io import BytesIO
from pathlib import Path

import pydicom
from highdicom.legacy import LegacyConvertedEnhancedMRImage
from pydicom.dataset import Dataset
from pydicom.uid import generate_uid

from puente.domain.models import DicomStudy


def load_datasets(path: Path) -> list[Dataset]:
    """Load DICOM datasets from a directory or .tar.zst archive."""
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")
    if path.is_file() and path.suffix == ".zst":
        return _load_from_zst(path)
    if path.is_dir():
        return _load_from_dir(path)
    raise ValueError(f"Expected a directory or .tar.zst file, got: {path}")


def get_source_info(path: Path) -> tuple[int, str]:
    """Return (slice_count, source_label) for CLI display."""
    if not path.exists():
        return 0, f"{path} (not found)"
    if path.is_file() and path.suffix == ".zst":
        count = _zst_dcm_count(path)
        label = f"{path.name} ({count} MR slices)"
    elif path.is_dir():
        count = len(list(path.glob("*.dcm")))
        label = f"{path} ({count} MR slices)"
    else:
        count = 0
        label = f"{path} (unsupported)"
    return count, label


def extract_study(datasets: list[Dataset]) -> DicomStudy:
    """Build a DicomStudy from the first loaded dataset."""
    ds = datasets[0]
    return DicomStudy(
        patient_id=str(ds.PatientID),
        accession_number=str(ds.AccessionNumber),
        study_description=str(ds.StudyDescription),
    )


# ── internal helpers ────────────────────────────────────────────


def _load_from_dir(path: Path) -> list[Dataset]:
    files = sorted(path.glob("*.dcm"))
    if not files:
        raise ValueError(f"No DICOM files found in {path}")
    return [pydicom.dcmread(str(f)) for f in files]


def _open_zst_tar(path: Path) -> tarfile.TarFile:
    """Open a .tar.zst archive and return a TarFile handle."""
    compressed = path.read_bytes()
    decompressed = zstd.decompress(compressed)
    return tarfile.open(fileobj=BytesIO(decompressed))


def _load_from_zst(path: Path) -> list[Dataset]:
    datasets: list[Dataset] = []
    with _open_zst_tar(path) as tar:
        for member in sorted(tar.getmembers(), key=lambda m: m.name):
            if not member.name.endswith(".dcm"):
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            datasets.append(pydicom.dcmread(BytesIO(extracted.read())))
    if not datasets:
        raise ValueError(f"No DICOM files found in {path}")
    return datasets


def _zst_dcm_count(path: Path) -> int:
    with _open_zst_tar(path) as tar:
        return sum(1 for m in tar.getmembers() if m.name.endswith(".dcm"))


def _parse_da(raw: str) -> date:
    """Parse a DICOM date string (YYYYMMDD) into a date."""
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))


def _parse_tm(raw: str) -> time:
    """Parse a DICOM time string (HHMMSS[.ffffff]) into a time."""
    # Strip fractional seconds and pad to 6 digits to avoid short-string
    # issues (e.g. "1200" -> "120000").
    clean = raw.split(".", maxsplit=1)[0].ljust(6, "0")
    return time(int(clean[:2]), int(clean[2:4]), int(clean[4:6]))


def _fix_datetime_types(ds: Dataset) -> None:
    """Coerce DA/TM strings into date/time for highdicom internals."""
    raw = getattr(ds, "AcquisitionDate", None)
    if raw is not None and not isinstance(raw, date):
        ds.AcquisitionDate = _parse_da(str(raw))
    raw = getattr(ds, "AcquisitionTime", None)
    if raw is not None and not isinstance(raw, time):
        ds.AcquisitionTime = _parse_tm(str(raw))


def build_enhanced_mr(datasets: list[Dataset]) -> bytes:
    """Merge single-frame MR datasets into a single Enhanced MR DICOM.

    Returns the raw DICOM bytes of the merged instance.
    The original datasets are mutated in place (normalised series UID
    and date/time coercion).
    """
    shared_series_uid = generate_uid()
    for index, ds in enumerate(datasets):
        ds.SeriesInstanceUID = shared_series_uid
        ds.SeriesNumber = "1"
        ds.InstanceNumber = str(index + 1)
        _fix_datetime_types(ds)

    enhanced = LegacyConvertedEnhancedMRImage(
        legacy_datasets=datasets,
        series_instance_uid=generate_uid(),
        series_number=100,
        sop_instance_uid=generate_uid(),
        instance_number=1,
    )

    buf = BytesIO()
    enhanced.save_as(buf)  # type: ignore[arg-type]
    return buf.getvalue()
