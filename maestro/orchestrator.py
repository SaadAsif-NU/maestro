"""The Orchestrator: coordinates the ensemble to accomplish a goal.

The pattern is a recognisable multi-agent workflow: plan, fan out independent
research in parallel, synthesise, critique, then write. Every stage streams its
work through the event bus, and the topology (who feeds whom) is published up
front so the UI can draw the graph before the agents start moving.
"""

from __future__ import annotations

import asyncio
import re
import time

from .agents import Agent
from .brains.base import Brain
from .events import (
    AGENT_SPAWNED,
    EDGE,
    METRICS,
    PLAN,
    RUN_COMPLETED,
    RUN_STARTED,
    EventBus,
)
from .tools.base import Tool
from .types import AgentResult, Role, RunStatus, RunSummary, Task

_PERCENT_RE = re.compile(r"(\d+)\s*percent|(\d+)%")


def _subject(goal: str) -> str:
    return goal.strip().rstrip(".!?").strip()


def _subquestions(goal: str, n: int) -> list[tuple[str, str]]:
    subject = _subject(goal)
    angles = [
        ("Demand and opportunity", f"market demand and opportunity for {subject}"),
        ("Risks and constraints", f"risks, costs and constraints around {subject}"),
        ("Best practices", f"proven best-practice approaches to {subject}"),
        ("Competitive landscape", f"competitive and comparable approaches to {subject}"),
    ]
    return angles[:n]


class Orchestrator:
    def __init__(
        self, bus: EventBus, brain: Brain, tools: dict[str, Tool], *, researchers: int = 2
    ) -> None:
        self._bus = bus
        self._brain = brain
        self._tools = tools
        self._n_researchers = researchers

    def _spawn(self, agent_id: str, role: Role, title: str) -> Agent:
        tools = self._tools if role in (Role.RESEARCHER, Role.ANALYST) else {}
        self._bus.emit(AGENT_SPAWNED, agent_id=agent_id, role=role.value, title=title)
        return Agent(agent_id, role, self._brain, self._bus, tools)

    def _edge(self, source: str, target: str) -> None:
        self._bus.emit(EDGE, source=source, target=target)

    async def run(self, goal: str) -> RunSummary:
        started = time.perf_counter()
        self._bus.emit(RUN_STARTED, goal=goal)

        # 1. Orchestrator plans.
        orchestrator = self._spawn("orchestrator", Role.ORCHESTRATOR, "Orchestrator")
        await orchestrator.run(Task(id="plan", role=Role.ORCHESTRATOR, title="Plan", prompt=goal))

        # 2. Announce the full team and topology so the graph renders at once.
        subqs = _subquestions(goal, self._n_researchers)
        researchers = [
            self._spawn(f"researcher-{i}", Role.RESEARCHER, title)
            for i, (title, _) in enumerate(subqs)
        ]
        analyst = self._spawn("analyst", Role.ANALYST, "Analyst")
        critic = self._spawn("critic", Role.CRITIC, "Critic")
        writer = self._spawn("writer", Role.WRITER, "Writer")

        for r in researchers:
            self._edge("orchestrator", r.id)
            self._edge(r.id, "analyst")
        self._edge("analyst", "critic")
        self._edge("critic", "writer")
        self._bus.emit(PLAN, workstreams=[t for t, _ in subqs])

        # 3. Research in parallel (independent evidence gathering).
        research: list[AgentResult] = await asyncio.gather(
            *(
                r.run(
                    Task(
                        id=r.id,
                        role=Role.RESEARCHER,
                        title=title,
                        prompt=f"{goal}\n\nFocus: {query}",
                    ),
                    tool_step=("search", query, "researcher_findings"),
                )
                for r, (title, query) in zip(researchers, subqs, strict=True)
            )
        )
        self._emit_metrics([*research])

        # 4. Analyst synthesises, optionally checking a figure with the calculator.
        research_blob = "\n".join(f"- {r.content}" for r in research)
        analyst_tool = self._calculator_step(research_blob)
        analysis = await analyst.run(
            Task(
                id="analyst",
                role=Role.ANALYST,
                title="Analysis",
                prompt=f"{goal}\n\nRESEARCH:\n{research_blob}",
            ),
            tool_step=analyst_tool,
        )

        # 5. Critic pressure-tests the analysis.
        critique = await critic.run(
            Task(
                id="critic",
                role=Role.CRITIC,
                title="Critique",
                prompt=f"{goal}\n\nANALYSIS:\n{analysis.content}",
            )
        )

        # 6. Writer composes the deliverable.
        deliverable = await writer.run(
            Task(
                id="writer",
                role=Role.WRITER,
                title="Deliverable",
                prompt=f"{goal}\n\nANALYSIS:\n{analysis.content}\n\nCRITIQUE:\n{critique.content}",
            )
        )

        results = [*research, analysis, critique, deliverable]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        summary = RunSummary(
            run_id=self._bus.log[0].run_id if self._bus.log else "",
            goal=goal,
            status=RunStatus.COMPLETED,
            deliverable=deliverable.content,
            total_tokens=sum(r.tokens for r in results),
            total_tool_calls=sum(len(r.tool_calls) for r in results),
            elapsed_ms=elapsed_ms,
            agents=len(researchers) + 4,
        )
        self._bus.emit(
            RUN_COMPLETED,
            deliverable=deliverable.content,
            total_tokens=summary.total_tokens,
            total_tool_calls=summary.total_tool_calls,
            elapsed_ms=round(elapsed_ms, 1),
            agents=summary.agents,
        )
        return summary

    def _calculator_step(self, text: str) -> tuple[str, str, str] | None:
        match = _PERCENT_RE.search(text)
        if not match:
            return None
        number = match.group(1) or match.group(2)
        # Show the calculator turning a percentage into a multiple (a real,
        # sensible check), with no follow-up reasoning pass.
        return ("calculator", f"{number}/100", "")

    def _emit_metrics(self, results: list[AgentResult]) -> None:
        self._bus.emit(
            METRICS,
            tokens=sum(r.tokens for r in results),
            tool_calls=sum(len(r.tool_calls) for r in results),
        )
