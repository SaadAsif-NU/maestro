from __future__ import annotations

from maestro.agents import Agent
from maestro.brains import SimulatedBrain
from maestro.events import AGENT_COMPLETED, AGENT_STATUS, TOKEN, TOOL_CALL, TOOL_RESULT, EventBus
from maestro.tools import default_toolbox
from maestro.types import Role, Task


async def test_agent_emits_events_and_returns_result():
    bus = EventBus("r")
    agent = Agent("a1", Role.ANALYST, SimulatedBrain(delay=0.0), bus)
    result = await agent.run(
        Task(id="t", role=Role.ANALYST, title="Analysis", prompt="Ship a product")
    )

    types = [e.type for e in bus.log]
    assert TOKEN in types and AGENT_STATUS in types and AGENT_COMPLETED in types
    statuses = [e.data["status"] for e in bus.log if e.type == AGENT_STATUS]
    assert statuses[0] == "thinking" and statuses[-1] == "done"
    assert result.tokens > 0 and result.content


async def test_agent_tool_step_records_tool_call():
    bus = EventBus("r")
    agent = Agent("r1", Role.RESEARCHER, SimulatedBrain(delay=0.0), bus, default_toolbox())
    result = await agent.run(
        Task(id="t", role=Role.RESEARCHER, title="Research", prompt="market for SaaS"),
        tool_step=("search", "market for SaaS", "researcher_findings"),
    )
    types = [e.type for e in bus.log]
    assert TOOL_CALL in types and TOOL_RESULT in types
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool == "search"


async def test_agent_events_carry_agent_and_role():
    bus = EventBus("r")
    await Agent("x", Role.CRITIC, SimulatedBrain(delay=0.0), bus).run(
        Task(id="t", role=Role.CRITIC, title="Critique", prompt="Ship a product")
    )
    tokens = [e for e in bus.log if e.type == TOKEN]
    assert tokens and all(e.agent_id == "x" and e.role == "critic" for e in tokens)
