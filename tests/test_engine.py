from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from maestro.brains import SimulatedBrain
from maestro.brains.base import Brain
from maestro.config import Settings
from maestro.engine import Engine, EngineBusyError
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


async def test_run_store_is_bounded(monkeypatch):
    monkeypatch.setenv("MAESTRO_MAX_RUNS", "3")
    engine = Engine(brain_factory=lambda: SimulatedBrain(delay=0.0), settings=Settings.from_env())
    for i in range(6):
        await engine.run_to_completion(f"design plan number {i}")
    assert len(engine.list_runs()) <= 3


async def test_run_times_out(monkeypatch):
    monkeypatch.setenv("MAESTRO_RUN_TIMEOUT", "0.05")
    engine = Engine(brain_factory=lambda: _SlowBrain(), settings=Settings.from_env())
    handle = engine.start_run("design a detailed plan")
    assert handle.task is not None
    await handle.task
    assert handle.status is RunStatus.FAILED
    assert any(
        e.type == "error" and "timed out" in e.data.get("message", "") for e in handle.bus.log
    )


async def test_rejects_when_too_many_active(monkeypatch):
    monkeypatch.setenv("MAESTRO_MAX_CONCURRENT_RUNS", "1")
    engine = Engine(brain_factory=lambda: _SlowBrain(), settings=Settings.from_env())
    first = engine.start_run("design a detailed plan")  # stays running on the slow brain
    with pytest.raises(EngineBusyError):
        engine.start_run("design another detailed plan")
    engine.cancel(first.run_id)
