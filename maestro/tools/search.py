"""An offline knowledge-base search tool.

Retrieves passages from a small built-in corpus by lexical overlap, so a
researcher agent produces evidence-backed findings with no network. Swap this for
a real web search or a vector store (a natural extension point) without touching
the agents.
"""

from __future__ import annotations

import re

from .base import Tool

_TOKEN_RE = re.compile(r"\b\w+\b", re.UNICODE)

# A compact, multi-domain corpus of general methods, so grounding is helpful
# across fitness, learning, software, and business goals rather than steering
# every answer toward one field. When nothing matches, agents reason from their
# own expertise instead.
_CORPUS: list[str] = [
    "A good plan sets a specific measurable goal, breaks it into phases, sequences "
    "tasks by dependency, and builds in checkpoints to measure progress and adjust.",
    "Sustainable progress comes from progressive overload: increase difficulty in "
    "small increments, allow time to recover, and track results to know when to advance.",
    "Consistency beats intensity: a routine that stays repeatable on a busy week "
    "compounds far more than an ambitious plan that gets abandoned after a fortnight.",
    "Balanced physical training combines resistance work for strength, conditioning "
    "for endurance, and mobility for injury prevention, with rest days for recovery; "
    "sleep and nutrition drive results as much as the workouts themselves.",
    "Losing body fat while keeping muscle needs a modest calorie deficit, adequate "
    "protein, and continued strength training so the body preserves lean mass.",
    "Effective learning is active and spaced: practise retrieval, space repetition "
    "over days, and raise difficulty as mastery grows rather than rereading passively.",
    "Retrieval-augmented generation grounds language models in a knowledge base, "
    "reducing hallucination by citing retrieved passages at answer time.",
    "Multi-agent systems decompose a goal into specialised roles that plan, act "
    "with tools, critique, and synthesise, improving quality over a single pass.",
    "Reliability engineering favours graceful degradation, retries with backoff, "
    "and circuit breakers so a single dependency cannot take down the whole system.",
    "Go-to-market strategy succeeds when it targets a narrow beachhead segment, "
    "nails a single sharp value proposition, and expands only after repeatable wins.",
]


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class SearchTool(Tool):
    name = "search"
    description = "Search the knowledge base for passages relevant to a query."

    async def run(self, argument: str) -> str:
        query = _tokens(argument)
        if not query:
            return "No query provided."
        scored = sorted(
            ((len(query & _tokens(doc)), doc) for doc in _CORPUS),
            key=lambda pair: pair[0],
            reverse=True,
        )
        hits = [doc for score, doc in scored if score > 0][:2]
        if not hits:
            return "No direct matches in the knowledge base; reasoning from priors."
        return " | ".join(hits)
