import asyncio

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from puente.bootstrap import create_pipeline
from puente.cli.mocks import create_demo_dicom, create_demo_report_pdf
from puente.config import get_settings
from puente.domain.models import DicomStudy, MedicalRecordUpload

app = typer.Typer(help="Puente Idonia-Recog CLI")
console = Console()


@app.command()
def version() -> None:
    """Show version and exit."""
    settings = get_settings()
    console.print(f"Puente Idonia-Recog {settings.version}")


@app.command()
def demo() -> None:
    """Run an end-to-end demo of the Idonia-Recog bridge."""
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

    study = DicomStudy(
        patient_id="12345678A",
        accession_number="MRI-2024-009",
        study_description="Rodilla_Derecha_PostOp",
    )

    console.print(
        "\n[bold]Paciente:[/bold] Juan Martínez López "
        + f"([dim]{study.patient_id}[/dim])",
    )
    console.print(f"[bold]Estudio:[/bold] {study.study_description}")
    console.print(f"[bold]Accession:[/bold] {study.accession_number}")

    async def _run() -> None:
        with console.status("[bold green]Generando documentos..."):
            report_pdf = create_demo_report_pdf()
            dicom_file = create_demo_dicom()

        record = MedicalRecordUpload(
            study=study,
            report_file=report_pdf,
            dicom_file=dicom_file,
        )

        console.print(
            "\n[bold]Fase I[/bold]  — Ingesta "
            + "[dim](subida de DICOM e informe)[/dim]",
        )
        console.print(
            "[bold]Fase II[/bold] — Humanización [dim](Recog AI)[/dim]",
        )
        console.print(
            "[bold]Fase III[/bold] — Entrega [dim](magic link)[/dim]\n",
        )

        pipeline = create_pipeline()

        with console.status(
            "[bold green]Ejecutando pipeline extremo a extremo...",
        ):
            magic_link = await pipeline.run(record)

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

    try:
        asyncio.run(_run())
    except Exception as e:
        console.print(f"\n[bold red]Pipeline failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def serve() -> None:
    """Run the Puente API server."""
    settings = get_settings()
    uvicorn.run(
        "puente.api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
    )
