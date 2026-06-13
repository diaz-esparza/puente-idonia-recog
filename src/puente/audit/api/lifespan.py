import asyncio
import contextlib
from typing import Annotated

from fastapi import Depends, FastAPI

from puente.telemetry.getters import get_logger

from ..worker import AuditWorker, get_worker

type DepWorker = Annotated[AuditWorker, Depends(get_worker)]

_logger = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    worker = get_worker()
    worker_task = asyncio.create_task(worker.flush_loop())
    _logger.info("worker_started")
    yield
    _ = worker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker_task
    await worker.close()
