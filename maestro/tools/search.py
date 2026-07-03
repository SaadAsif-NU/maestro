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

# A compact, general corpus so research is relevant across common business and
# technical goals.
_CORPUS: list[str] = [
    "Go-to-market strategy succeeds when it targets a narrow beachhead segment, "
    "nails a single sharp value proposition, and expands only after repeatable wins.",
    "B2B SaaS growth is driven by net revenue retention above 120 percent; "
    "expansion within existing accounts compounds faster than new logos.",
    "Retrieval-augmented generation grounds language models in a knowledge base, "
    "reducing hallucination by citing retrieved passages at answer time.",
    "Vector databases index embeddings with approximate nearest-neighbour graphs "
    "such as HNSW, trading a little recall for large speedups at scale.",
    "Pricing power comes from differentiation and switching costs; usage-based "
    "pricing aligns cost with customer value and lowers adoption friction.",
    "A durable moat is built from data network effects, high switching costs, and "
    "a workflow that becomes the system of record for a team.",
    "Reliability engineering favours graceful degradation, retries with backoff, "
    "and circuit breakers so that a single dependency cannot take down the system.",
    "Multi-agent systems decompose a goal into specialised roles that plan, act "
    "with tools, critique, and synthesise, improving quality over a single pass.",
    "Unit economics hinge on customer acquisition cost payback under twelve months "
    "and a lifetime-value-to-CAC ratio above three.",
    "Effective analytics products reduce time-to-insight; the winning feature is "
    "usually a fast, trustworthy answer to the one question a user asks daily.",
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
