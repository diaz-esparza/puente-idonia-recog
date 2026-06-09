import logging
import sys
from typing import Any

import orjson
import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from structlog.types import EventDict

from puente.config import get_settings


def _json_dumps(value: Any, **_: Any) -> str:
    return orjson.dumps(value).decode("utf-8")


def _add_otel_trace_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Adds trace ID to every log. We inject it via `configure_logging`."""
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if span_context and span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
        event_dict["trace_flags"] = int(span_context.trace_flags)
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    log_level = settings.otel_log_level
    service_name = settings.otel_service_name
    environment = settings.otel_environment

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_otel_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(serializer=_json_dumps),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    otel_endpoint = settings.otel_endpoint
    if otel_endpoint is not None:
        log_resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": settings.version,
                "deployment.environment": environment,
            }
        )
        log_provider = LoggerProvider(resource=log_resource)
        log_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(
                    endpoint=otel_endpoint,
                    insecure=settings.otel_connect_insecurely,
                )
            )
        )
        root_logger.addHandler(
            LoggingHandler(logger_provider=log_provider)
        )

    _ = structlog.contextvars.bind_contextvars(
        service=service_name,
        environment=environment,
    )


def configure_tracing() -> None:
    settings = get_settings()
    service_name = settings.otel_service_name
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": settings.version,
            "deployment.environment": settings.otel_environment,
        }
    )
    provider = TracerProvider(resource=resource)
    endpoint = settings.otel_endpoint
    if endpoint is None:
        exporter = ConsoleSpanExporter(service_name=service_name)
    else:
        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=settings.otel_connect_insecurely,
        )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
