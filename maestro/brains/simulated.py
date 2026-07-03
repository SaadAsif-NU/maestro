"""A deterministic, offline brain.

It produces believable, role-appropriate reasoning with no API key and no
network, streaming chunk by chunk so the live view looks exactly like a real
model. Output is a pure function of (role, prompt), which makes demos flawless
and tests reproducible. Swap in a real model brain for genuine intelligence; the
orchestration is identical.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

from .base import Brain

_CHUNK_RE = re.compile(r"\S+\s*|\n")


def _subject(text: str) -> str:
    """The first line of a prompt, trimmed of trailing punctuation."""
    first = text.strip().splitlines()[0] if text.strip() else "the objective"
    return first.strip().rstrip(".!?").strip()


def _section(text: str, header: str) -> str:
    """Pull a labelled block (``HEADER:\\n...``) out of a composed prompt."""
    match = re.search(rf"{header}:\n(.+?)(?:\n[A-Z]+:|\Z)", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _excerpt(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit].rsplit(" ", 1)[0] + "..."


def _orchestrator(prompt: str) -> str:
    subject = _subject(prompt)
    return (
        f"Decomposing the goal into parallel workstreams: {subject}.\n"
        "Plan: dispatch researchers to gather independent evidence, hand their "
        "findings to an analyst for synthesis, have a critic pressure-test the "
        "result, and let the writer compose the deliverable. Fanning out the "
        "research now."
    )


def _researcher_plan(prompt: str) -> str:
    subject = _subject(prompt)
    return (
        f"Investigating: {subject}. I will query the knowledge base for primary "
        "evidence before drawing any conclusion."
    )


def _researcher_findings(prompt: str) -> str:
    sources = _section(prompt, "SOURCES")
    lead = _excerpt(sources or "no direct matches; reasoning from priors", 200)
    return (
        f"Retrieved supporting material. Key signal: {lead} "
        "This gives a defensible, evidence-backed basis for the analysis stage."
    )


def _analyst(prompt: str) -> str:
    return (
        "Cross-referencing the researchers' findings into a single coherent picture. "
        "The evidence converges on a clear direction: keep the initial scope narrow, "
        "lead with the highest-impact option, and expand only on proven, repeatable "
        "wins. Three themes dominate, the trade-offs are explicit, and the "
        "recommended path is the one that maximises impact against the goal."
    )


def _critic(prompt: str) -> str:
    return (
        "Stress-testing the analysis for weak assumptions and missing angles.\n"
        "Risks: over-reliance on a single source, and an optimistic timeline. "
        "Gaps: the cost side is under-explored. On balance the reasoning holds; "
        "the deliverable should surface the caveats explicitly. Confidence: 0.83."
    )


def _writer(prompt: str) -> str:
    subject = _subject(prompt)
    return (
        f"# {subject.capitalize()}\n\n"
        "## Summary\n"
        "A synthesised, evidence-backed response drawing on parallel research, a "
        "quantitative cross-check, and a critical review before finalising.\n\n"
        "## Recommendations\n"
        "- Lead with the highest-impact, lowest-risk option surfaced by the analysis.\n"
        "- Address the critic's caveats up front to build trust.\n"
        "- Sequence the work so early, measurable wins fund the harder phases.\n\n"
        "## Next steps\n"
        "Validate the top recommendation with a small, measurable pilot before "
        "committing further resources."
    )


def _assistant(prompt: str) -> str:
    return (
        "Hi, I am Maestro, a live multi-agent studio. Give me a concrete goal, "
        'for example "Design a go-to-market strategy for a B2B SaaS analytics '
        'product", and I will assemble a team to research it, analyse the '
        "findings, critique them, and deliver a result you can read and download. "
        "What would you like to work on?"
    )


_SCRIPTS = {
    "orchestrator": _orchestrator,
    "researcher": _researcher_plan,
    "researcher_findings": _researcher_findings,
    "analyst": _analyst,
    "critic": _critic,
    "writer": _writer,
    "assistant": _assistant,
}


class SimulatedBrain(Brain):
    """Deterministic, offline brain driven by role-specific scripts."""

    name = "simulated"

    def __init__(self, *, delay: float = 0.02) -> None:
        # Per-chunk delay makes streaming visible in the UI; set 0 in tests.
        self._delay = delay

    async def stream(
        self, prompt: str, *, system: str | None = None, role: str | None = None
    ) -> AsyncIterator[str]:
        script = _SCRIPTS.get(role or "", _analyst)
        text = script(prompt)
        for chunk in _CHUNK_RE.findall(text):
            if self._delay:
                await asyncio.sleep(self._delay)
            yield chunk
