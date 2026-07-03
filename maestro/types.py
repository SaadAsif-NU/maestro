"""Core value types for runs, tasks, agents, and results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    ORCHESTRATOR = "orchestrator"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    CRITIC = "critic"
    WRITER = "writer"

    @property
    def label(self) -> str:
        return self.value.capitalize()


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    USING_TOOL = "using_tool"
    DONE = "done"
    ERROR = "error"


class Task(BaseModel):
    """A unit of work assigned to a worker agent."""

    id: str
    role: Role
    title: str
    prompt: str


class ToolCall(BaseModel):
    tool: str
    argument: str
    result: str


class AgentResult(BaseModel):
    agent_id: str
    role: Role
    title: str
    content: str
    tokens: int = 0
    tool_calls: list[ToolCall] = Field(default_factory=list)


class RunRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=2000)
    researchers: int = Field(default=2, ge=1, le=4)


class RunSummary(BaseModel):
    run_id: str
    goal: str
    status: RunStatus
    deliverable: str | None = None
    total_tokens: int = 0
    total_tool_calls: int = 0
    elapsed_ms: float = 0.0
    agents: int = 0
