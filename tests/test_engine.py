from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from maestro.brains.base import Brain
from maestro.engine import Engine
from maestro.types import RunStatus


class _SlowBrain(Brain):
    name = "slow"

    async def stream(
        self, prompt: str, *, system: str | None = None, role: str | None = None
    ) -> AsyncIterator[str]:
        await asyncio.sleep(5)
        yield "x"


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


async def test_list_runs_newest_first(fast_engine):
    await fast_engine.run_to_completion("first")
    await fast_engine.run_to_completion("second")
    runs = fast_engine.list_runs()
    assert [r["goal"] for r in runs] == ["second", "first"]
    assert runs[0]["status"] == "completed"


async def test_cancel_running_run():
    engine = Engine(brain_factory=lambda: _SlowBrain())
    handle = engine.start_run("goal")
    await asyncio.sleep(0.05)  # let it start and block on the slow brain
    assert engine.cancel(handle.run_id) is True
    assert handle.status is RunStatus.CANCELLED
    assert any(e.type == "run_cancelled" for e in handle.bus.log)
    assert engine.cancel(handle.run_id) is False  # already cancelled


async def test_cancel_unknown_run(fast_engine):
    assert fast_engine.cancel("nope") is False
