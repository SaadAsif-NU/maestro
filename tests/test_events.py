from __future__ import annotations

import asyncio

from maestro.events import EventBus


def test_emit_assigns_increasing_seq_and_logs():
    bus = EventBus("run-1")
    a = bus.emit("token", text="hi")
    b = bus.emit("token", text="there")
    assert (a.seq, b.seq) == (0, 1)
    assert [e.type for e in bus.log] == ["token", "token"]
    assert bus.log[0].run_id == "run-1"


async def test_subscribe_replays_backlog_then_live():
    bus = EventBus("r")
    bus.emit("a")

    async def consume() -> list[str]:
        return [e.type async for e in bus.subscribe()]

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)  # let the subscriber replay the backlog and start waiting
    bus.emit("b")
    bus.close()
    result = await asyncio.wait_for(task, 1.0)
    assert result == ["a", "b"]


async def test_late_subscriber_after_close_gets_full_backlog():
    bus = EventBus("r")
    bus.emit("a")
    bus.emit("b")
    bus.close()
    result = [e.type async for e in bus.subscribe()]
    assert result == ["a", "b"]


async def test_multiple_subscribers_each_get_everything():
    bus = EventBus("r")

    async def consume() -> list[int]:
        return [e.seq async for e in bus.subscribe()]

    t1 = asyncio.create_task(consume())
    t2 = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    for _ in range(3):
        bus.emit("x")
    bus.close()
    r1, r2 = await asyncio.gather(t1, t2)
    assert r1 == [0, 1, 2]
    assert r2 == [0, 1, 2]
