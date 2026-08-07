"""Adapter for OpenAI-style tool calling (`tool_calls` on the assistant message).

Where the fabrication actually lives in this shape is worth being precise about. When a
model emits a structured `tool_calls` entry and your loop executes it, claim and
execution cannot diverge -- the call IS the claim. The gap opens one level up:

  * the model's final NL summary of what it did, which users and downstream agents read
  * a sub-agent reporting to an orchestrator in prose
  * a report assembled after the fact from memory rather than from the transcript

So this adapter routes execution through the proxy, and the audit scores the model's
final text. If your system has no such text, it has no dispatch-fidelity surface in the
first place, and the honest answer is that you do not need this tool for that path.
"""
from __future__ import annotations

import json


def execute_tool_calls(session, assistant_message: dict, *, agent_id: str = "agent") -> list[dict]:
    """Execute every tool call on an assistant message; return `tool` role messages.

    Accepts both dicts and SDK objects exposing the same attributes.
    """
    calls = _get(assistant_message, "tool_calls") or []
    out = []
    for call in calls:
        fn = _get(call, "function") or {}
        name = _get(fn, "name")
        raw = _get(fn, "arguments") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except json.JSONDecodeError:
            args = {"_unparsed_arguments": str(raw)}
        result = session.call(str(name), args, agent_id=agent_id)
        out.append({"role": "tool", "tool_call_id": _get(call, "id"),
                    "name": name, "content": result})
    return out


def tool_specs(session, descriptions: dict | None = None) -> list[dict]:
    """Minimal OpenAI tool specs for the session's toolset, canaries included.

    The canary is offered to the agent as an ordinary tool on purpose. An agent told
    which call is the tripwire is being tested on a different question.
    """
    descriptions = descriptions or {}
    specs = []
    for name in session.tool_names:
        specs.append({
            "type": "function",
            "function": {
                "name": name,
                "description": descriptions.get(name, f"Tool {name}."),
                "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
            },
        })
    return specs


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
