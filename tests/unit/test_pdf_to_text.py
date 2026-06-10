"""Unit tests for the PDF-to-text conversion adapter."""

from puente.adapters.pdf_to_txt import PymupdfAdapter
from tests.support.data import build_multipage_pdf, build_simple_pdf


class TestPymupdfAdapter:
    """Tests for the PDF-to-text conversion adapter."""

    def test_convert_extracts_text_from_pdf(self) -> None:
        pdf = build_simple_pdf("Hello from the PDF.")
        adapter = PymupdfAdapter()
        text = adapter.convert(pdf)
        assert "Hello from the PDF." in text

    def test_convert_empty_pdf_returns_empty_string(self) -> None:
        pdf = build_simple_pdf("")
        adapter = PymupdfAdapter()
        text = adapter.convert(pdf)
        assert text == ""

    def test_convert_multipage_pdf_concatenates_text(self) -> None:
        pdf = build_multipage_pdf()
        adapter = PymupdfAdapter()
        text = adapter.convert(pdf)
        assert "Page one." in text
        assert "Page two." in text
