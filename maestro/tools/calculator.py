"""A safe arithmetic calculator tool.

Evaluates arithmetic expressions with an allow-listed AST, never ``eval``. Useful
when an analyst needs a quick, exact number (ratios, growth, payback).
"""

from __future__ import annotations

import ast
import operator

from .base import Tool

_OPS: dict[type[ast.operator], object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        op = _OPS[type(node.op)]
        return op(_eval(node.left), _eval(node.right))  # type: ignore[operator]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand)
    raise ValueError("unsupported expression")


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate an arithmetic expression, e.g. '(120-100)/100'."

    async def run(self, argument: str) -> str:
        try:
            tree = ast.parse(argument, mode="eval")
            result = _eval(tree.body)
        except (SyntaxError, ValueError, ZeroDivisionError):
            return f"Could not evaluate {argument!r}."
        rounded = round(result, 6)
        return f"{argument} = {rounded:g}"
