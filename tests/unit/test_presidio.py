"""Unit tests for the Microsoft Presidio PII redaction adapters."""

import pytest

from puente.adapters.placeholders import DummyRedactionAdapter
from puente.adapters.presidio import PresidioAdapter
from puente.cli.presidio_samples import (
    COMMON_STRINGS,
    MEDICAL_STRINGS,
    get_pii_fields_for_tests,
)


class TestDummyRedactionAdapter:
    """Identity pass-through adapter tests."""

    @pytest.mark.parametrize("text", MEDICAL_STRINGS + COMMON_STRINGS)
    def test_returns_same_text(self, text: str) -> None:
        adapter = DummyRedactionAdapter()
        assert text == adapter.redact(text)


class TestPresidioAdapterWithRealEngine:
    """Tests utilizing the real Presidio adapter."""

    @pytest.fixture(scope="class")
    def adapter(self) -> PresidioAdapter:
        return PresidioAdapter()

    @pytest.mark.parametrize("contents", get_pii_fields_for_tests())
    def test_redacts_pii(
        self,
        contents: tuple[str, list[str]],
        adapter: PresidioAdapter,
    ) -> None:
        text, keywords = contents
        result = adapter.redact(text)
        for word in keywords:
            assert word not in result

    @pytest.mark.parametrize("text", MEDICAL_STRINGS + COMMON_STRINGS)
    def test_redact_handles_text_without_pii(
        self,
        text: str,
        adapter: PresidioAdapter,
    ) -> None:
        assert text == adapter.redact(text)
