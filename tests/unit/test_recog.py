"""Unit tests for the Recog AI humanization adapter."""

import httpx
import orjson
import pytest
import respx

from puente.adapters.recog import RecogAdapter
from puente.config import Settings


class TestRecogAdapterHappy:
    """Basic tests for the Recog AI humanization adapter."""

    async def test_humanize_sends_correct_payload(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        route = respx_mock.post(settings.recog_url).respond(
            200, content=b"pdf-bytes"
        )

        adapter = RecogAdapter()
        result = await adapter.humanize("clinical text")

        assert result == b"pdf-bytes"
        request = route.calls.last.request
        assert request.headers["x-api-key"] == "test-recog-key"
        body = orjson.loads(request.content)
        assert body["dictationReport"] == "clinical text"


class TestRecogAdapterError:
    """Error management tests for the Recog AI humanization adapter."""

    async def test_humanize_raises_on_http_error(
        self, respx_mock: respx.MockRouter, settings: Settings
    ) -> None:
        _ = respx_mock.post(settings.recog_url).respond(500)

        adapter = RecogAdapter()
        with pytest.raises(httpx.HTTPStatusError):
            _ = await adapter.humanize("clinical text")
