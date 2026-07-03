"""Run lifecycle management.

The engine starts a run as a background task with its own event bus, tracks its
status and final summary, and lets any number of clients subscribe to its event
stream (with replay). It is the single object the HTTP/WebSocket server talks to.

Reliability guards (from :class:`~maestro.config.Settings`): runs are bounded to a
maximum count (oldest finished runs are evicted), each run has a wall-clock
timeout, and the number of simultaneously active runs is capped.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from .brains import build_brain
from .brains.base import Brain
from .config import Settings
from .events import ERROR, RUN_CANCELLED, Event, EventBus
from .observability import log_event
from .orchestrator import Orchestrator
from .tools import default_toolbox
from .tools.base import Tool
from .types import RunStatus, RunSummary


class EngineBusyError(RuntimeError):
    """Raised when too many runs are already active."""


@dataclass
class RunHandle:
    run_id: str
    goal: str
    bus: EventBus
    status: RunStatus = RunStatus.RUNNING
    summary: RunSummary | None = None
    started_at: float = field(default_factory=time.time)
    task: asyncio.Task[None] | None = field(default=None, repr=False)


class Engine:
    def __init__(
        self,
        brain_factory: Callable[[], Brain] = build_brain,
        tools_factory: Callable[[], dict[str, Tool]] = default_toolbox,
        settings: Settings | None = None,
    ) -> None:
        self._brain_factory = brain_factory
        self._tools_factory = tools_factory
        self._settings = settings or Settings.from_env()
        self._runs: dict[str, RunHandle] = {}

    def active_run_count(self) -> int:
        return sum(1 for h in self._runs.values() if h.status is RunStatus.RUNNING)

    def start_run(
        self,
        goal: str,
        *,
        researchers: int = 2,
        brain_factory: Callable[[], Brain] | None = None,
    ) -> RunHandle:
        if self.active_run_count() >= self._settings.max_concurrent_runs:
            raise EngineBusyError("too many active runs")

        self._evict_if_needed()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        bus = EventBus(run_id)
        brain = (brain_factory or self._brain_factory)()
        orchestrator = Orchestrator(bus, brain, self._tools_factory(), researchers=researchers)
        handle = RunHandle(run_id=run_id, goal=goal, bus=bus)
        self._runs[run_id] = handle
        log_event("run.started", run_id=run_id, researchers=researchers)
        handle.task = asyncio.create_task(self._drive(handle, orchestrator, brain, goal))
        return handle

    def _evict_if_needed(self) -> None:
        """Keep the run store bounded by dropping the oldest *finished* runs."""
        while len(self._runs) >= self._settings.max_runs:
            victim = next(
                (rid for rid, h in self._runs.items() if h.status is not RunStatus.RUNNING),
                None,
            )
            if victim is None:
                return  # everything is still running; do not evict a live run
            self._runs.pop(victim, None)

    async def _drive(
        self, handle: RunHandle, orchestrator: Orchestrator, brain: Brain, goal: str
    ) -> None:
        try:
            handle.summary = await asyncio.wait_for(
                orchestrator.run(goal), timeout=self._settings.run_timeout_s
            )
            handle.status = RunStatus.COMPLETED
            elapsed = (time.time() - handle.started_at) * 1000.0
            log_event(
                "run.completed",
                run_id=handle.run_id,
                elapsed_ms=round(elapsed, 1),
                tokens=handle.summary.total_tokens,
                agents=handle.summary.agents,
            )
        except asyncio.TimeoutError:
            # asyncio.TimeoutError is only an alias of builtin TimeoutError from
            # 3.11+, so catch it by its asyncio name to also work on 3.10.
            handle.status = RunStatus.FAILED
            if not handle.bus.closed:
                handle.bus.emit(ERROR, message="run timed out")
            log_event("run.timeout", logging.WARNING, run_id=handle.run_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # surface the failure as an event, never crash the server
            handle.status = RunStatus.FAILED
            if not handle.bus.closed:
                handle.bus.emit(ERROR, message=str(exc))
            log_event("run.failed", logging.ERROR, run_id=handle.run_id, error=str(exc))
        finally:
            await brain.aclose()
            if not handle.bus.closed:
                handle.bus.close()

    def get(self, run_id: str) -> RunHandle | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[dict[str, str]]:
        """Newest-first list of runs in this session, for the history panel."""
        return [
            {"run_id": h.run_id, "goal": h.goal, "status": h.status.value}
            for h in reversed(list(self._runs.values()))
        ]

    def cancel(self, run_id: str) -> bool:
        """Stop a running run. Returns ``True`` if it was cancellable."""
        handle = self._runs.get(run_id)
        if handle is None or handle.status is not RunStatus.RUNNING:
            return False
        handle.status = RunStatus.CANCELLED
        if not handle.bus.closed:
            handle.bus.emit(RUN_CANCELLED, message="cancelled by user")
        if handle.task is not None and not handle.task.done():
            handle.task.cancel()
        if not handle.bus.closed:
            handle.bus.close()
        log_event("run.cancelled", run_id=run_id)
        return True

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
