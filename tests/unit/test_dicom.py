"""Unit tests for DICOM loading and conversion CLI primitives."""

import copy
from datetime import date, time
from io import BytesIO
from pathlib import Path

import pydicom
import pytest

from puente.cli.dicom import (
    _fix_datetime_types,
    _parse_da,
    _parse_tm,
    build_enhanced_mr,
    extract_study,
    get_source_info,
    load_datasets,
)
from puente.config import _PROJECT_ROOT
from puente.domain.models import DicomStudy
from tests.support.data import (
    build_minimal_dicom_file,
    build_minimal_dicom_zst,
)


class TestLoadDatasets:
    """Tests for loading DICOM datasets from directories and .tar.zst files."""

    def test_load_datasets_from_dir(self, tmp_path: Path) -> None:
        build_minimal_dicom_file(tmp_path / "slice1.dcm")
        build_minimal_dicom_file(tmp_path / "slice2.dcm")
        datasets = load_datasets(tmp_path)
        assert len(datasets) == 2
        assert datasets[0].PatientID == "PT-001"

    def test_load_datasets_from_zst(self, tmp_path: Path) -> None:
        zst_path = tmp_path / "archive.tar.zst"
        build_minimal_dicom_zst(zst_path, count=2)
        datasets = load_datasets(zst_path)
        assert len(datasets) == 2

    def test_load_datasets_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_datasets(tmp_path / "missing.tar.zst")

    def test_load_datasets_unsupported_extension_raises(
        self,
        tmp_path: Path,
    ) -> None:
        bad = tmp_path / "file.txt"
        bad.write_text("not dicom")
        with pytest.raises(
            ValueError,
            match=r"Expected a directory or \.tar\.zst",
        ):
            load_datasets(bad)


class TestGetSourceInfo:
    """Tests for get_source_info path introspection."""

    def test_get_source_info_from_zst(self, tmp_path: Path) -> None:
        zst_path = tmp_path / "archive.tar.zst"
        build_minimal_dicom_zst(zst_path, count=2)
        count, label = get_source_info(zst_path)
        assert count == 2
        assert "archive.tar.zst" in label
        assert "2 MR slices" in label

    def test_get_source_info_from_dir(self, tmp_path: Path) -> None:
        build_minimal_dicom_file(tmp_path / "slice1.dcm")
        build_minimal_dicom_file(tmp_path / "slice2.dcm")
        count, label = get_source_info(tmp_path)
        assert count == 2
        assert str(tmp_path) in label
        assert "2 MR slices" in label

    def test_get_source_info_missing(self, tmp_path: Path) -> None:
        count, label = get_source_info(tmp_path / "missing.tar.zst")
        assert count == 0
        assert "not found" in label

    def test_get_source_info_unsupported(self, tmp_path: Path) -> None:
        bad = tmp_path / "file.txt"
        bad.write_text("not dicom")
        count, label = get_source_info(bad)
        assert count == 0
        assert "unsupported" in label


class TestExtractStudy:
    """Tests for extracting DicomStudy from loaded datasets."""

    def test_extract_study(self, tmp_path: Path) -> None:
        build_minimal_dicom_file(tmp_path / "slice1.dcm")
        datasets = load_datasets(tmp_path)
        study = extract_study(datasets)
        assert study == DicomStudy(
            patient_id="PT-001",
            accession_number="ACC-001",
            study_description="Test Study",
        )


class TestDateTimeParsing:
    """Tests for DICOM date/time parsing helpers."""

    def test_parse_da(self) -> None:
        assert _parse_da("20240315") == date(2024, 3, 15)

    def test_parse_tm_full(self) -> None:
        assert _parse_tm("143052") == time(14, 30, 52)

    def test_parse_tm_short(self) -> None:
        assert _parse_tm("1200") == time(12, 0, 0)

    def test_parse_tm_with_fraction(self) -> None:
        assert _parse_tm("143052.123") == time(14, 30, 52)

    def test_fix_datetime_types(self) -> None:
        ds = pydicom.Dataset()
        ds.AcquisitionDate = "20240101"
        ds.AcquisitionTime = "120000"
        _fix_datetime_types(ds)
        assert ds.AcquisitionDate == date(2024, 1, 1)
        assert ds.AcquisitionTime == time(12, 0, 0)

    def test_fix_datetime_types_idempotent(self) -> None:
        ds = pydicom.Dataset()
        ds.AcquisitionDate = "20240101"
        ds.AcquisitionTime = "120000"
        _fix_datetime_types(ds)
        _fix_datetime_types(ds)
        assert ds.AcquisitionDate == date(2024, 1, 1)
        assert ds.AcquisitionTime == time(12, 0, 0)


class TestBuildEnhancedMr:
    """Tests for converting legacy MR slices into Enhanced MR."""

    @pytest.fixture
    def real_mr_datasets(self) -> list[pydicom.Dataset]:
        """Load the first two slices from the real data archive."""
        path = _PROJECT_ROOT / "data" / "dicom.tar.zst"
        all_datasets = load_datasets(path)
        return [copy.deepcopy(ds) for ds in all_datasets[:2]]

    def test_build_enhanced_mr_returns_valid_dicom(
        self,
        real_mr_datasets: list[pydicom.Dataset],
    ) -> None:
        result = build_enhanced_mr(real_mr_datasets)
        enhanced = pydicom.dcmread(BytesIO(result))
        assert enhanced.Modality == "MR"
        assert enhanced.NumberOfFrames == 2
        assert enhanced.SOPClassUID == "1.2.840.10008.5.1.4.1.1.4.4"

    def test_build_enhanced_mr_normalizes_series_uid(
        self,
        real_mr_datasets: list[pydicom.Dataset],
    ) -> None:
        original_uids = [ds.SeriesInstanceUID for ds in real_mr_datasets]
        _ = build_enhanced_mr(real_mr_datasets)
        assert (
            real_mr_datasets[0].SeriesInstanceUID
            == real_mr_datasets[1].SeriesInstanceUID
        )
        assert real_mr_datasets[0].SeriesInstanceUID != original_uids[0]

    def test_build_enhanced_mr_sets_instance_numbers(
        self,
        real_mr_datasets: list[pydicom.Dataset],
    ) -> None:
        _ = build_enhanced_mr(real_mr_datasets)
        assert real_mr_datasets[0].InstanceNumber == "1"
        assert real_mr_datasets[1].InstanceNumber == "2"

    def test_build_enhanced_mr_sets_series_number(
        self,
        real_mr_datasets: list[pydicom.Dataset],
    ) -> None:
        _ = build_enhanced_mr(real_mr_datasets)
        assert real_mr_datasets[0].SeriesNumber == "1"
