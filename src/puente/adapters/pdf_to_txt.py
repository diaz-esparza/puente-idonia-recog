# pyright: reportUnknownMemberType=false

from typing import override

import pymupdf

from puente.domain.ports import PdfToTextPort


class PymupdfAdapter(PdfToTextPort):
    @override
    def convert(self, pdf_file: bytes) -> str:
        document = pymupdf.open(stream=pdf_file, filetype="pdf")
        pages = [p.get_textpage().extractText() for p in document]
        return "\n".join(pages)
