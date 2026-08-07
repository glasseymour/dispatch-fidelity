"""Adapter for Anthropic-style tool use (`tool_use` content blocks).

Same shape as the OpenAI adapter and the same caveat: a structured `tool_use` block that
your loop executes cannot diverge from what happened. What can diverge is the prose the
model writes about it -- the summary, the hand-off to another agent, the final report.
That text is what the audit scores.
"""
from __future__ import annotations


def execute_tool_use(session, content_blocks, *, agent_id: str = "agent") -> list[dict]:
    """Execute every tool_use block; return tool_result blocks for the next turn."""
    results = []
    for block in content_blocks or []:
        if _get(block, "type") != "tool_use":
            continue
        name = str(_get(block, "name"))
        args = _get(block, "input") or {}
        result = session.call(name, dict(args), agent_id=agent_id)
        results.append({"type": "tool_result", "tool_use_id": _get(block, "id"),
                        "content": result})
    return results


def tool_specs(session, descriptions: dict | None = None) -> list[dict]:
    """Minimal Anthropic tool specs for the session's toolset, canaries included."""
    descriptions = descriptions or {}
    return [{
        "name": name,
        "description": descriptions.get(name, f"Tool {name}."),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": True},
    } for name in session.tool_names]


def final_text(message) -> str:
    """Concatenate the text blocks of a message -- the claim surface to score."""
    blocks = _get(message, "content") or []
    parts = [str(_get(b, "text") or "") for b in blocks if _get(b, "type") == "text"]
    return "\n".join(p for p in parts if p)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
