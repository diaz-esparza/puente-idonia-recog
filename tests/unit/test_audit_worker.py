"""Unit tests for the audit background worker."""

import asyncio
import contextlib
import hashlib
from collections.abc import Generator
from compression import zstd
from pathlib import Path
from typing import cast
from unittest import mock

import cbor2
import pytest

from puente.audit.worker import AuditDataTypes, AuditWorker, get_worker
from puente.config import get_settings
from puente.domain.models import AuditRecord


@pytest.fixture
def worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[AuditWorker]:
    """Fresh ``AuditWorker`` with external side-effects mocked."""
    monkeypatch.setenv(
        "PUENTE_AUDIT_PRIVATE_KEY_FILE",
        str(tmp_path / "signing_key.pem"),
    )
    monkeypatch.setenv(
        "PUENTE_AUDIT_PUBLIC_KEY_FILE",
        str(tmp_path / "signing_key.pub"),
    )
    monkeypatch.setenv(
        "PUENTE_AUDIT_SQLITE_FILE",
        str(tmp_path / "audit.db"),
    )
    monkeypatch.setenv("PUENTE_AUDIT_FLUSH_INTERVAL_S", "1")
    get_settings.cache_clear()

    mock_key = mock.Mock()
    mock_key.sign = mock.Mock(return_value=b"signature")

    with (
        mock.patch(
            "puente.audit.worker.pki.keygen",
            return_value=mock_key,
        ),
        mock.patch(
            "puente.audit.worker.pki.timestamp",
            new_callable=mock.AsyncMock,
            return_value=b"tsr",
        ),
        mock.patch(
            "puente.audit.worker.storage.setup",
            new_callable=mock.AsyncMock,
            return_value=mock.AsyncMock(),
        ),
    ):
        w = AuditWorker()
        yield w
        get_settings.cache_clear()


async def _drain_flush_loop(worker: AuditWorker) -> None:
    """Run ``flush_loop`` for one iteration then cancel it."""
    call_count = 0

    async def _sleep(_: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise asyncio.CancelledError

    with mock.patch("asyncio.sleep", side_effect=_sleep):
        task = asyncio.create_task(worker.flush_loop())
        with contextlib.suppress(asyncio.CancelledError):
            await task


class TestAuditWorkerPut:
    async def test_put_accumulates_events(self, worker: AuditWorker) -> None:
        worker.put(b"e1", AuditDataTypes.LOGS)
        worker.put(b"e2", AuditDataTypes.LOGS)
        with mock.patch.object(
            worker,
            "_process_bucket",
            new_callable=mock.AsyncMock,
        ) as mock_process:
            await _drain_flush_loop(worker)
        bucket = mock_process.call_args.args[0]
        assert bucket[AuditDataTypes.LOGS] == [b"e1", b"e2"]

    async def test_put_isolated_by_type(self, worker: AuditWorker) -> None:
        worker.put(b"e1", AuditDataTypes.LOGS)
        worker.put(b"e2", AuditDataTypes.TRACES)
        with mock.patch.object(
            worker,
            "_process_bucket",
            new_callable=mock.AsyncMock,
        ) as mock_process:
            await _drain_flush_loop(worker)
        bucket = mock_process.call_args.args[0]
        assert bucket[AuditDataTypes.LOGS] == [b"e1"]
        assert bucket[AuditDataTypes.TRACES] == [b"e2"]


class TestAuditWorkerGetDb:
    async def test_get_db_returns_connection(
        self, worker: AuditWorker
    ) -> None:
        db = await worker.get_db()
        assert db is not None

    async def test_get_db_caches_connection(self, worker: AuditWorker) -> None:
        db1 = await worker.get_db()
        db2 = await worker.get_db()
        assert db1 is db2

    async def test_get_db_calls_setup_once(self, worker: AuditWorker) -> None:
        with mock.patch(
            "puente.audit.worker.storage.setup",
            new_callable=mock.AsyncMock,
        ) as mock_setup:
            _ = await worker.get_db()
            _ = await worker.get_db()
        mock_setup.assert_awaited_once()


class TestAuditWorkerProcessBucket:
    async def test_process_bucket_creates_audit_record(
        self,
        worker: AuditWorker,
    ) -> None:
        with mock.patch(
            "puente.audit.worker.storage.add_record",
            new_callable=mock.AsyncMock,
        ) as mock_add:
            await worker._process_bucket({AuditDataTypes.LOGS: [b"event1"]})
        record = mock_add.call_args.args[1]
        assert isinstance(record, AuditRecord)
        assert record.signature == b"signature"
        assert record.tsr == b"tsr"

    async def test_process_bucket_updates_sequence(
        self,
        worker: AuditWorker,
    ) -> None:
        with mock.patch(
            "puente.audit.worker.storage.add_record",
            new_callable=mock.AsyncMock,
        ) as mock_add:
            await worker._process_bucket({AuditDataTypes.LOGS: [b"e1"]})
        first_record = mock_add.call_args.args[1]
        first_chain = cbor2.loads(first_record.chain_cbor)
        assert first_chain["sequence"] == 0

        with mock.patch(
            "puente.audit.worker.storage.add_record",
            new_callable=mock.AsyncMock,
        ) as mock_add:
            await worker._process_bucket({AuditDataTypes.LOGS: [b"e2"]})
        second_record = mock_add.call_args.args[1]
        second_chain = cbor2.loads(second_record.chain_cbor)
        assert second_chain["sequence"] == 1

    async def test_process_bucket_links_to_previous_chain(
        self,
        worker: AuditWorker,
    ) -> None:
        with mock.patch(
            "puente.audit.worker.storage.add_record",
            new_callable=mock.AsyncMock,
        ) as mock_add:
            await worker._process_bucket({AuditDataTypes.LOGS: [b"e1"]})
        first_record = mock_add.call_args.args[1]

        with mock.patch(
            "puente.audit.worker.storage.add_record",
            new_callable=mock.AsyncMock,
        ) as mock_add:
            await worker._process_bucket({AuditDataTypes.LOGS: [b"e2"]})
        second_record = mock_add.call_args.args[1]

        expected_hash = hashlib.sha256(first_record.chain_cbor).digest()
        chain = cbor2.loads(second_record.chain_cbor)
        assert chain["previous_chain_hash"] == expected_hash

    async def test_process_bucket_updates_previous_tsr_hash(
        self,
        worker: AuditWorker,
    ) -> None:
        with mock.patch(
            "puente.audit.worker.storage.add_record",
            new_callable=mock.AsyncMock,
        ) as mock_add:
            await worker._process_bucket({AuditDataTypes.LOGS: [b"e1"]})

        with mock.patch(
            "puente.audit.worker.storage.add_record",
            new_callable=mock.AsyncMock,
        ) as mock_add:
            await worker._process_bucket({AuditDataTypes.LOGS: [b"e2"]})
        second_record = mock_add.call_args.args[1]

        expected_tsr_hash = hashlib.sha256(b"tsr").digest()
        chain = cbor2.loads(second_record.chain_cbor)
        assert chain["previous_tsr_hash"] == expected_tsr_hash

    async def test_process_bucket_with_none_tsr(
        self,
        worker: AuditWorker,
    ) -> None:
        with (
            mock.patch(
                "puente.audit.worker.pki.timestamp",
                new_callable=mock.AsyncMock,
                return_value=None,
            ),
            mock.patch(
                "puente.audit.worker.storage.add_record",
                new_callable=mock.AsyncMock,
            ) as mock_add,
        ):
            await worker._process_bucket({AuditDataTypes.LOGS: [b"e1"]})
        record = mock_add.call_args.args[1]
        assert record.tsr is None

        with (
            mock.patch(
                "puente.audit.worker.pki.timestamp",
                new_callable=mock.AsyncMock,
                return_value=None,
            ),
            mock.patch(
                "puente.audit.worker.storage.add_record",
                new_callable=mock.AsyncMock,
            ) as mock_add,
        ):
            await worker._process_bucket({AuditDataTypes.LOGS: [b"e2"]})
        record = mock_add.call_args.args[1]
        chain = cbor2.loads(record.chain_cbor)
        assert chain["previous_tsr_hash"] is None

    async def test_process_bucket_compresses_bucket(
        self,
        worker: AuditWorker,
    ) -> None:
        with mock.patch(
            "puente.audit.worker.storage.add_record",
            new_callable=mock.AsyncMock,
        ) as mock_add:
            await worker._process_bucket({AuditDataTypes.LOGS: [b"event1"]})
        record = mock_add.call_args.args[1]
        decompressed = zstd.decompress(record.bucket_zstd)
        bucket = cbor2.loads(decompressed)
        assert bucket[AuditDataTypes.LOGS] == [b"event1"]


class TestAuditWorkerFlushLoop:
    async def test_flush_loop_calls_process_bucket(
        self,
        worker: AuditWorker,
    ) -> None:
        worker.put(b"e1", AuditDataTypes.LOGS)
        with mock.patch.object(
            worker,
            "_process_bucket",
            new_callable=mock.AsyncMock,
        ) as mock_process:
            await _drain_flush_loop(worker)
        mock_process.assert_awaited_once()

    async def test_flush_loop_logs_empty_bucket(
        self,
        worker: AuditWorker,
    ) -> None:
        with (
            mock.patch("puente.audit.worker._logger") as mock_logger,
        ):
            await _drain_flush_loop(worker)
        mock_logger.debug.assert_called_once_with("audit_flush_empty")

    async def test_flush_loop_logs_process_bucket_error(
        self,
        worker: AuditWorker,
    ) -> None:
        worker.put(b"e1", AuditDataTypes.LOGS)
        with (
            mock.patch.object(
                worker,
                "_process_bucket",
                side_effect=RuntimeError("boom"),
            ),
            mock.patch("puente.audit.worker._logger") as mock_logger,
        ):
            await _drain_flush_loop(worker)
        mock_logger.exception.assert_called_once_with("audit_flush_error")


class TestAuditWorkerClose:
    async def test_close_closes_db(self, worker: AuditWorker) -> None:
        db = cast(mock.AsyncMock, await worker.get_db())
        await worker.close()
        db.close.assert_awaited_once()


class TestGetWorker:
    def test_returns_singleton(self) -> None:
        get_worker.cache_clear()
        w1 = get_worker()
        w2 = get_worker()
        assert w1 is w2
        get_worker.cache_clear()
