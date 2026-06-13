"""Unit tests for the audit CLI inspection helpers."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import cbor2
import pytest

from puente.audit.pki import keygen
from puente.cli.audit import _build_chains, _verify_signature
from puente.config import get_settings
from puente.domain.models import AuditChain, AuditRecord


class TestVerifySignature:
    def test_valid_signature(
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
        chain_cbor = b"test-chain"
        signature = key.sign(chain_cbor)
        record = AuditRecord(
            chain_cbor=chain_cbor,
            signature=signature,
            tsr=None,
            bucket_zstd=b"",
        )
        ok, detail = _verify_signature(record)
        assert ok is True
        assert detail == ""

    def test_invalid_signature(self) -> None:
        record = AuditRecord(
            chain_cbor=b"chain",
            signature=b"bad-sig",
            tsr=None,
            bucket_zstd=b"",
        )
        ok, detail = _verify_signature(record)
        assert ok is False
        assert detail == "Clave inválida"


class TestBuildChains:
    def test_single_contiguous_chain(self) -> None:
        ts = datetime.now(UTC)
        chain1 = AuditChain(
            sequence=0,
            previous_chain_hash=None,
            previous_tsr_hash=None,
            bucket_hash=b"1",
            ts=ts,
        )
        chain2 = AuditChain(
            sequence=1,
            previous_chain_hash=sha256(
                cbor2.dumps(chain1.model_dump(), canonical=True)
            ).digest(),
            previous_tsr_hash=None,
            bucket_hash=b"2",
            ts=ts,
        )
        rows: list[tuple[int, bytes]] = [
            (1, cbor2.dumps(chain1.model_dump(), canonical=True)),
            (2, cbor2.dumps(chain2.model_dump(), canonical=True)),
        ]
        chains = _build_chains(rows)
        assert len(chains) == 1
        assert len(chains[0]) == 2

    def test_broken_link_creates_two_chains(self) -> None:
        ts = datetime.now(UTC)
        chain1 = AuditChain(
            sequence=0,
            previous_chain_hash=None,
            previous_tsr_hash=None,
            bucket_hash=b"1",
            ts=ts,
        )
        chain2 = AuditChain(
            sequence=1,
            previous_chain_hash=b"wrong",
            previous_tsr_hash=None,
            bucket_hash=b"2",
            ts=ts,
        )
        rows: list[tuple[int, bytes]] = [
            (1, cbor2.dumps(chain1.model_dump(), canonical=True)),
            (2, cbor2.dumps(chain2.model_dump(), canonical=True)),
        ]
        chains = _build_chains(rows)
        assert len(chains) == 2
        assert len(chains[0]) == 1
        assert len(chains[1]) == 1
