"""Integration tests for error management in `BridgePipeline` orchestrator."""

import pytest

from puente.service.pipeline import BridgePipeline
from tests.support.data import build_simple_record
from tests.support.fakes import (
    DelayedFailingDicomStorage,
    FailingDicomStorage,
    FailingHumanization,
    FailingMagicLinkStorage,
    FailingReportStorage,
    FakeHumanization,
    FakePdfToText,
    FakeStorage,
)


async def test_run_raises_when_magic_link_fails() -> None:
    """Final part of the pipeline should raise on failure."""
    pipeline = BridgePipeline(
        storage=FailingMagicLinkStorage(),
        pdf_to_text=FakePdfToText(),
        humanization=FakeHumanization(),
    )
    record = build_simple_record()
    with pytest.raises(RuntimeError, match=FailingMagicLinkStorage.__name__):
        _ = await pipeline.run(record)


"""As of the current implementation, any upload/humanization failing
should raise, independently on order of execution, but only the events
that fail first, will stop the magic link creation.

This is because of the `FIRST_COMPLETED` directive in `asyncio.wait`.

The following tests check for this exact behavior in the code.

This behavior might not be optimal in production, and is subject to
change. The test is just in place to ensure no unintended change in
the program flow.
"""


@pytest.mark.parametrize(
    ("storage_module", "humanization_module", "failing_module"),
    [
        (FailingDicomStorage(), FakeHumanization(), FailingDicomStorage),
        (FailingReportStorage(), FakeHumanization(), FailingReportStorage),
        (FakeStorage(), FailingHumanization(), FailingHumanization),
    ],
)
async def test_run_magic_link_not_created_on_fast_upload_fails(
    storage_module: FakeStorage,
    humanization_module: FakeHumanization,
    failing_module: type,
) -> None:
    pipeline = BridgePipeline(
        storage=storage_module,
        pdf_to_text=FakePdfToText(),
        humanization=humanization_module,
    )
    record = build_simple_record()
    with pytest.raises(RuntimeError, match=failing_module.__name__):
        _ = await pipeline.run(record)
    assert not storage_module.magic_requested


async def test_run_magic_link_created_on_slow_upload_fails() -> None:
    storage = DelayedFailingDicomStorage()
    pipeline = BridgePipeline(
        storage=storage,
        pdf_to_text=FakePdfToText(),
        humanization=FakeHumanization(),
    )
    record = build_simple_record()
    with pytest.raises(RuntimeError, match=storage.__class__.__name__):
        _ = await pipeline.run(record)
    assert storage.magic_requested
