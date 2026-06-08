from typing import override

import httpx

from puente.config import get_settings
from puente.domain.ports import ReportHumanizationPort
from puente.telemetry.getters import get_logger
from puente.telemetry.timer import Timer

_logger = get_logger(__name__)


class RecogAdapter(ReportHumanizationPort):
    def __init__(self) -> None:
        settings = get_settings()

        self.__client = httpx.AsyncClient(timeout=settings.recog_timeout_s)
        self.__url = settings.recog_url
        self.__api_key = settings.recog_api_key

    @override
    async def humanize(self, report: str) -> bytes:
        _logger.info("recog_request", report_length=len(report))
        with Timer() as timer:
            response = (
                await self.__client.post(
                    self.__url,
                    headers={"X-API-Key": self.__api_key.get_secret_value()},
                    json={"dictationReport": report},
                )
            ).raise_for_status()
            result = await response.aread()
        _logger.info(
            "recog_response",
            response_size=len(result),
            endpoint_duration_ms=timer.duration_ms,
        )
        return result
