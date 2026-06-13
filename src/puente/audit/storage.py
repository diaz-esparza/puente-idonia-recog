import aiosqlite

from puente.config import get_settings
from puente.domain.models import AuditRecord
from puente.telemetry.getters import get_logger

_logger = get_logger(__name__)

async def setup() -> aiosqlite.Connection:
    settings = get_settings()
    db = aiosqlite.connect(settings.audit_sqlite_file)
    _ = await db.execute("""
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY,
            chain_cbor BLOB NOT NULL,
            signature BLOB NOT NULL,
            tsr BLOB,
            bucket_zstd BLOB NOT NULL
        )
    """)
    await db.commit()
    _logger.info("db_setup")
    return db


async def add_record(db: aiosqlite.Connection, record: AuditRecord) -> None:
    _ = await db.execute(
        """
            INSERT INTO audit (
                chain_cbor,
                signature,
                tsr,
                bucket_zstd
            ) VALUES (?, ?, ?, ?)
        """,
        record.chain_cbor,
        record.signature,
        record.tsr,
        record.bucket_zstd,
    )
    await db.commit()
    _logger.info("db_insert")
