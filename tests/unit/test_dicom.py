"""Unit tests for DICOM zip loading primitives."""

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from puente.cli.dicom import extract_study_from_zip, get_source_info
from puente.domain.models import DicomStudy
from tests.support.data import build_simple_dicom_bytes


def _build_dicom_zip(path: Path, count: int = 2) -> None:
    """Write a .zip with *count* minimal DICOM files to *path*."""
    dcm = build_simple_dicom_bytes()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(count):
            zf.writestr(f"slice{i}.dcm", dcm)


class TestGetSourceInfo:
    """Tests for get_source_info path introspection."""

    def test_get_source_info_from_zip(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "archive.zip"
        _build_dicom_zip(zip_path, count=2)
        count, label = get_source_info(zip_path)
        assert count == 2
        assert "archive.zip" in label
        assert "2 MR slices" in label

    def test_get_source_info_missing(self, tmp_path: Path) -> None:
        count, label = get_source_info(tmp_path / "missing.zip")
        assert count == 0
        assert "not found" in label

    def test_get_source_info_unsupported(self, tmp_path: Path) -> None:
        bad = tmp_path / "file.txt"
        bad.write_text("not dicom")
        count, label = get_source_info(bad)
        assert count == 0
        assert "unsupported" in label


class TestExtractStudyFromZip:
    """Tests for extracting DicomStudy from a DICOM zip."""

    def test_extract_study_from_zip(self) -> None:
        dcm = build_simple_dicom_bytes()
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("slice0.dcm", dcm)
        study = extract_study_from_zip(buf.getvalue())
        assert study == DicomStudy(
            patient_id="PT-001",
            accession_number="ACC-001",
            study_description="Test Study",
        )

    def test_extract_study_from_zip_no_dicom_raises(self) -> None:
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("readme.txt", b"not a dicom")
        with pytest.raises(ValueError, match="No DICOM files found"):
            extract_study_from_zip(buf.getvalue())
