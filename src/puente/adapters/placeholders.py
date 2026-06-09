# pyright: reportUnknownMemberType=false
"""Placeholders to be properly implemented later."""

from typing import override

import pymupdf

from puente.domain.ports import ReportHumanizationPort

from puente.telemetry.getters import get_logger

_logger = get_logger(__name__)


class DummyHumanizationAdapter(ReportHumanizationPort):
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
        _logger.warning("mock_humanization")
        return document.tobytes()
