from fastapi import FastAPI

from puente.config import get_settings

from . import v1
from .lifespan import lifespan

app = FastAPI(
    title="Puente Audit",
    version=get_settings().version,
    lifespan=lifespan,
)

app.include_router(v1.router)
