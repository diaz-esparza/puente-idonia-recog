"""Puente CLI entry point."""

import asyncio

import typer
import uvicorn
from rich.console import Console

from puente.config import get_settings

from .client import DemoClient
from .demo import main as demo_main

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
        reload=settings.app_reload,
    )


@app.command()
def healthcheck() -> None:
    """Run the health check probe against the API server."""
    try:
        client = DemoClient()
        asyncio.run(client.healthcheck())
    except Exception:
        raise typer.Exit(code=1) from None
