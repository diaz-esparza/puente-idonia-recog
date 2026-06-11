# pyright: reportMissingTypeStubs=false

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from puente.config import get_settings
from puente.telemetry.setup import configure_logging, configure_tracing

from . import v1

configure_logging()
configure_tracing()
app = FastAPI(title="Puente Idonia-Recog", version=get_settings().version)

FastAPIInstrumentor.instrument_app(app)

app.include_router(v1.router)
