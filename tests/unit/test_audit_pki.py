"""Unit tests for the audit PKI helpers."""

import stat
from pathlib import Path
from unittest import mock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from rfc3161ng import TimestampingError

from puente.audit.pki import keygen, timestamp, to_canonical_bin
from puente.config import get_settings


class TestToCanonicalBin:
    def test_returns_deterministic_bytes(self) -> None:
        data: dict[str, int] = {"b": 2, "a": 1}
        first = to_canonical_bin(data)
        second = to_canonical_bin(data)
        assert first == second

    def test_order_independence(self) -> None:
        assert to_canonical_bin({"a": 1, "b": 2}) == to_canonical_bin(
            {"b": 2, "a": 1}
        )


class TestKeygen:
    def test_generates_new_key_when_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv(
            "PUENTE_AUDIT_PRIVATE_KEY_FILE",
            str(tmp_path / "signing_key.pem"),
        )
        monkeypatch.setenv(
            "PUENTE_AUDIT_PUBLIC_KEY_FILE",
            str(tmp_path / "signing_key.pub"),
        )
        get_settings.cache_clear()
        keygen.cache_clear()

        key = keygen()
        assert isinstance(key, Ed25519PrivateKey)
        assert (tmp_path / "signing_key.pem").exists()
        assert (tmp_path / "signing_key.pub").exists()
        perms = stat.S_IMODE((tmp_path / "signing_key.pem").stat().st_mode)
        assert perms == 0o600

    def test_loads_existing_key(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv(
            "PUENTE_AUDIT_PRIVATE_KEY_FILE",
            str(tmp_path / "signing_key.pem"),
        )
        monkeypatch.setenv(
            "PUENTE_AUDIT_PUBLIC_KEY_FILE",
            str(tmp_path / "signing_key.pub"),
        )
        get_settings.cache_clear()
        keygen.cache_clear()

        first = keygen()
        keygen.cache_clear()
        get_settings.cache_clear()
        second = keygen()
        assert first.public_key() == second.public_key()

    def test_rejects_non_ed25519_key(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_path = tmp_path / "rsa_key.pem"
        key_path.write_bytes(pem)
        monkeypatch.setenv("PUENTE_AUDIT_PRIVATE_KEY_FILE", str(key_path))
        monkeypatch.setenv(
            "PUENTE_AUDIT_PUBLIC_KEY_FILE",
            str(tmp_path / "signing_key.pub"),
        )
        get_settings.cache_clear()
        keygen.cache_clear()

        with pytest.raises(TypeError, match="Expected a Ed25519PrivateKey"):
            keygen()


class TestTimestamp:
    async def test_returns_tsr_bytes_on_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PUENTE_AUDIT_TSA_URL", "https://tsa.test")
        get_settings.cache_clear()
        with (
            mock.patch(
                "puente.audit.pki.RemoteTimestamper",
            ) as mock_tsa,
            mock.patch(
                "puente.audit.pki.encode_timestamp_response",
                return_value=b"tsr-bytes",
            ),
        ):
            tsa_instance = mock_tsa.return_value
            tsa_instance.return_value = mock.Mock()
            result = await timestamp(b"signature")
        assert result == b"tsr-bytes"

    async def test_returns_none_on_tsa_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PUENTE_AUDIT_TSA_URL", "https://tsa.test")
        get_settings.cache_clear()
        with mock.patch(
            "puente.audit.pki.RemoteTimestamper",
            side_effect=Exception("boom"),
        ):
            result = await timestamp(b"signature")
        assert result is None

    async def test_returns_none_on_timestamping_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PUENTE_AUDIT_TSA_URL", "https://tsa.test")
        get_settings.cache_clear()
        with mock.patch(
            "puente.audit.pki.RemoteTimestamper",
            side_effect=TimestampingError("boom"),
        ):
            result = await timestamp(b"signature")
        assert result is None

    async def test_returns_none_on_format_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PUENTE_AUDIT_TSA_URL", "https://tsa.test")
        get_settings.cache_clear()
        with (
            mock.patch(
                "puente.audit.pki.RemoteTimestamper",
            ) as mock_tsa,
            mock.patch(
                "puente.audit.pki.encode_timestamp_response",
                return_value="not-bytes",
            ),
        ):
            tsa_instance = mock_tsa.return_value
            tsa_instance.return_value = mock.Mock()
            result = await timestamp(b"signature")
        assert result is None
