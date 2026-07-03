from __future__ import annotations

from maestro.brains import SimulatedBrain
from maestro.events import AGENT_SPAWNED, EDGE, RUN_COMPLETED, EventBus
from maestro.orchestrator import Orchestrator
from maestro.tools import default_toolbox
from maestro.types import RunStatus


async def test_full_run_produces_deliverable_and_topology():
    bus = EventBus("run")
    orch = Orchestrator(bus, SimulatedBrain(delay=0.0), default_toolbox(), researchers=2)
    summary = await orch.run("Design a go-to-market strategy for a SaaS product")

    assert summary.status is RunStatus.COMPLETED
    assert summary.deliverable and summary.deliverable.startswith("#")
    assert summary.agents == 6  # orchestrator + 2 researchers + analyst + critic + writer

    spawned = [e for e in bus.log if e.type == AGENT_SPAWNED]
    assert len(spawned) == 6
    edges = [e for e in bus.log if e.type == EDGE]
    assert len(edges) == 2 * 2 + 2  # each researcher in/out of pipeline + analyst->critic->writer
    assert any(e.type == RUN_COMPLETED for e in bus.log)
    assert summary.total_tool_calls >= 2  # each researcher searched


async def test_researcher_count_scales_agents():
    bus = EventBus("r")
    orch = Orchestrator(bus, SimulatedBrain(delay=0.0), default_toolbox(), researchers=3)
    summary = await orch.run("Reduce churn")
    assert summary.agents == 7


async def test_calculator_fires_when_a_percentage_appears():
    bus = EventBus("r")
    orch = Orchestrator(bus, SimulatedBrain(delay=0.0), default_toolbox(), researchers=1)
    # the corpus mentions "120 percent" for retention goals, triggering the calculator
    await orch.run("Improve net revenue retention above 120 percent")
    tools_used = {e.data.get("tool") for e in bus.log if e.type == "tool_call"}
    assert "calculator" in tools_used
