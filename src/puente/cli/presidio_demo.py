"""Standalone Presidio PII redaction showcase."""

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from puente.adapters.presidio import PresidioAdapter
from puente.config import get_settings
from puente.telemetry.setup import configure_noop_logging

from .mocks import DEMO_REPORT_TEXT
from .presidio_samples import MEDICAL_LABELS, get_pii_samples_for_demo


def _print_banner(console: Console) -> None:
    settings = get_settings()
    console.print(
        Panel.fit(
            "[bold cyan]Puente Idonia-Recog[/bold cyan] "
            + f"[bold yellow]v{settings.version}[/bold yellow] "
            + "[bold cyan]PRESIDIO[/bold cyan]\n"
            + "[dim]Microsoft Presidio — anonimización de datos "
            + "personales en texto clínico en español.[/dim]\n"
            + "[bold]Operador:[/bold] "
            + f"{settings.presidio_anonymizer_operator} "
            + f"[dim]({settings.presidio_config_file})[/dim]",
            title="[bold green]Demo[/bold green]",
            border_style="green",
        ),
    )


def _build_pii_table(
    rows: list[tuple[str, str, str]],
) -> Table:
    table = Table(
        title="[bold]Supresión de datos personales (PII)[/bold]",
        show_header=True,
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold",
    )
    table.add_column("Tipo", style="dim", width=12)
    table.add_column("Original", style="white")
    table.add_column("Anonimizado", style="cyan")
    for label, original, redacted in rows:
        table.add_row(label, original, redacted)
    return table


def main(console: Console) -> None:
    configure_noop_logging()
    _print_banner(console)
    try:
        adapter = PresidioAdapter()
    except Exception as exc:
        console.print(
            f"\n[bold red]Error inicializando Presidio:[/bold red] {exc}"
        )
        raise typer.Exit(code=1) from exc

    pii_rows: list[tuple[str, str, str]] = []
    for label, text in get_pii_samples_for_demo():
        pii_rows.append((label, text, adapter.redact(text)))
    pii_rows.append(
        ("Informe demo", DEMO_REPORT_TEXT, adapter.redact(DEMO_REPORT_TEXT))
    )

    console.print()
    console.print(_build_pii_table(pii_rows))

    unchanged = 0
    medical_table = Table(
        title="[bold]Verificación de texto sin PII[/bold]",
        show_header=True,
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold",
    )
    medical_table.add_column("Tipo", style="dim", width=12)
    medical_table.add_column("Texto", style="white")
    medical_table.add_column("Resultado", style="cyan", width=20)
    for label, text in MEDICAL_LABELS:
        result = adapter.redact(text)
        status = (
            "[bold green]Sin cambios[/bold green]"
            if text == result
            else "[bold red]Modificado[/bold red]"
        )
        medical_table.add_row(label, text, status)
        if text == result:
            unchanged += 1

    console.print()
    console.print(medical_table)

    console.print(
        "\n[bold green]Presidio demo completada.[/bold green] "
        + f"[dim]{unchanged}/{len(MEDICAL_LABELS)} textos médicos "
        + "sin modificar.[/dim]\n"
    )
