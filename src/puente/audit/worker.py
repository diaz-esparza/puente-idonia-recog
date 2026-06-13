import asyncio
from collections import defaultdict
from compression import zstd
from enum import StrEnum, auto
from functools import lru_cache
from hashlib import sha256

import aiosqlite

from puente.config import get_settings
from puente.domain.models import AuditChain, AuditRecord
from puente.telemetry.getters import get_logger

from . import pki, storage

_logger = get_logger(__name__)


class AuditDataTypes(StrEnum):
    LOGS = auto()
    TRACES = auto()


type BucketType = dict[AuditDataTypes, list[bytes]]


class AuditWorker:
    _db: aiosqlite.Connection | None = None

    def __init__(self) -> None:
        settings = get_settings()
        self.__flush_interval_s = settings.audit_flush_interval_s
        self.__bucket: BucketType = defaultdict(list)
        self.__previous_chain_hash: bytes | None = None
        self.__previous_tsr_hash: bytes | None = None
        self.__sequence = 0

    def put(self, event: bytes, data_type: AuditDataTypes) -> None:
        self.__bucket[data_type].append(event)

    async def get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await storage.setup()
        return self._db

    async def flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self.__flush_interval_s)
            old_bucket = self.__bucket

            if old_bucket:
                self.__bucket = defaultdict(list)
                try:
                    await self._process_bucket(old_bucket)
                    _logger.debug(
                        "audit_flush",
                        **{
                            f"{data_type.lower()}_count": len(data)
                            for data_type, data in old_bucket.items()
                        },
                    )
                except Exception:
                    _logger.exception("audit_flush_error")
                    # Restore failed bucket events to the front of the bucket
                    for data_type, events in old_bucket.items():
                        self.__bucket[data_type] = (
                            events + self.__bucket[data_type]
                        )
            else:
                _logger.debug("audit_flush_empty")

    async def _process_bucket(self, bucket: BucketType) -> None:
        bucket_bytes = pki.to_canonical_bin(bucket)
        chain = AuditChain(
            sequence=self.__sequence,
            previous_chain_hash=self.__previous_chain_hash,
            previous_tsr_hash=self.__previous_tsr_hash,
            bucket_hash=sha256(bucket_bytes).digest(),
        )
        chain_cbor = pki.to_canonical_bin(chain.model_dump())
        signature = pki.keygen().sign(chain_cbor)
        tsr = await pki.timestamp(signature)
        record = AuditRecord(
            chain_cbor=chain_cbor,
            signature=signature,
            tsr=tsr,
            bucket_zstd=zstd.compress(bucket_bytes),
        )
        await storage.add_record(await self.get_db(), record)
        self.__previous_chain_hash = sha256(chain_cbor).digest()
        self.__previous_tsr_hash = (
            sha256(tsr).digest() if tsr is not None else None
        )
        self.__sequence += 1

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None


@lru_cache(maxsize=1)
def get_worker() -> AuditWorker:
    return AuditWorker()
