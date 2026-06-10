"""Unit tests for the Idonia storage adapter."""

import httpx
import pytest
import respx
from pydantic import SecretStr

from puente.adapters.idonia import IdoniaAdapter
from puente.config import Settings
from puente.domain.models import DicomStudy


def _make_study() -> DicomStudy:
    return DicomStudy(
        patient_id="P1", accession_number="A1", study_description="CT"
    )


class TestIdoniaAdapterHappy:
    """Basic tests for the Idonia medical storage adapter."""

    def test_decode_secret_strips_s2_prefix(self) -> None:
        adapter = IdoniaAdapter()
        encoded = "S2dGVzdHNlY3JldC0zMi1ieXRlcy1rZXktMDEyMzQ1Njc="
        secret = adapter._decode_secret(SecretStr(encoded))
        assert secret.get_secret_value() is not None

    def test_create_jwt_generates_valid_token(self) -> None:
        adapter = IdoniaAdapter()
        token = adapter._create_jwt()
        assert token.startswith("eyJ")
        assert adapter._get_jwt() == token

    def test_get_jwt_returns_cached_token_when_valid(self) -> None:
        adapter = IdoniaAdapter()
        first = adapter._get_jwt()
        second = adapter._get_jwt()
        assert first == second

    async def test_upload_dicom_calls_correct_endpoint(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        route = respx_mock.post(
            f"{settings.idonia_base_url}/files/dicom_hak_num3",
        ).respond(200, json=["dicom-id-42"])

        adapter = IdoniaAdapter()
        file_id = await adapter.upload_dicom(_make_study(), b"fake-dicom")

        assert file_id == "dicom-id-42"
        assert route.called

    async def test_upload_report_calls_correct_endpoint(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        route = respx_mock.post(
            f"{settings.idonia_base_url}/files/report_hak_num3",
        ).respond(200, json=["report-id-42"])

        adapter = IdoniaAdapter()
        file_id = await adapter.upload_report(_make_study(), b"fake-report")

        assert file_id == "report-id-42"
        assert route.called

    async def test_create_magic_link_returns_parsed_link(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        route = respx_mock.put(
            f"{settings.idonia_base_url}/ml",
        ).respond(200, json=[{"URL": "https://magic.test/99", "PIN": "1234"}])

        adapter = IdoniaAdapter()
        link = await adapter.create_magic_link(_make_study())

        assert link.url == "https://magic.test/99"
        assert link.pin == "1234"
        assert route.called


class TestIdoniaAdapterError:
    """Error management tests for the Idonia medical storage adapter."""

    async def test_upload_dicom_raises_on_http_error(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        _ = respx_mock.post(
            f"{settings.idonia_base_url}/files/dicom_hak_num3",
        ).respond(500)

        adapter = IdoniaAdapter()
        with pytest.raises(httpx.HTTPStatusError):
            _ = await adapter.upload_dicom(_make_study(), b"fake-dicom")

    async def test_upload_report_raises_on_http_error(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        _ = respx_mock.post(
            f"{settings.idonia_base_url}/files/report_hak_num3",
        ).respond(400)

        adapter = IdoniaAdapter()
        with pytest.raises(httpx.HTTPStatusError):
            _ = await adapter.upload_report(_make_study(), b"fake-report")

    async def test_upload_dicom_raises_on_unexpected_body(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        _ = respx_mock.post(
            f"{settings.idonia_base_url}/files/dicom_hak_num3",
        ).respond(200, json={"not": "a-list"})

        adapter = IdoniaAdapter()
        with pytest.raises(RuntimeError, match="Unexpected Idonia"):
            _ = await adapter.upload_dicom(_make_study(), b"fake-dicom")

    async def test_create_magic_link_raises_on_non_list_body(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        _ = respx_mock.put(
            f"{settings.idonia_base_url}/ml",
        ).respond(200, json={"not": "a-list"})

        adapter = IdoniaAdapter()
        with pytest.raises(RuntimeError, match="Unexpected Idonia"):
            _ = await adapter.create_magic_link(_make_study())

    async def test_create_magic_link_raises_on_wrong_length(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        _ = respx_mock.put(
            f"{settings.idonia_base_url}/ml",
        ).respond(200, json=[{"URL": "a"}, {"URL": "b"}])

        adapter = IdoniaAdapter()
        with pytest.raises(RuntimeError, match="Unexpected Idonia"):
            _ = await adapter.create_magic_link(_make_study())
