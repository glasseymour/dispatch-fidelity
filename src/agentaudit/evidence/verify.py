"""Verify — READ-ONLY, fail-closed. Reader side.

Three checks, each closing a gap that a green aggregate cannot see:

  BINDING   the recorded run came from the code currently on disk, and it passed.
            A result belonging to another tree state is genuine and irrelevant.
  ANCHORS   numbers fixed BEFORE the change still hold. An anchor is a commitment made
            while the answer was unknown; re-reading the output just produced is not
            verification.
  WAIVERS   every suppression in the codebase (skip, xfail, ignore, disable) is declared
            with a written reason. An undeclared exception looks identical whether it was
            deliberate or an accident.

This program writes nothing. `gate.py` is the only writer. Exit 0 means, and only means:
every applicable check passed.

Usage:
    python verify.py                 # all checks, every recorded label
    python verify.py --label tests   # binding for one label only
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:                                     # installed package
    from .gate import tree_digest
except ImportError:                      # run directly as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gate import tree_digest  # noqa: E402  -- one definition of tree identity, not two

ROOT = Path.cwd()
VERIFY_DIR = ROOT / ".verify"
ANCHORS = ROOT / "ANCHOR.txt"
WAIVERS = ROOT / "waivers.txt"

# Suppression markers. Each hit must be declared in waivers.txt or it is a finding.
SUPPRESSIONS = [
    (re.compile(r"@pytest\.mark\.(skip|xfail)"), "pytest skip/xfail"),
    (re.compile(r"#\s*type:\s*ignore"), "mypy ignore"),
    (re.compile(r"#\s*noqa"), "lint noqa"),
    (re.compile(r"eslint-disable"), "eslint disable"),
    (re.compile(r"@ts-(ignore|expect-error)"), "typescript ignore"),
    (re.compile(r"\.only\s*\("), "focused test (.only)"),
]
SCAN_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs"}
SKIP_DIRS = {".git", ".verify", "__pycache__", ".pytest_cache", "node_modules",
             ".venv", "venv", ".mypy_cache", ".ruff_cache", "dist", "build"}


def parse_declared(path):
    """key -> reason, from a `key | reason` file with # comments."""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, reason = line.partition("|")
        out[key.strip()] = reason.strip() or "(no reason given)"
    return out


def check_binding(findings, only=None):
    records = sorted(VERIFY_DIR.glob("*.run.json")) if VERIFY_DIR.is_dir() else []
    if only:
        records = [p for p in records if p.name == f"{only}.run.json"]
    if not records:
        findings.append(("BINDING", "no recorded run — run gate.py before verifying. "
                                    "An unrecorded check is a claim, not evidence."))
        return 0, 0

    current = tree_digest(ROOT)
    ok = 0
    for p in records:
        rec = json.loads(p.read_text(encoding="utf-8"))
        label = rec.get("label", p.stem)
        raw = ROOT / rec.get("raw_output", "")
        if rec.get("exit_code") != 0:
            findings.append(("BINDING", f"{label}: the recorded run FAILED "
                                        f"(exit {rec.get('exit_code')}); see {rec.get('raw_output')}"))
            continue
        if rec.get("tree_changed_during_run"):
            findings.append(("BINDING", f"{label}: the tree changed while the command ran — "
                                        f"the result describes no single state"))
            continue
        if rec.get("tree_before") != current:
            findings.append(("BINDING", f"{label}: STALE — recorded against a different tree "
                                        f"state than the one on disk now"))
            continue
        if not raw.exists():
            findings.append(("BINDING", f"{label}: raw output missing ({rec.get('raw_output')})"))
            continue
        ok += 1
    return ok, len(records)


def check_anchors(findings):
    """Each anchor: name | shell command | expected substring, fixed before the change."""
    declared = parse_declared(ANCHORS)
    if not declared:
        return 0, 0
    ok = 0
    for name, spec in declared.items():
        cmd, _, expected = spec.rpartition("|")
        cmd, expected = cmd.strip(), expected.strip()
        if not cmd:
            findings.append(("ANCHOR", f"{name}: malformed — expected `name | command | value`"))
            continue
        try:
            proc = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=600)
        except subprocess.SubprocessError as exc:
            findings.append(("ANCHOR", f"{name}: command failed to run ({exc})"))
            continue
        got = (proc.stdout or "") + (proc.stderr or "")
        if expected in got:
            ok += 1
        else:
            tail = " / ".join(got.strip().splitlines()[-2:])[:110]
            findings.append(("ANCHOR", f"{name}: expected {expected!r}, not present. "
                                       f"Last output: {tail}"))
    return ok, len(declared)


def check_waivers(findings):
    declared = parse_declared(WAIVERS)
    hits = {}
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.suffix not in SCAN_EXT:
            continue
        if any(x in SKIP_DIRS for x in p.relative_to(ROOT).parts):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for rx, kind in SUPPRESSIONS:
                if rx.search(line):
                    hits.setdefault(p.relative_to(ROOT).as_posix(), []).append((i, kind))
    for rel, found in sorted(hits.items()):
        if rel not in declared:
            kinds = ", ".join(sorted({k for _, k in found}))
            lines = ", ".join(str(i) for i, _ in found[:6])
            findings.append(("WAIVER", f"undeclared suppression in {rel} ({kinds}; "
                                       f"line {lines}) — name it in waivers.txt with a reason"))
    for rel in sorted(declared):
        if rel not in hits:
            findings.append(("WAIVER", f"STALE declaration: {rel} carries no suppression any "
                                       f"more — remove it from waivers.txt"))
    return len(hits), len(declared)


def main(argv):
    only = None
    if len(argv) >= 2 and argv[0] == "--label":
        only = argv[1]

    findings = []
    b_ok, b_total = check_binding(findings, only)
    a_ok, a_total = check_anchors(findings)
    w_found, w_declared = check_waivers(findings)

    print("=" * 74)
    print("VERIFY — read-only, fail-closed")
    print("=" * 74)
    print(f"  recorded runs bound to this tree : {b_ok} / {b_total}")
    print(f"  anchors holding                  : {a_ok} / {a_total}"
          f"{'   (no ANCHOR.txt)' if not a_total else ''}")
    print(f"  suppressions found / declared    : {w_found} / {w_declared}")

    if findings:
        print(f"\n--- {len(findings)} FINDING(S) ---")
        for kind, msg in findings:
            print(f"  [{kind}] {msg}")
        print("\nNOT VERIFIED")
        return 1

    print("\nVERIFIED — the recorded runs came from this tree, the anchors hold, "
          "and every suppression is declared")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
