"""Unit tests for the audit SQLite storage layer."""

from collections.abc import AsyncGenerator
from pathlib import Path

import aiosqlite
import pytest

from puente.audit.storage import add_record, setup
from puente.config import get_settings
from puente.domain.models import AuditRecord


@pytest.fixture
async def db(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> AsyncGenerator[aiosqlite.Connection]:
    monkeypatch.setenv(
        "PUENTE_AUDIT_SQLITE_FILE",
        str(tmp_path / "audit.db"),
    )
    get_settings.cache_clear()
    conn = await setup()
    yield conn
    await conn.close()


async def test_setup_creates_audit_table(
    db: aiosqlite.Connection,
) -> None:
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit'"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "audit"


async def test_add_record_inserts_and_commits(
    db: aiosqlite.Connection,
) -> None:
    record = AuditRecord(
        chain_cbor=b"chain",
        signature=b"sig",
        tsr=b"tsr",
        bucket_zstd=b"zstd",
    )
    await add_record(db, record)
    cursor = await db.execute(
        "SELECT chain_cbor, signature, tsr, bucket_zstd "
        "FROM audit WHERE id = 1"
    )
    row = await cursor.fetchone()
    assert row == (b"chain", b"sig", b"tsr", b"zstd")
