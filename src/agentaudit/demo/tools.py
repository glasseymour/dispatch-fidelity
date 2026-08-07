"""A tiny deterministic toolset for the demo and the validation matrix.

Determinism is the point: every tool returns the same value for the same arguments, so
a claimed result can be checked against the log by exact comparison rather than by
judgement. Real toolsets are not like this, which is why the canary exists -- but for
proving that the SCORER works, a toolset with no ambiguity of its own is what you want.
"""
from __future__ import annotations

import ast
import operator as _op
from datetime import date

_ALLOWED = {ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul,
            ast.Div: _op.truediv, ast.Pow: _op.pow, ast.USub: _op.neg}

_DOCS = {
    "doc-1": "The quick brown fox jumps over the lazy dog.",
    "doc-2": "Instrument failure takes the shape of the hypothesis.",
    "doc-3": "An aggregate that hides its cases hides its errors too.",
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED:
        return _ALLOWED[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED:
        return _ALLOWED[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    """Evaluate a small arithmetic expression. No names, no calls, no attributes."""
    return str(_eval(ast.parse(str(expression), mode="eval").body))


def date_diff(start: str, end: str) -> str:
    """Days from `start` to `end`. Order matters -- swapping them is a different call."""
    a = date.fromisoformat(str(start))
    b = date.fromisoformat(str(end))
    return str((b - a).days)


def doc_lookup(key: str) -> str:
    """Fetch a fixed document by key."""
    return _DOCS.get(str(key), "NOT_FOUND")


def text_stat(text: str) -> str:
    """Word and character count of the given text."""
    t = str(text)
    return f"words={len(t.split())} chars={len(t)}"


TOOLS = {
    "calculator": calculator,
    "date_diff": date_diff,
    "doc_lookup": doc_lookup,
    "text_stat": text_stat,
}

# Declared parameter order, so the scorer can map renamed keys onto roles.
SCHEMA = {
    "calculator": {"params": ["expression"]},
    "date_diff": {"params": ["start", "end"]},
    "doc_lookup": {"params": ["key"]},
    "text_stat": {"params": ["text"]},
    "canary_probe": {"params": ["label"]},
    "canary_checksum": {"params": ["payload"]},
}
