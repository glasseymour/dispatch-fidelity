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
        evidence = cls.mutate_log(list(records)) if cls.mutate_log else records
        s = score(mutated, evidence, nonce, session.schema,
                  strict_results=cls.strict)
        detected = s.value_integrity_failures > 0
        if cls.kind == "positive":
            expected, passed = "flagged", detected
            observed = f"{s.value_integrity_failures} flagged" if detected else "MISSED"
        else:
            expected, passed = "silent", not detected
            observed = "silent" if not detected else f"FALSE ALARM ({s.value_integrity_failures})"
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


def _run_gate_matrix(work: Path) -> list[Row]:
    """The machine boundary, measured like everything else.

    Findings #17-#20 were all one shape: the report said NOT CLEAN and the exit code
    said 0. Nothing in the earlier matrix looked at exit codes, so nothing caught it.
    These rows do, because a verdict that only exists on screen is not a gate.
    """
    import json

    from ..fidelity.outcome import decide
    from ..fidelity.scorer import score

    rows = []

    def row(key, kind, title, expected_code, actual_code, note):
        rows.append(Row(key, kind, title, f"exit {expected_code}", f"exit {actual_code}",
                        expected_code == actual_code, note))

    session, report = mock_agent.faithful_artifacts(run_dir=work, run_id="gate-clean")
    records = load_log(session.log_path)
    nonce = session._nonce
    binding = check_binding(session.manifest_path, session.log_path)
    clean = decide(score(report, records, nonce, session.schema), binding, records)
    row("G0", "negative", "clean run passes the gate", 0, clean.exit_code,
        "a gate that never passes gets switched off")

    sub_session, sub_report = mock_agent.run("substituting", run_dir=work,
                                             run_id="gate-substituting")
    sub_records = load_log(sub_session.log_path)
    sub = decide(score(sub_report, sub_records, sub_session._nonce, sub_session.schema),
                 check_binding(sub_session.manifest_path, sub_session.log_path),
                 sub_records)
    row("G1", "positive", "SUBSTITUTED reaches the exit code", 1, sub.exit_code,
        "finding #17: scored, printed, and left out of the gate")

    empty = report + "\n```json\n" + json.dumps({"results": []}) + "\n```\n"
    unmeasured = decide(score(empty, records, nonce, session.schema), binding, records)
    row("G2", "positive", "unmeasured run is not a pass", 2, unmeasured.exit_code,
        "finding #18: the last results block wins, so an empty one is a bypass")

    stripped = [r for r in records if not str(r.get("tool", "")).startswith("canary")]
    for i, rec in enumerate(stripped, 1):
        rec["seq"] = i
    nocanary = work / "gate-nocanary.toollog.jsonl"
    nocanary.write_text("\n".join(json.dumps(r) for r in stripped) + "\n", encoding="utf-8")
    unproven = check_binding(session.manifest_path, nocanary)
    row("G3", "positive", "unprovable binding is not BOUND", 2,
        {"PROVEN": 0, "FAILED": 1, "UNPROVEN": 2}[unproven.status],
        "finding #19: `bound` used to mean 'no explicit finding'")

    corrupt = work / "gate-corrupt.toollog.jsonl"
    corrupt.write_text(session.log_path.read_text(encoding="utf-8") + "{not json\n",
                       encoding="utf-8")
    damaged = load_log(corrupt)
    torn = decide(score(report, damaged, nonce, session.schema), binding, damaged)
    row("G4", "positive", "an unreadable log line is not a pass", 2, torn.exit_code,
        "finding #20: a corrupt last line left no trace at all")

    # G5 and G6 exist because G0-G4 measured this module's own composition rather than
    # the paths a user actually takes. G4 handed `decide` a binding computed from the
    # INTACT log while corrupting only the copy the scorer saw -- so the CLI, where the
    # damaged log goes into both, was never covered. Findings #24 and #25 both live in
    # that gap. A matrix that tests its own convenience wiring proves nothing about the
    # command someone runs.
    unchecked = decide(score(report, records, nonce, session.schema), None, records)
    row("G5", "positive", "binding never checked is not a pass", 2, unchecked.exit_code,
        "finding #25: --manifest is optional, and its absence was read as proof")

    torn_binding = check_binding(session.manifest_path, corrupt)
    both = decide(score(report, damaged, nonce, session.schema), torn_binding, damaged)
    row("G6", "positive", "torn log stays inconclusive with a manifest", 2, both.exit_code,
        "finding #24: damaged evidence became FAIL once a manifest was supplied")

    return rows


def run(verbose: bool = True) -> tuple[list[Row], bool]:
    work = Path(tempfile.mkdtemp(prefix="dispatch-fidelity-matrix-"))
    try:
        rows = _run_claim_matrix(work) + _run_splice_matrix(work) + _run_gate_matrix(work)
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
        print("KNOWN FAILURE-CLASS REGRESSION MATRIX PASSED" if ok else
              "REGRESSION MATRIX FAILED -- do not trust this instrument's clean results")
        print(bar)
    return rows, ok
