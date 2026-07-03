"""Event model and the per-run event bus.

Everything a run does is expressed as an ordered stream of events: an agent
started thinking, a token was produced, a tool was called, a result came back.
The UI is a pure projection of this stream, which means the same events drive the
live view, a reconnecting client (via replay), and the tests.

The bus is event-sourced: it keeps the full ordered log so a subscriber that
connects late (or reconnects) receives the backlog and then live updates, with no
gap and no duplicate.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

# Event type constants (kept as plain strings so the wire format is obvious and
# the frontend can switch on them directly).
RUN_STARTED = "run_started"
PLAN = "plan"
AGENT_SPAWNED = "agent_spawned"
AGENT_STATUS = "agent_status"
TOKEN = "token"
TOOL_CALL = "tool_call"
TOOL_RESULT = "tool_result"
EDGE = "edge"
AGENT_COMPLETED = "agent_completed"
METRICS = "metrics"
RUN_COMPLETED = "run_completed"
ERROR = "error"


class Event(BaseModel):
    seq: int
    ts: float
    type: str
    run_id: str
    agent_id: str | None = None
    role: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class EventBus:
    """Ordered, replayable async fan-out of a run's events."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._log: list[Event] = []
        self._subscribers: set[asyncio.Queue[Event | None]] = set()
        self._seq = 0
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def log(self) -> list[Event]:
        return list(self._log)

    def emit(
        self,
        type: str,
        *,
        agent_id: str | None = None,
        role: str | None = None,
        **data: Any,
    ) -> Event:
        """Append an event to the log and fan it out to live subscribers."""
        event = Event(
            seq=self._seq,
            ts=time.time(),
            type=type,
            run_id=self._run_id,
            agent_id=agent_id,
            role=role,
            data=data,
        )
        self._seq += 1
        self._log.append(event)
        for queue in self._subscribers:
            queue.put_nowait(event)
        return event

    def close(self) -> None:
        self._closed = True
        for queue in self._subscribers:
            queue.put_nowait(None)

    async def subscribe(self) -> AsyncIterator[Event]:
        """Yield the full backlog, then live events until the bus closes.

        The subscriber is registered before the backlog is snapshotted, so an
        event published concurrently lands in both; the seq filter drops the
        duplicate. That is what guarantees no gap and no repeat.
        """
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            backlog = list(self._log)
            last_seq = backlog[-1].seq if backlog else -1
            for event in backlog:
                yield event
            if self._closed:
                return
            while True:
                item = await queue.get()
                if item is None:
                    return
                if item.seq > last_seq:
                    yield item
        finally:
            self._subscribers.discard(queue)
