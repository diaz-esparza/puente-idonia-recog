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
        secret = "S2dGVzdHNlY3JldC0zMi1ieXRlcy1rZXktMDEyMzQ1Njc="
        assert adapter._decode_secret(SecretStr(secret)).get_secret_value()

    def test_create_jwt_generates_valid_token(self) -> None:
        adapter = IdoniaAdapter()
        token = adapter._create_jwt()
        assert token.startswith("eyJ")
        assert adapter._get_jwt() == token

    def test_get_jwt_returns_cached_token_when_valid(self) -> None:
        adapter = IdoniaAdapter()
        assert adapter._get_jwt() == adapter._get_jwt()

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
        link = await adapter.create_magic_link(_make_study(), password=None)

        assert link.url == "https://magic.test/99"
        assert link.pin == "1234"
        assert route.called

    def test_serialize_password_returns_empty_string_when_none(self) -> None:
        assert IdoniaAdapter._serialize_password(None) == ""

    def test_serialize_password_hashes_with_sha256_hex_base64(self) -> None:
        # Reference value from IDONIA guide
        password = SecretStr("1234")
        assert (
            IdoniaAdapter._serialize_password(password)
            == "MDNhYzY3NDIxNmYzZTE1Yzc2MWVlMWE1ZTI1NWYwNj"
            + "c5NTM2MjNjOGIzODhiNDQ1OWUxM2Y5NzhkN2M4NDZmNA=="
        )

    async def test_create_magic_link_sends_hashed_password(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        route = respx_mock.put(
            f"{settings.idonia_base_url}/ml",
        ).respond(200, json=[{"URL": "https://magic.test/99", "PIN": "1234"}])

        adapter = IdoniaAdapter()
        password = SecretStr("password-1234")
        _ = await adapter.create_magic_link(_make_study(), password=password)

        request = route.calls.last.request
        sent_password = request.url.params.get("password")
        assert sent_password == IdoniaAdapter._serialize_password(password)


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
            _ = await adapter.create_magic_link(_make_study(), password=None)

    async def test_create_magic_link_raises_on_wrong_length(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        _ = respx_mock.put(
            f"{settings.idonia_base_url}/ml",
        ).respond(200, json=[{"URL": "a"}, {"URL": "b"}])

        adapter = IdoniaAdapter()
        with pytest.raises(RuntimeError, match="Unexpected Idonia"):
            _ = await adapter.create_magic_link(_make_study(), password=None)
