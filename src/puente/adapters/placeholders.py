# pyright: reportUnknownMemberType=false
"""Placeholders to be properly implemented later."""

from typing import override

import pymupdf

from puente.domain.ports import PiiRedactionPort, ReportHumanizationPort
from puente.telemetry.getters import get_logger

_logger = get_logger(__name__)


class DummyRedactionAdapter(PiiRedactionPort):
    """Identity pass-through that logs a warning.

    Not for use in production, as all PII goes through unmodified.
    """

    @override
    def redact(self, text: str) -> str:
        _logger.warning("dummy_redaction", text_length=len(text))
        return text


class DummyHumanizationAdapter(ReportHumanizationPort):
    """Dummy adapter that converts to pdf and logs a warning.

    Not for use in production.
    """

    @override
    async def humanize(self, report: str) -> bytes:
        document = pymupdf.open()
        page = document.new_page()
        report += (
            "\n" * 2
            + "Este no es un informe generado por IA, "
            + "sino un parche temporal para pruebas"
        )
        _ = page.insert_text((72, 72), report, fontsize=12)
        _logger.warning("dummy_humanization")
        return document.tobytes()
