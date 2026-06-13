# pyright: reportUnknownVariableType=false
"""CLI de inspección de auditoría — lector offline de SQLite
con verificación de cadena.
"""

import asyncio
from compression import zstd
from hashlib import sha256
from typing import cast

import aiosqlite
import cbor2
from cryptography.exceptions import InvalidSignature as _CryptoInvalidSig
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from puente.audit import pki
from puente.audit.worker import BucketType
from puente.config import get_settings
from puente.domain.models import AuditChain, AuditRecord


def _print_banner(console: Console) -> None:
    settings = get_settings()
    console.print(
        Panel.fit(
            "[bold cyan]Puente Idonia-Recog[/bold cyan] "
            + f"[bold yellow]v{settings.version}[/bold yellow] "
            + f"[bold cyan]AUDIT[/bold cyan]\n"
            + "[dim]¡Todo por un pasaje seguro por las montañas![/dim]",
            title="[bold green]Demo[/bold green]",
            border_style="green",
        ),
    )


async def _count_entries(db: aiosqlite.Connection) -> int:
    cursor = await db.execute("SELECT COUNT(*) FROM audit")
    row = await cursor.fetchone()
    return row[0] if row else 0


async def _fetch_record(
    db: aiosqlite.Connection,
    row_id: int,
) -> AuditRecord | None:
    cursor = await db.execute(
        """
            SELECT id, chain_cbor, signature, tsr, bucket_zstd
            FROM audit WHERE id = ?
        """,
        (row_id,),
    )
    all_rows = await cursor.fetchall()
    try:
        row = next(iter(all_rows))
        return AuditRecord(
            chain_cbor=row[1],
            signature=row[2],
            tsr=row[3],
            bucket_zstd=row[4],
        )
    except StopIteration:
        return None


async def _fetch_all_chain_cbors(
    db: aiosqlite.Connection,
) -> list[tuple[int, bytes]]:
    cursor = await db.execute("SELECT id, chain_cbor FROM audit ORDER BY id")
    return [(row[0], cast(bytes, row[1])) for row in await cursor.fetchall()]


def _verify_signature(record: AuditRecord) -> tuple[bool, str]:
    try:
        public_key = pki.keygen().public_key()
        public_key.verify(record.signature, record.chain_cbor)
        return True, ""
    except _CryptoInvalidSig:
        return False, "Clave inválida"
    except Exception as e:
        return False, f"Error: {e}"


def _format_hash(data: bytes | None) -> str:
    if data is None:
        return "Sin hash (inicio de la cadena)"
    return data.hex()


def _get_chain(record: AuditRecord) -> AuditChain:
    return AuditChain.model_validate(cbor2.loads(record.chain_cbor))


def _render_chain_panel(
    row_id: int,
    record: AuditRecord,
    console: Console,
) -> None:
    chain_data = _get_chain(record)
    chain = AuditChain.model_validate(chain_data)

    chain_table = Table(
        title=f"Registro de cadena #{row_id}",
        show_header=False,
        title_style="bold",
    )
    chain_table.add_column("Campo", style="cyan")
    chain_table.add_column("Valor")
    chain_table.add_row("Versión", str(chain.version))
    chain_table.add_row("Secuencia (0-inclusive)", str(chain.sequence))
    chain_table.add_row("Marca temporal", chain.ts.isoformat())
    chain_table.add_row("Hash del bucket", chain.bucket_hash.hex())
    chain_table.add_row(
        "Hash de cadena anterior", _format_hash(chain.previous_chain_hash)
    )
    chain_table.add_row(
        "Hash de TSR anterior", _format_hash(chain.previous_tsr_hash)
    )
    chain_table.add_row(
        "Tamaño CBOR de cadena", f"{len(record.chain_cbor)} bytes"
    )
    console.print(chain_table)


def _render_signature_panel(record: AuditRecord, console: Console) -> None:

    is_valid, detail = _verify_signature(record)

    status = Text()
    if is_valid:
        _ = status.append("VÁLIDA", style="bold green")
    else:
        _ = status.append("NO VÁLIDA", style="bold red")
        _ = status.append(detail, style="red")

    sig_table = Table(title="Firma", show_header=False, title_style="bold")
    sig_table.add_column("Campo", style="cyan")
    sig_table.add_column("Valor")
    sig_table.add_row("Tamaño", f"{len(record.signature)} bytes")
    sig_table.add_row("Estado", status)
    console.print(sig_table)


def _render_tsr_panel(tsr: bytes | None, console: Console) -> None:
    tsr_table = Table(
        title="Respuesta de marca temporal (TSR)",
        show_header=False,
        title_style="bold",
    )
    tsr_table.add_column("Campo", style="cyan")
    tsr_table.add_column("Valor")
    if tsr is not None:
        tsr_table.add_row("Tamaño", f"{len(bytes(tsr))} bytes")
        tsr_table.add_row("Presente", "Sí")
    else:
        tsr_table.add_row(
            "Presente", "No (TSA no disponible en el momento de volcado)"
        )
    console.print(tsr_table)


def _render_bucket_panel(bucket_zstd: bytes, console: Console) -> None:
    bucket_table = Table(
        title="Contenido del bucket",
        show_header=False,
        title_style="bold",
    )
    bucket_table.add_column("Campo", style="cyan")
    bucket_table.add_column("Valor")
    bucket_raw = zstd.decompress(bucket_zstd)

    bucket_table.add_row("Tamaño comprimido", f"{len(bucket_zstd)} bytes")
    bucket_table.add_row("Tamaño descomprimido", f"{len(bucket_raw)} bytes")
    bucket = cast(BucketType, cbor2.loads(bucket_raw))

    keys = [str(k) for k in bucket]
    bucket_table.add_row("Tipos de datos", ", ".join(keys))
    for key, events in bucket.items():
        total = sum(len(e) for e in events)
        bucket_table.add_row(f"  {key} eventos", str(len(events)))
        bucket_table.add_row(f"  {key} bytes totales", str(total))

    console.print(bucket_table)


def _render_chain_link_panel(
    chain: AuditChain,
    prev_chain_cbor: bytes | None,
    row_id: int,
    console: Console,
) -> None:
    link_table = Table(
        title="Verificación de enlace de cadena",
        show_header=False,
        title_style="bold",
    )
    link_table.add_column("Comprobación", style="cyan")
    link_table.add_column("Resultado")

    if prev_chain_cbor is None:
        chain_link = f"Registro #{row_id}"
        verdict = "[green]sin registro previo[/green]"
    else:
        chain_link = f"#{row_id - 1} -> #{row_id}"
        if chain.previous_chain_hash is None:
            verdict = (
                "[yellow]cadena reiniciada: existe registro previo pero"
                + " no está enlazado[/yellow]"
            )
        else:
            expected = sha256(prev_chain_cbor).digest()
            verdict = (
                "[green]enlace de cadena válido[/green]"
                if chain.previous_chain_hash == expected
                else "[red]roto: los hashes no coinciden[/red]"
            )
    link_table.add_row(chain_link, verdict)
    console.print(link_table)


def _build_chains(
    rows: list[tuple[int, bytes]],
) -> list[list[tuple[int, bytes, AuditChain]]]:
    chains: list[list[tuple[int, bytes, AuditChain]]] = []
    current: list[tuple[int, bytes, AuditChain]] = []

    for row_id, chain_cbor in rows:
        chain = AuditChain.model_validate(cbor2.loads(chain_cbor))
        if current:
            _, prev_cbor, _ = current[-1]
            prev_hash = sha256(prev_cbor).digest()
            if chain.previous_chain_hash == prev_hash:
                current.append((row_id, chain_cbor, chain))
            else:
                chains.append(current)
                current = [(row_id, chain_cbor, chain)]
        else:
            current.append((row_id, chain_cbor, chain))

    if current:
        chains.append(current)
    return chains


def _render_chains_summary(
    chains: list[list[tuple[int, bytes, AuditChain]]],
    console: Console,
) -> None:
    summary = Table(title="Cadenas detectadas", title_style="bold")
    summary.add_column("#", style="cyan")
    summary.add_column("Registros", justify="center")
    summary.add_column("Longitud", justify="right")
    summary.add_column("Rango temporal", justify="center")

    for i, chain_records in enumerate(chains, 1):
        first_id = chain_records[0][0]
        last_id = chain_records[-1][0]
        length = len(chain_records)
        first_ts = chain_records[0][2].ts.isoformat()
        last_ts = chain_records[-1][2].ts.isoformat()
        range_str = first_ts if length == 1 else f"{first_ts}\n  -> {last_ts}"
        summary.add_row(
            str(i),
            f"#{first_id} - #{last_id}",
            str(length),
            range_str,
        )
    console.print(summary)


async def _inspect(console: Console) -> None:
    _print_banner(console)

    settings = get_settings()
    db_path = settings.audit_sqlite_file

    async with aiosqlite.connect(db_path) as db:
        total = await _count_entries(db)
        console.print(f"\n[bold]Entradas de auditoría totales:[/bold] {total}")

        if total == 0:
            console.print(
                "\n[yellow]No hay registros en la base de datos.[/yellow]\n"
            )
            return

        all_rows = await _fetch_all_chain_cbors(db)
        chains = _build_chains(all_rows)
        console.print()
        _render_chains_summary(chains, console)

        last_chain = chains[-1]
        row_id = last_chain[-1][0]

        console.print(
            "\n[bold]Inspeccionando último registro de la cadena"
            + f" {len(chains)} (#{row_id}):[/bold]\n"
        )

        last_record = await _fetch_record(db, row_id)
        if last_record is None:
            raise ValueError("Valor de registro inesperado de la BD")

        _render_chain_panel(row_id, last_record, console)
        _render_signature_panel(last_record, console)
        _render_tsr_panel(last_record.tsr, console)
        _render_bucket_panel(last_record.bucket_zstd, console)

        prev_record = await _fetch_record(db, row_id - 1)
        prev_chain_cbor: bytes | None = (
            prev_record.chain_cbor if prev_record is not None else None
        )

        _render_chain_link_panel(
            _get_chain(last_record),
            prev_chain_cbor,
            row_id,
            console,
        )
        console.print()


def main(console: Console) -> None:
    """Inspecciona el registro de auditoría más reciente
    directamente desde la base de datos SQLite.

    Imprime cadenas de hash contiguas y realiza la verificación
    completa del último registro en la última cadena.
    """
    asyncio.run(_inspect(console))
