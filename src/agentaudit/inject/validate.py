"""Run the validation matrix -- the instrument measuring itself.

Sensitivity  of the deliberate defects, how many were caught
Specificity  of the harmless variations, how many were correctly left alone

Both numbers are needed and neither is sufficient. A checker that flags everything has
perfect sensitivity and is useless; one that flags nothing has perfect specificity and
is worse than useless, because it prints a clean result.

The splice half is separate because it attacks a different surface. It modifies nothing
at all: it takes genuine, unmodified artifacts from two real runs and crosses them. Every
file stays valid, every hash still matches, and the assembled evidence describes a run
that never happened. Only the nonce commitment sees it.
"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..demo import mock_agent
from ..fidelity.binding import check_binding
from ..fidelity.proxy import load_log
from ..fidelity.scorer import score
from .classes import CLASSES


@dataclass
class Row:
    key: str
    kind: str
    title: str
    expected: str
    observed: str
    passed: bool
    note: str = ""


def _run_claim_matrix(work: Path) -> list[Row]:
    session, report = mock_agent.faithful_artifacts(run_dir=work, run_id="matrix-base")
    records = load_log(session.log_path)
    nonce = session._nonce  # the matrix is the one caller allowed to know it
    rows = []
    for cls in CLASSES:
        mutated = cls.mutate(report)
        s = score(mutated, records, nonce, session.schema)
        detected = s.fabricated > 0
        if cls.kind == "positive":
            expected, passed = "flagged", detected
            observed = f"{s.fabricated} flagged" if detected else "MISSED"
        else:
            expected, passed = "silent", not detected
            observed = "silent" if not detected else f"FALSE ALARM ({s.fabricated})"
        rows.append(Row(cls.key, cls.kind, cls.title, expected, observed, passed,
                        cls.rationale))
    return rows


def _run_splice_matrix(work: Path) -> list[Row]:
    a, _ = mock_agent.faithful_artifacts(run_dir=work, run_id="splice-a")
    b, _ = mock_agent.faithful_artifacts(run_dir=work, run_id="splice-b")
    rows = []

    intact = check_binding(a.manifest_path, a.log_path)
    rows.append(Row("X0", "negative", "matched manifest and log", "bound",
                    "bound" if intact.bound else "FALSE ALARM", intact.bound,
                    "an unspliced run must never raise the alarm"))

    crossed = work / "crossed"
    crossed.mkdir(exist_ok=True)
    shutil.copy(a.manifest_path, crossed / "splice-a.manifest.json")
    shutil.copy(b.log_path, crossed / "splice-a.toollog.jsonl")
    r = check_binding(crossed / "splice-a.manifest.json", crossed / "splice-a.toollog.jsonl")
    rows.append(Row("X1", "positive", "tool log from another run", "flagged",
                    "flagged" if not r.bound else "MISSED", not r.bound,
                    "every record genuine, every hash valid, wrong run"))

    crossed2 = work / "crossed2"
    crossed2.mkdir(exist_ok=True)
    shutil.copy(b.manifest_path, crossed2 / "splice-b.manifest.json")
    shutil.copy(a.log_path, crossed2 / "splice-b.toollog.jsonl")
    r2 = check_binding(crossed2 / "splice-b.manifest.json", crossed2 / "splice-b.toollog.jsonl")
    rows.append(Row("X2", "positive", "manifest from another run", "flagged",
                    "flagged" if not r2.bound else "MISSED", not r2.bound,
                    "the pre-run commitment cannot be relabelled"))
    return rows


def run(verbose: bool = True) -> tuple[list[Row], bool]:
    work = Path(tempfile.mkdtemp(prefix="agentaudit-matrix-"))
    try:
        rows = _run_claim_matrix(work) + _run_splice_matrix(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    pos = [r for r in rows if r.kind == "positive"]
    neg = [r for r in rows if r.kind == "negative"]
    sens = sum(r.passed for r in pos)
    spec = sum(r.passed for r in neg)
    ok = sens == len(pos) and spec == len(neg)

    if verbose:
        bar = "=" * 74
        print(bar)
        print("VALIDATION MATRIX -- the instrument measured against known defects")
        print(bar)
        for r in rows:
            mark = "ok  " if r.passed else "FAIL"
            print(f"  [{mark}] {r.key:3s} {r.title:42s} {r.observed}")
            if not r.passed:
                print(f"         expected {r.expected} -- {r.note}")
        print()
        print(f"  sensitivity : {sens}/{len(pos)}   (deliberate defects caught)")
        print(f"  specificity : {spec}/{len(neg)}   (harmless variations left alone)")
        print()
        print(bar)
        print("INSTRUMENT VALIDATED" if ok else
              "INSTRUMENT NOT VALIDATED -- do not trust its clean results")
        print(bar)
    return rows, ok
