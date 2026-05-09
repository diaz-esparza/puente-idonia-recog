# pyright: reportUnknownMemberType=false
"""Temporary mock data generators for CLI demo commands.

These helpers are slated for removal once the project migrates to
proper pytest-based fixtures and integration tests.
"""

import struct

import pymupdf


def create_demo_report_pdf() -> bytes:
    """Generate a synthetic surgical report PDF for the demo."""
    doc = pymupdf.open()
    page = doc.new_page()
    text = (
        "INFORME QUIRÚRGICO\n\n"
        + "Paciente: Juan Martínez López\n"
        + "NHC: 7845321\n"
        + "DNI: 12345678A\n"
        + "Fecha: 2024-03-15\n\n"
        + "CIRUGÍA DE RODILLA DERECHA\n\n"
        + "Se realizó artroscopia de rodilla derecha con resección de "
        + "menisco medial roto. Procedimiento sin incidencias. "
        + "El paciente evolucionó favorablemente en el postoperatorio "
        + "inmediato.\n\n"
        + "Recomendaciones:\n"
        + "- Reposo relativo 48h\n"
        + "- Fisioterapia desde la semana siguiente\n"
        + "- Revisión en 15 días"
    )
    _ = page.insert_text((72, 72), text, fontsize=11)
    return doc.tobytes()


def create_demo_dicom() -> bytes:
    """Generate a minimal DICOM file for the demo."""
    preamble = b"\x00" * 128
    magic = b"DICM"

    def _tag(group: int, element: int) -> bytes:
        return struct.pack("<HH", group, element)

    def _ui(tag: bytes, uid: str) -> bytes:
        v = uid.encode("ascii")
        if len(v) % 2:
            v += b"\x00"
        return tag + b"UI" + struct.pack("<H", len(v)) + v

    def _sh(tag: bytes, val: str) -> bytes:
        v = val.encode("ascii")
        if len(v) % 2:
            v += b" "
        return tag + b"SH" + struct.pack("<H", len(v)) + v

    def _pn(tag: bytes, val: str) -> bytes:
        v = val.encode("ascii")
        if len(v) % 2:
            v += b" "
        return tag + b"PN" + struct.pack("<H", len(v)) + v

    def _lo(tag: bytes, val: str) -> bytes:
        v = val.encode("ascii")
        if len(v) % 2:
            v += b" "
        return tag + b"LO" + struct.pack("<H", len(v)) + v

    def _ul(tag: bytes, val: int) -> bytes:
        return tag + b"UL" + struct.pack("<H", 4) + struct.pack("<I", val)

    def _ob(tag: bytes, val: bytes) -> bytes:
        return tag + b"OB" + b"\x00\x00" + struct.pack("<I", len(val)) + val

    meta = b""
    meta += _ob(_tag(0x0002, 0x0001), b"\x00\x01")
    meta += _ui(_tag(0x0002, 0x0002), "1.2.840.10008.5.1.4.1.1.2")
    meta += _ui(
        _tag(0x0002, 0x0003),
        "1.2.826.0.1.3680043.2.1125.1.1.20240315.1",
    )
    meta += _ui(_tag(0x0002, 0x0010), "1.2.840.10008.1.2.1")
    meta = _ul(_tag(0x0002, 0x0000), len(meta)) + meta

    dataset = b""
    dataset += _sh(_tag(0x0008, 0x0060), "CT")
    dataset += _pn(_tag(0x0010, 0x0010), "Martinez^Juan")
    dataset += _lo(_tag(0x0010, 0x0020), "12345678A")
    dataset += _ui(
        _tag(0x0020, 0x000D),
        "1.2.826.0.1.3680043.2.1125.1.2.20240315.1",
    )
    dataset += _sh(_tag(0x0020, 0x0010), "MRI-2024-001")

    return preamble + magic + meta + dataset
