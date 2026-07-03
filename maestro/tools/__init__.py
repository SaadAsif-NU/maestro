"""Agent tools."""

from __future__ import annotations

from .base import Tool
from .calculator import CalculatorTool
from .search import SearchTool

__all__ = ["Tool", "SearchTool", "CalculatorTool", "default_toolbox"]


def default_toolbox() -> dict[str, Tool]:
    """The tools available to agents, keyed by name."""
    return {tool.name: tool for tool in (SearchTool(), CalculatorTool())}
