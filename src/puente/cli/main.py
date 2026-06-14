"""Puente CLI entry point."""

import asyncio

import typer
import uvicorn
from rich.console import Console

from puente.config import get_settings

from .audit import main as audit_inspect_main
from .client import DemoClient
from .demo import main as demo_main
from .presidio_demo import main as presidio_demo_main

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
    demo_main(console)


@app.command()
def serve() -> None:
    """Run the Puente API server."""
    settings = get_settings()
    uvicorn.run(
        "puente.api.app:app",
        host=settings.app_host,
        port=settings.app_port,
    )


async def _async_healthcheck():
    async with DemoClient() as client:
        await client.healthcheck()


@app.command()
def serve_audit() -> None:
    """Run the Puente Audit REST server."""
    settings = get_settings()
    uvicorn.run(
        "puente.audit.api.app:app",
        host=settings.audit_app_host,
        port=settings.audit_app_port,
    )


@app.command()
def healthcheck() -> None:
    """Run the health check probe against the API server."""
    try:
        asyncio.run(_async_healthcheck())
    except Exception:
        raise typer.Exit(code=1) from None


@app.command()
def audit_inspect() -> None:
    """Inspect audit records — count entries, verify chain, show details."""
    audit_inspect_main(console)


@app.command()
def presidio_demo() -> None:
    """Run a standalone showcase of Presidio PII redaction."""
    presidio_demo_main(console)
