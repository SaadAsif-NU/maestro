"""Maestro, a live multi-agent orchestration studio.

Programmatic use::

    import asyncio
    from maestro import Engine

    engine = Engine()
    summary = asyncio.run(engine.run_to_completion("Design a launch plan for X"))
    print(summary.deliverable)
"""

from __future__ import annotations

from .agents import Agent
from .brains import Brain, SimulatedBrain, build_brain
from .engine import Engine, RunHandle
from .events import Event, EventBus
from .orchestrator import Orchestrator
from .tools import CalculatorTool, SearchTool, Tool, default_toolbox
from .types import (
    AgentResult,
    AgentStatus,
    Role,
    RunRequest,
    RunStatus,
    RunSummary,
    Task,
)

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentResult",
    "AgentStatus",
    "Brain",
    "CalculatorTool",
    "Engine",
    "Event",
    "EventBus",
    "Orchestrator",
    "Role",
    "RunHandle",
    "RunRequest",
    "RunStatus",
    "RunSummary",
    "SearchTool",
    "SimulatedBrain",
    "Task",
    "Tool",
    "build_brain",
    "default_toolbox",
    "__version__",
]
