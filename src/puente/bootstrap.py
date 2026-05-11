from functools import lru_cache

from puente.adapters.idonia import IdoniaAdapter
from puente.adapters.pdf_to_txt import PymupdfAdapter
from puente.adapters.recog import RecogAdapter
from puente.service.pipeline import BridgePipeline


@lru_cache(maxsize=1)
def get_pipeline() -> BridgePipeline:
    return BridgePipeline(
        storage=IdoniaAdapter(),
        pdf_to_text=PymupdfAdapter(),
        humanization=RecogAdapter(),
    )
