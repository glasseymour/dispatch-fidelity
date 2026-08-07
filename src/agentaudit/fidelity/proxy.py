"""The logging proxy -- the ground-truth side of the measurement.

Every real tool call passes through `LoggingProxy.call`, which appends an immutable
JSONL record BEFORE the result goes back to the agent. The log is written first on
purpose: a record written afterwards can be lost exactly when the run misbehaves, and
the interesting runs are the ones that misbehave.

The proxy is deliberately dumb. It does not know what an agent is, what a model is, or
what the tools mean. It knows how to call a callable and how to append a line. Anything
smarter here would be a second place where the evidence could be shaped.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

MAX_RESULT_CHARS = 100_000


class LoggingProxy:
    """Wrap a set of callables; log every invocation to `<run_id>.toollog.jsonl`.

    `tools` may be a mapping of name -> callable, or any object whose public attributes
    are callables. Names starting with an underscore are never reachable.
    """

    def __init__(self, tools: Mapping[str, Callable] | Any, run_id: str, log_dir: Path):
        self._tools = _as_mapping(tools)
        self._run_id = run_id
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path = log_dir / f"{run_id}.toollog.jsonl"
        self._seq = 0

    @property
    def log_path(self) -> Path:
        return self._path

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._tools)

    def call(self, tool: str, args: dict | None = None, *, agent_id: str = "agent") -> str:
        """Execute `tool` and record it. Returns the result as a string.

        Errors are returned as a deterministic string rather than raised. An exception
        that escapes here would leave the run with an unlogged call, which is precisely
        the state the instrument must never be in.
        """
        args = dict(args or {})
        fn = self._tools.get(tool)
        if fn is None or tool.startswith("_"):
            result = f"ERROR:unknown_tool:{tool}"
        else:
            try:
                result = fn(**args)
            except Exception as exc:
                result = f"ERROR:{type(exc).__name__}"
        text = str(result)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + f"...[truncated {len(text)} chars]"

        self._seq += 1
        record = {
            "seq": self._seq,
            "run_id": self._run_id,
            "agent_id": agent_id,
            "tool": tool,
            "args": args,
            "result": text,
            "result_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "ts": datetime.now(timezone.utc).isoformat(),
            "monotonic": time.monotonic(),
        }
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return text


def _as_mapping(tools) -> dict[str, Callable]:
    if isinstance(tools, Mapping):
        return {str(k): v for k, v in tools.items() if not str(k).startswith("_")}
    out = {}
    for name in dir(tools):
        if name.startswith("_"):
            continue
        attr = getattr(tools, name)
        if callable(attr):
            out[name] = attr
    return out


def load_log(path: Path) -> list[dict]:
    """Read a tool log. Malformed lines are skipped and counted by the caller if needed."""
    path = Path(path)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
