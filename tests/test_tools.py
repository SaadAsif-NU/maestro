from __future__ import annotations

from maestro.tools import CalculatorTool, SearchTool, default_toolbox


async def test_search_returns_relevant_passages():
    tool = SearchTool()
    result = await tool.run("go-to-market strategy for SaaS")
    assert "beachhead" in result or "retention" in result


async def test_search_empty_query():
    assert (await SearchTool().run("")) == "No query provided."


async def test_search_no_matches():
    result = await SearchTool().run("zzzqqq nonsense token")
    assert "No direct matches" in result


async def test_calculator_arithmetic():
    tool = CalculatorTool()
    assert (await tool.run("2 + 3 * 4")).endswith("= 14")
    assert (await tool.run("(120-100)/100")).endswith("= 0.2")


async def test_calculator_rejects_unsafe_input():
    tool = CalculatorTool()
    assert "Could not evaluate" in await tool.run("__import__('os').system('ls')")
    assert "Could not evaluate" in await tool.run("1/0")


def test_default_toolbox():
    box = default_toolbox()
    assert set(box) == {"search", "calculator"}
