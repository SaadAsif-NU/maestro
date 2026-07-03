"""The Agent: one worker in the ensemble.

An agent runs a task by streaming its reasoning from the brain, optionally
calling a tool and folding the result back into a second pass, and emitting an
event for everything it does so the run is fully observable.
"""

from __future__ import annotations

from .brains.base import Brain
from .events import (
    AGENT_COMPLETED,
    AGENT_STATUS,
    TOKEN,
    TOOL_CALL,
    TOOL_RESULT,
    EventBus,
)
from .tools.base import Tool
from .types import AgentResult, AgentStatus, Role, Task, ToolCall

# A tool invocation the orchestrator wants an agent to perform: (tool, argument,
# follow-up role used to script the post-tool reasoning).
ToolStep = tuple[str, str, str]


class Agent:
    def __init__(
        self,
        agent_id: str,
        role: Role,
        brain: Brain,
        bus: EventBus,
        tools: dict[str, Tool] | None = None,
    ) -> None:
        self.id = agent_id
        self.role = role
        self._brain = brain
        self._bus = bus
        self._tools = tools or {}

    def _status(self, status: AgentStatus) -> None:
        self._bus.emit(AGENT_STATUS, agent_id=self.id, role=self.role.value, status=status.value)

    async def _think(self, prompt: str, role_hint: str) -> tuple[str, int]:
        self._status(AgentStatus.THINKING)
        parts: list[str] = []
        tokens = 0
        async for chunk in self._brain.stream(prompt, role=role_hint):
            self._bus.emit(TOKEN, agent_id=self.id, role=self.role.value, text=chunk)
            parts.append(chunk)
            tokens += 1
        return "".join(parts), tokens

    async def run(self, task: Task, *, tool_step: ToolStep | None = None) -> AgentResult:
        content, tokens = await self._think(task.prompt, self.role.value)
        tool_calls: list[ToolCall] = []

        if tool_step is not None:
            tool_name, argument, follow_role = tool_step
            tool = self._tools.get(tool_name)
            if tool is not None:
                self._status(AgentStatus.USING_TOOL)
                self._bus.emit(
                    TOOL_CALL,
                    agent_id=self.id,
                    role=self.role.value,
                    tool=tool_name,
                    argument=argument,
                )
                result = await tool.run(argument)
                self._bus.emit(
                    TOOL_RESULT,
                    agent_id=self.id,
                    role=self.role.value,
                    tool=tool_name,
                    result=result,
                )
                tool_calls.append(ToolCall(tool=tool_name, argument=argument, result=result))

                if follow_role:
                    follow_prompt = f"{task.prompt}\n\nSOURCES:\n{result}"
                    extra, extra_tokens = await self._think(follow_prompt, follow_role)
                    content = f"{content}\n{extra}"
                    tokens += extra_tokens

        self._status(AgentStatus.DONE)
        self._bus.emit(
            AGENT_COMPLETED,
            agent_id=self.id,
            role=self.role.value,
            tokens=tokens,
            tool_calls=len(tool_calls),
        )
        return AgentResult(
            agent_id=self.id,
            role=self.role,
            title=task.title,
            content=content,
            tokens=tokens,
            tool_calls=tool_calls,
        )
