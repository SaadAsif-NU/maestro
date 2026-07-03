from __future__ import annotations

from maestro.brains import SimulatedBrain


async def _collect(brain, prompt, role):
    return [c async for c in brain.stream(prompt, role=role)]


async def test_deterministic():
    a = SimulatedBrain(delay=0.0)
    b = SimulatedBrain(delay=0.0)
    out_a = await a.complete("Ship a product", role="orchestrator")
    out_b = await b.complete("Ship a product", role="orchestrator")
    assert out_a == out_b
    assert len(out_a) > 0


async def test_roles_differ():
    brain = SimulatedBrain(delay=0.0)
    planner = await brain.complete("Ship a product", role="orchestrator")
    critic = await brain.complete("Ship a product", role="critic")
    assert planner != critic


async def test_streams_multiple_chunks():
    brain = SimulatedBrain(delay=0.0)
    chunks = await _collect(brain, "Ship a product", "analyst")
    assert len(chunks) > 3
    assert "".join(chunks) == await brain.complete("Ship a product", role="analyst")


async def test_writer_produces_markdown():
    brain = SimulatedBrain(delay=0.0)
    out = await brain.complete("Design a launch plan", role="writer")
    assert out.startswith("# ")
    assert "## Recommendations" in out


async def test_orchestrator_references_goal():
    brain = SimulatedBrain(delay=0.0)
    out = await brain.complete("Reduce customer churn", role="orchestrator")
    assert "Reduce customer churn" in out
