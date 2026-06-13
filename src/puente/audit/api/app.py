from fastapi import FastAPI

from puente.config import get_settings
from puente.telemetry.setup import configure_logging

from . import v1
from .lifespan import lifespan

configure_logging()
app = FastAPI(
    title="Puente Audit",
    version=get_settings().version,
    lifespan=lifespan,
)

app.include_router(v1.router)
