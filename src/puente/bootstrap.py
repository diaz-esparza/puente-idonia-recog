from puente.adapters.idonia import IdoniaAdapter
from puente.adapters.pdf_to_txt import PymupdfAdapter
from puente.adapters.placeholders import DummyHumanizationAdapter
from puente.service.pipeline import BridgePipeline


def create_pipeline() -> BridgePipeline:
    return BridgePipeline(
        storage=IdoniaAdapter(),
        pdf_to_text=PymupdfAdapter(),
        humanization=DummyHumanizationAdapter(),
    )
