from __future__ import annotations

from maestro.types import RunStatus


async def test_run_to_completion(fast_engine):
    summary = await fast_engine.run_to_completion("Ship a product")
    assert summary.status is RunStatus.COMPLETED
    assert summary.deliverable
    assert summary.total_tokens > 0


async def test_start_run_and_subscribe(fast_engine):
    handle = fast_engine.start_run("Design a launch plan")
    types = [event.type async for event in fast_engine.subscribe(handle.run_id)]
    assert "run_started" in types
    assert "run_completed" in types
    assert handle.task is not None
    await handle.task
    assert fast_engine.get(handle.run_id).status is RunStatus.COMPLETED


async def test_unknown_run(fast_engine):
    assert fast_engine.get("nope") is None
