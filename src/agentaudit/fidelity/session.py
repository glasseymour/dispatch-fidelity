"""AuditSession -- the one object most users need.

The whole audit is four moves:

    session = AuditSession(tools={"search": my_search})   # 1. seal a run
    result  = run_my_agent(session.call)                  # 2. let the agent use the proxy
    score   = session.score(result)                       # 3. score its report
    print(session.report())                               # 4. read the verdict

Everything else in this package is either a detail of those four or a way to prove that
step 3 works. The session owns the run id, the nonce, the manifest, the proxy and the
canary tools, so a caller cannot accidentally build a run whose evidence does not bind.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .binding import BindingResult, check_binding
from .canary import CanaryTools
from .nonce import new_nonce, seal_manifest
from .proxy import LoggingProxy, load_log
from .outcome import Outcome, decide
from .report import render
from .scorer import DispatchScore, score

DEFAULT_DIR = Path("audit_runs")


class AuditSession:
    """One measured run of one agentic system."""

    def __init__(self, tools: Mapping[str, Callable] | Any = None, *,
                 run_dir: Path | str = DEFAULT_DIR, run_id: str | None = None,
                 task_id: str | None = None, system: dict | None = None,
                 schema: dict | None = None, with_canary: bool = True,
                 strict_results: bool = False):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
        self.task_id = task_id
        self.schema = schema or {}
        self.strict_results = strict_results
        self._nonce = new_nonce()
        self._canary = CanaryTools(self._nonce)

        toolset = dict(_normalise(tools))
        if with_canary:
            toolset.update(self._canary.as_dict())
        self._toolset = toolset

        # Sealed BEFORE anything runs. A manifest written afterwards can be made to
        # agree with whatever happened, which is the opposite of a commitment.
        self.manifest_path = seal_manifest(
            self.run_id, self._nonce, self.run_dir, system=system, task_id=task_id
        )
        self.proxy = LoggingProxy(toolset, self.run_id, self.run_dir)
        self._score: DispatchScore | None = None
        self._binding: BindingResult | None = None
        self._log = None
        self._outcome: Outcome | None = None

    # -- the agent-facing surface ------------------------------------------------
    def call(self, tool: str, args: dict | None = None, *, agent_id: str = "agent") -> str:
        """Hand this to the agent as its only route to a tool."""
        return self.proxy.call(tool, args, agent_id=agent_id)

    @property
    def tool_names(self) -> list[str]:
        return self.proxy.tool_names

    @property
    def log_path(self) -> Path:
        return self.proxy.log_path

    def tool_descriptions(self) -> str:
        """A block you can paste into the agent's system prompt."""
        lines = [f"- {name}" for name in self.tool_names]
        return "\n".join(lines)

    # -- scoring -----------------------------------------------------------------
    def score(self, report: str) -> DispatchScore:
        """Score the agent's final report against the log this session recorded."""
        records = load_log(self.log_path)
        self._log = records
        self._score = score(report, records, self._nonce, self.schema,
                            strict_results=self.strict_results)
        self._binding = check_binding(self.manifest_path, self.log_path)
        self._outcome = decide(self._score, self._binding, records)
        (self.run_dir / f"{self.run_id}.score.json").write_text(
            json.dumps(
                {"run_id": self.run_id,
                 "scored_at": datetime.now(timezone.utc).isoformat(),
                 "score": self._score.to_dict(),
                 "binding": self._binding.to_dict(),
                 "outcome": self._outcome.to_dict()},
                indent=2, ensure_ascii=False),
            encoding="utf-8")
        return self._score

    @property
    def binding(self) -> BindingResult | None:
        return self._binding

    @property
    def outcome(self) -> Outcome | None:
        """PASS / FAIL / INCONCLUSIVE, and the exit code a gate should use."""
        return self._outcome

    def report(self) -> str:
        if self._score is None:
            return "No score yet -- call session.score(agent_report) first."
        return render(self.run_id, self._score, self._binding, self._log)


def _normalise(tools) -> dict:
    if tools is None:
        return {}
    if isinstance(tools, Mapping):
        return {str(k): v for k, v in tools.items()}
    return {n: getattr(tools, n) for n in dir(tools)
            if not n.startswith("_") and callable(getattr(tools, n))}
