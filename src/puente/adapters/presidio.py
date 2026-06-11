from typing import cast, override

from opentelemetry import trace
from presidio_analyzer import AnalyzerEngine, AnalyzerEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import (
    OperatorConfig,
)
from presidio_anonymizer.entities import (
    RecognizerResult as AnonymizerRecognizerResult,
)

from puente.config import get_settings
from puente.domain.ports import PiiRedactionPort
from puente.telemetry.getters import get_logger
from puente.telemetry.timer import Timer

_logger = get_logger(__name__)
_tracer = trace.get_tracer(__name__)


class PresidioAdapter(PiiRedactionPort):
    """PII de-identification via Microsoft Presidio.

    Runs locally with no outbound HTTP calls.  Engines are lazy-
    initialised on first request because the spaCy model may be
    downloaded on the first invocation.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.__operator: str = settings.presidio_anonymizer_operator
        self.__analyzer: AnalyzerEngine | None = None
        self.__anonymizer: AnonymizerEngine | None = None

    def _ensure_engines(self) -> tuple[AnalyzerEngine, AnonymizerEngine]:

        if self.__analyzer is None or self.__anonymizer is None:
            settings = get_settings()
            # NOTE: Next release of microsoft/presidio (>2.2.362) will allow us
            # to filter rules by country. Would be useful to add that option.
            # See: https://github.com/microsoft/presidio/blob/main/docs/analyzer/filtering_by_country.md
            self.__analyzer = AnalyzerEngineProvider(
                analyzer_engine_conf_file=settings.presidio_config_file
            ).create_engine()
            self.__anonymizer = AnonymizerEngine()
            _logger.info("presidio_lazy_init")
        return self.__analyzer, self.__anonymizer

    @override
    def redact(self, text: str) -> str:
        span = trace.get_current_span()
        _logger.info("presidio_request", original_length=len(text))

        try:
            analyzer, anonymizer = self._ensure_engines()
        except Exception:
            _logger.exception("presidio_engine_init_failed")
            raise

        with Timer() as timer_analyze:
            results = analyzer.analyze(
                text=text,
                language="es",
            )
        # casted because presidio_anonymizer and presidio_analyzer have
        # equivalent, but different classes
        results = cast(list[AnonymizerRecognizerResult], results)

        pii_count = len(results)
        span.set_attribute("presidio.pii_count", pii_count)

        if pii_count > 0:
            with Timer() as timer_anonymize:
                anonymized = anonymizer.anonymize(
                    text=text,
                    analyzer_results=results,
                    operators={"DEFAULT": OperatorConfig(self.__operator)},
                )

            result = anonymized.text
            anonymize_duration_ms = timer_anonymize.duration_ms
        else:
            result = text
            anonymize_duration_ms = None

        _logger.info(
            "presidio_response",
            redacted_length=len(result),
            analyze_duration_ms=timer_analyze.duration_ms,
            anonymize_duration_ms=anonymize_duration_ms,
        )
        return result
