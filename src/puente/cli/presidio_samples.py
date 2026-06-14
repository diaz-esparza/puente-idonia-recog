"""Shared Presidio sample data used by both tests and CLI demos."""

PII_SAMPLES: list[tuple[str, str, list[str]]] = [
    (
        "Nombre",
        "Paciente: Juan Martínez López.",
        ["Juan", "Martínez", "López"],
    ),
    (
        "DNI",
        "El paciente se llama Carlos, con DNI 23923401C. Vive en Ponferrada.",
        ["Carlos", "23923401C", "Ponferrada"],
    ),
    *[
        (data_name, f"El dato relevante: {data}", [data])
        for data_name, data in [
            ("Email", "diaz.esparza@proton.me"),
            ("Email", "marina.dader.suarez@gmail.com"),
            ("NIF", "12345678Z"),
            ("NIE", "X1234567L"),
            ("NIE", "Z3986854Q"),
        ]
    ],
]

MEDICAL_STRINGS: list[str] = [
    "Se realizó artroscopia de rodilla derecha con resección de "
    + "menisco medial roto. Procedimiento sin incidencias.",
    "El paciente recibió una concusión hace 2 semanas, no se ven "
    + "secuelas. Se recomienda seguimiento.",
]

MEDICAL_LABELS: list[tuple[str, str]] = [
    ("Hallazgo clínico", MEDICAL_STRINGS[0]),
    ("Seguimiento", MEDICAL_STRINGS[1]),
]

COMMON_STRINGS: list[str] = [
    "Ha habido un incidente en la oficina.",
    "\r\nLa oveja camina por el monte.\n",
    "",
    "Hoy es día 15 de agosto de 2025",
    "Los sucesos ocurrieron el 12/10/18.",
    "Los sucesos ocurrieron el 12/10/2018.",
]


def get_pii_fields_for_tests() -> list[tuple[str, list[str]]]:
    """Return (text, keywords) pairs for pytest parametrize."""
    return [(text, kw) for _, text, kw in PII_SAMPLES]


def get_pii_samples_for_demo() -> list[tuple[str, str]]:
    """Return (label, text) pairs for CLI demo display."""
    return [(label, text) for label, text, _ in PII_SAMPLES]
