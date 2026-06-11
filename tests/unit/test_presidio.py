"""Unit tests for the Microsoft Presidio PII redaction adapters."""

import pytest

from puente.adapters.placeholders import DummyRedactionAdapter
from puente.adapters.presidio import PresidioAdapter

_FIELDS_PII = [
    (
        "Paciente: Juan Martínez López.",
        ["Juan", "Martínez", "López"],
    ),
    (
        "El paciente se llama Carlos, con DNI 23923401C. Vive en Ponferrada.",
        ["Carlos", "23923401C", "Ponferrada"],
    ),
    *[
        (f"El dato relevante: {i}.", [i])
        for i in [
            "12345678Z",
            "diaz.esparza@proton.me",
            "marina.dader.suarez@gmail.com",
            "X1234567L",
            "Z3986854Q",
        ]
    ],
]

_STRINGS_MEDICAL = [
    "Se realizó artroscopia de rodilla derecha con resección de "
    + "menisco medial roto. Procedimiento sin incidencias.",
    "El paciente recibió una concusión hace 2 semanas, no se ven secuelas. "
    + "Se recomienda seguimiento.",
]

_STRINGS_COMMON = [
    "Ha habido un incidente en la oficina.",
    "\r\nLa oveja camina por el monte.\n",
    "",
    # We want to preserve dates and times for health diagnoses
    "Hoy es día 15 de agosto de 2025",
    "Los sucesos ocurrieron el 12/10/18.",
    "Los sucesos ocurrieron el 12/10/2018.",
]


class TestDummyRedactionAdapter:
    """Identity pass-through adapter tests."""

    @pytest.mark.parametrize("text", _STRINGS_MEDICAL + _STRINGS_COMMON)
    def test_returns_same_text(self, text: str) -> None:
        adapter = DummyRedactionAdapter()
        assert text == adapter.redact(text)


class TestPresidioAdapterWithRealEngine:
    """Tests utilizing the real Presidio adapter."""

    # Mitigates creation overhead
    @pytest.fixture(scope="class")
    def adapter(self) -> PresidioAdapter:
        return PresidioAdapter()

    @pytest.mark.parametrize("contents", _FIELDS_PII)
    def test_redacts_pii(
        self,
        contents: tuple[str, list[str]],
        adapter: PresidioAdapter,
    ) -> None:
        text, keywords = contents
        result = adapter.redact(text)
        for word in keywords:
            assert word not in result

    @pytest.mark.parametrize("text", _STRINGS_MEDICAL + _STRINGS_COMMON)
    def test_redact_handles_text_without_pii(
        self,
        text: str,
        adapter: PresidioAdapter,
    ) -> None:
        assert text == adapter.redact(text)
