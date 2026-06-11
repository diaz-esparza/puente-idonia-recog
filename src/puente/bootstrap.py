from functools import lru_cache

from puente.adapters.idonia import IdoniaAdapter
from puente.adapters.pdf_to_txt import PymupdfAdapter
from puente.adapters.placeholders import (
    DummyHumanizationAdapter,
    DummyPresidioAdapter,
)
from puente.adapters.presidio import PresidioAdapter
from puente.adapters.recog import RecogAdapter
from puente.config import get_settings
from puente.service.pipeline import BridgePipeline


@lru_cache(maxsize=1)
def get_pipeline() -> BridgePipeline:
    settings = get_settings()
    humanization_impl = (
        DummyHumanizationAdapter()
        if settings.humanized_mock
        else RecogAdapter()
    )
    pii_redaction_impl = (
        DummyPresidioAdapter() if settings.presidio_mock else PresidioAdapter()
    )
    return BridgePipeline(
        storage=IdoniaAdapter(),
        pdf_to_text=PymupdfAdapter(),
        humanization=humanization_impl,
        pii_redaction=pii_redaction_impl,
    )
