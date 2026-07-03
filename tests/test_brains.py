from __future__ import annotations

import httpx

from maestro.brains import SimulatedBrain
from maestro.brains.openai import OpenAIBrain


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


async def test_build_brain_prefers_gemini(monkeypatch):
    from maestro.brains import build_brain

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("MAESTRO_MODEL", "gemini-2.0-flash")
    brain = build_brain()
    assert brain.name == "gemini-2.0-flash"
    assert "generativelanguage.googleapis.com" in brain._base_url
    await brain.aclose()


async def test_build_brain_defaults_to_offline(monkeypatch):
    from maestro.brains import build_brain

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert build_brain().name == "simulated"


async def test_openai_brain_retries_on_429():
    calls = {"n": 0}
    sse = 'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="rate limited")  # first attempt is throttled
        return httpx.Response(200, text=sse)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    brain = OpenAIBrain(api_key="x", client=client, max_retries=3, backoff_base=0.0)
    out = [chunk async for chunk in brain.stream("hello")]
    assert "".join(out) == "hi"
    assert calls["n"] == 2  # it retried the 429 and then succeeded
    await brain.aclose()


async def test_openai_brain_raises_after_exhausting_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="always throttled")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    brain = OpenAIBrain(api_key="x", client=client, max_retries=2, backoff_base=0.0)
    try:
        with_raises = False
        try:
            [chunk async for chunk in brain.stream("hello")]
        except httpx.HTTPStatusError:
            with_raises = True
        assert with_raises
    finally:
        await brain.aclose()
