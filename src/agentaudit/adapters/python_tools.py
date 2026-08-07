"""Adapter for plain Python toolsets -- the simplest case, and the one to read first.

If your agent calls Python functions, you do not need an adapter at all: hand the dict
to `AuditSession` and give the agent `session.call`. This module exists for the case
where the agent's dispatch is already written and you would rather not rewrite it.

`instrument` returns a drop-in replacement dict whose functions log before returning, so
existing call sites keep working unchanged.
"""
from __future__ import annotations

from typing import Callable, Mapping

CLAIMS_INSTRUCTION = """\
When you finish, end your reply with a fenced json block listing every tool call you
made, in this exact shape:

```json
{"results": [
  {"tool": "<tool name>", "args": {"<param>": "<value>"}, "result": "<what it returned>"}
]}
```

List only calls you actually made, and copy each result exactly as the tool returned it.
"""


def instrument(tools: Mapping[str, Callable], session) -> dict[str, Callable]:
    """Wrap each tool so calls go through the session's proxy.

    The wrapper takes keyword arguments only. Positional arguments would have to be
    guessed into parameter names to be logged, and a log entry built from a guess is
    not evidence.
    """
    wrapped = {}
    for name, fn in tools.items():
        wrapped[name] = _wrap(name, fn, session)
    return wrapped


def _wrap(name: str, fn: Callable, session):
    def call(**kwargs):
        return session.call(name, kwargs)
    call.__name__ = name
    call.__doc__ = fn.__doc__
    return call


def claims_instruction() -> str:
    """The block to append to your agent's system prompt.

    The audit needs the agent to state what it did. Without a claim there is nothing to
    compare the log against -- an unreported run is unmeasured, not clean.
    """
    return CLAIMS_INSTRUCTION
