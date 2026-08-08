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
import threading
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
        # Finding #29. `self._seq += 1` is a read-modify-write, and the append was a
        # separate open-write-close per call. Under concurrency that loses EXECUTED
        # CALLS outright: measured against LangGraph's ToolNode, which runs the tool
        # calls of one message in parallel on separate threads, 13 of 20 runs dropped
        # records from a 64-call batch — up to three at a time.
        #
        # The sequence number and the write live under one lock, so a record's number
        # and its line cannot be produced by different interleavings.
        #
        # ONE handle, opened once, not one open-append-close per call. The first fix
        # kept per-call opens under the lock and still lost lines on Windows: 64
        # serialized open-write-close cycles left 60 lines in the file, with every
        # call() returning success. Whatever the OS-level mechanism (delayed metadata
        # on rapidly reopened append handles is the usual suspect), the defence is to
        # stop doing the thing: a single handle plus an explicit flush per record.
        self._lock = threading.Lock()
        self._fh = open(self._path, "a", encoding="utf-8")

    @property
    def log_path(self) -> Path:
        return self._path

    def close(self) -> None:
        with self._lock:
            if not self._fh.closed:
                self._fh.close()

    def __del__(self):  # best-effort; close() is the real contract
        try:
            self.close()
        except Exception:
            pass

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

        # Sequence assignment and the write happen under ONE lock acquisition, so a
        # record's number and its line cannot come from different interleavings — and
        # the write goes to the single shared handle, never a fresh open. Composing the
        # record inside the lock costs a few microseconds of serialization and buys the
        # property the evidence layer exists for: every executed call has a line.
        with self._lock:
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
            self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._fh.flush()
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


class ToolLog(list):
    """The records, plus what could not be read.

    A plain list was the original return type and it silently dropped malformed lines.
    That is finding #20: a corrupted last line vanishes without a trace, the surviving
    prefix stays gap-free, and every downstream check reports a clean run over evidence
    that is missing a piece. A middle line usually shows up as a sequence gap; the last
    one does not show up at all.

    An audit log reader has to be fail-closed. This subclass keeps every existing caller
    working -- it iterates and indexes like the list it replaced -- while carrying the
    damage forward so a caller cannot fail to see it.
    """

    def __init__(self, records=(), malformed=(), total_lines=0, path=None):
        super().__init__(records)
        self.malformed = list(malformed)     # 1-based line numbers
        self.total_lines = total_lines
        self.path = path

    @property
    def intact(self) -> bool:
        return not self.malformed

    def findings(self) -> list[str]:
        if not self.malformed:
            return []
        shown = ", ".join(str(n) for n in self.malformed[:8])
        more = "" if len(self.malformed) <= 8 else f" (+{len(self.malformed) - 8} more)"
        return [f"tool log has {len(self.malformed)} unreadable line(s) at {shown}{more} "
                f"-- the evidence is incomplete, so no result over it is conclusive"]


def load_log(path: Path) -> ToolLog:
    """Read a tool log, keeping a record of every line that could not be parsed."""
    path = Path(path)
    if not path.exists():
        return ToolLog(path=path)
    records, malformed = [], []
    lines = path.read_text(encoding="utf-8").splitlines()
    for n, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            malformed.append(n)
    return ToolLog(records, malformed, len(lines), path)
