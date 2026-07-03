"""Run lifecycle management.

The engine starts a run as a background task with its own event bus, tracks its
status and final summary, and lets any number of clients subscribe to its event
stream (with replay). It is the single object the HTTP/WebSocket server talks to.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from .brains import build_brain
from .brains.base import Brain
from .events import ERROR, Event, EventBus
from .orchestrator import Orchestrator
from .tools import default_toolbox
from .tools.base import Tool
from .types import RunStatus, RunSummary


@dataclass
class RunHandle:
    run_id: str
    goal: str
    bus: EventBus
    status: RunStatus = RunStatus.RUNNING
    summary: RunSummary | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)


class Engine:
    def __init__(
        self,
        brain_factory: Callable[[], Brain] = build_brain,
        tools_factory: Callable[[], dict[str, Tool]] = default_toolbox,
    ) -> None:
        self._brain_factory = brain_factory
        self._tools_factory = tools_factory
        self._runs: dict[str, RunHandle] = {}

    def start_run(self, goal: str, *, researchers: int = 2) -> RunHandle:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        bus = EventBus(run_id)
        brain = self._brain_factory()
        orchestrator = Orchestrator(bus, brain, self._tools_factory(), researchers=researchers)
        handle = RunHandle(run_id=run_id, goal=goal, bus=bus)
        self._runs[run_id] = handle
        handle.task = asyncio.create_task(self._drive(handle, orchestrator, brain, goal))
        return handle

    async def _drive(
        self, handle: RunHandle, orchestrator: Orchestrator, brain: Brain, goal: str
    ) -> None:
        try:
            handle.summary = await orchestrator.run(goal)
            handle.status = RunStatus.COMPLETED
        except Exception as exc:  # surface the failure as an event, never crash the server
            handle.status = RunStatus.FAILED
            handle.bus.emit(ERROR, message=str(exc))
        finally:
            await brain.aclose()
            handle.bus.close()

    def get(self, run_id: str) -> RunHandle | None:
        return self._runs.get(run_id)

    async def subscribe(self, run_id: str) -> AsyncIterator[Event]:
        handle = self._runs[run_id]
        async for event in handle.bus.subscribe():
            yield event

    async def run_to_completion(self, goal: str, *, researchers: int = 2) -> RunSummary:
        """Convenience for scripts/tests: run and await the summary."""
        handle = self.start_run(goal, researchers=researchers)
        assert handle.task is not None
        await handle.task
        assert handle.summary is not None
        return handle.summary

    async def aclose(self) -> None:
        for handle in self._runs.values():
            if handle.task is not None and not handle.task.done():
                handle.task.cancel()
