"""Demo implementation."""

import asyncio

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from puente.config import get_settings
from puente.domain.models import DicomStudy, MagicLink, MedicalRecordUpload

from .client import DemoClient
from .mocks import build_demo_record


def _print_banner(console: Console) -> None:
    settings = get_settings()
    console.print(
        Panel.fit(
            "[bold cyan]Puente Idonia-Recog[/bold cyan] "
            + f"[bold yellow]v{settings.version}[/bold yellow]\n"
            + "[dim]Cuando los Picos de Europa separan al paciente de su "
            + "historia clínica, los datos deben cruzar la montaña antes que "
            + "él.[/dim]",
            title="[bold green]Demo[/bold green]",
            border_style="green",
        ),
    )


def _print_patient_info(console: Console, study: DicomStudy) -> None:
    console.print(
        "\n[bold]Paciente:[/bold] Juan Martínez López "
        + f"([dim]{study.patient_id}[/dim])",
    )
    console.print(f"[bold]Estudio:[/bold] {study.study_description}")
    console.print(f"[bold]Accession:[/bold] {study.accession_number}")


def _print_phases(console: Console) -> None:
    settings = get_settings()
    console.print(
        "\n[bold]Fase I[/bold]  — Ingesta [dim](subida de DICOM e informe)"
        + "[/dim]",
    )
    console.print(
        "[bold]Fase II[/bold] — Humanización "
        + f"[dim]({settings.humanized_provider})[/dim]",
    )
    console.print(
        "[bold]Fase III[/bold] — Entrega [dim](magic link)[/dim]\n",
    )


def _print_result(console: Console, magic_link: MagicLink) -> None:
    settings = get_settings()
    table = Table(show_header=False, box=None)
    table.add_row("URL", f"{settings.idonia_output_url}/{magic_link.url}")
    table.add_row("PIN", f"[bold]{magic_link.pin}[/bold]")

    console.print(
        Panel(
            table,
            title="[bold]Magic Link[/bold]",
            border_style="green",
        ),
    )
    console.print(
        "\n[bold green]Demo completada.[/bold green] "
        + "Visor disponible en la URL de arriba.",
    )


async def _run_api(
    console: Console,
    record: MedicalRecordUpload,
) -> MagicLink:
    async with DemoClient() as client:
        with console.status(
            f"[bold yellow]Buscando servidor en {client.host}...",
        ):
            await client.healthcheck()
        console.print(
            f"[bold cyan]Servidor detectado[/bold cyan] en {client.host}."
        )
        with console.status(
            "[bold green]Enviando registro, humanizando informe y "
            + "recibiendo el magic link...",
        ):
            return await client.run_pipeline(record)


def main(console: Console) -> None:
    _print_banner(console)

    with console.status("[bold green]Generando documentos de prueba..."):
        record = build_demo_record()

    _print_patient_info(console, record.study)
    _print_phases(console)
    record = build_demo_record()

    try:
        magic_link = asyncio.run(_run_api(console, record))
    except httpx.HTTPStatusError as exc:
        console.print(
            "\n[bold red]Error de la API:[/bold red] "
            + f"{exc.response.status_code}: {exc.response.text}",
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"\n[bold red]Error genérico:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_result(console, magic_link)
