"""Self-test — the package's own regression guards.

Six behaviours, each one the reason a check exists. A checker nobody exercises is a
checker nobody knows the state of; these assertions are what keep this package from
becoming decoration.

Hermetic: builds a throwaway git repo in a temp directory and uses trivial commands, so
it needs neither pytest nor a network. Requires git on PATH.

Usage:  py -3.12 selftest.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import os

HERE = Path(__file__).resolve().parent
SRC_ROOT = HERE.parent.parent                     # .../src, so `-m agentaudit...` resolves
PY = [sys.executable]
PASS_CMD = PY + ["-c", "print('2 passed')"]


def _env():
    """Make the package importable in the subprocess even from a source checkout."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_ROOT) + (os.pathsep + existing if existing else "")
    return env


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=_env())


def gate(cwd, cmd=None):
    return run(PY + ["-m", "agentaudit.evidence.gate", "--label", "tests", "--",
                     *(cmd or PASS_CMD)], cwd)


def verify(cwd):
    return run(PY + ["-m", "agentaudit.evidence.verify"], cwd)


def expect(case, cond, detail=""):
    mark = "ok  " if cond else "FAIL"
    print(f"  [{mark}] {case}" + (f"\n         {detail}" if not cond and detail else ""))
    return bool(cond)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="agent-verify-selftest-"))
    ok = True
    try:
        (tmp / "src.py").write_text("import os  # noqa\n\n\ndef f():\n    return 1\n",
                                    encoding="utf-8")
        (tmp / "ANCHOR.txt").write_text(
            f'green | "{sys.executable}" -c "print(\'2 passed\')" | 2 passed\n', encoding="utf-8")
        (tmp / "waivers.txt").write_text("", encoding="utf-8")
        for args in (["init", "-q", "."], ["config", "user.email", "t@t"],
                     ["config", "user.name", "t"], ["add", "-A"],
                     ["commit", "-qm", "init"]):
            run(["git", *args], tmp)

        print("evidence discipline self-test\n")

        # 1 — an unrecorded check is a claim, not evidence
        r = verify(tmp)
        ok &= expect("no recording -> NOT VERIFIED", r.returncode == 1 and "BINDING" in r.stdout)

        # 2 — an undeclared suppression is a finding
        gate(tmp)
        r = verify(tmp)
        ok &= expect("undeclared suppression -> finding",
                     r.returncode == 1 and "undeclared suppression" in r.stdout, r.stdout[-200:])

        # 3 — declared, everything aligned -> pass
        (tmp / "waivers.txt").write_text(
            "src.py | noqa on the unused import; kept as the module's public re-export.\n",
            encoding="utf-8")
        gate(tmp)
        r = verify(tmp)
        ok &= expect("clean path -> VERIFIED", r.returncode == 0 and "VERIFIED" in r.stdout,
                     r.stdout[-300:])

        # 4 — editing after the recording makes the green belong to another tree
        (tmp / "src.py").write_text("import os  # noqa\n\n\ndef f():\n    return 2\n",
                                    encoding="utf-8")
        r = verify(tmp)
        ok &= expect("edit after recording -> STALE",
                     r.returncode == 1 and "STALE" in r.stdout, r.stdout[-200:])

        # 5 — re-running restores the binding but must NOT launder a broken anchor
        (tmp / "ANCHOR.txt").write_text(
            f'green | "{sys.executable}" -c "print(\'2 passed\')" | 7 passed\n', encoding="utf-8")
        gate(tmp)
        r = verify(tmp)
        ok &= expect("re-run cannot pass a broken anchor",
                     r.returncode == 1 and "[ANCHOR]" in r.stdout and "STALE" not in r.stdout,
                     r.stdout[-260:])

        # 6 — a declaration that outlived its suppression is itself a finding
        (tmp / "ANCHOR.txt").write_text(
            f'green | "{sys.executable}" -c "print(\'2 passed\')" | 2 passed\n', encoding="utf-8")
        (tmp / "src.py").write_text("def f():\n    return 2\n", encoding="utf-8")
        gate(tmp)
        r = verify(tmp)
        ok &= expect("stale declaration -> finding",
                     r.returncode == 1 and "STALE declaration" in r.stdout, r.stdout[-200:])

        # 7 — a failing command is recorded, and refuses to verify
        gate(tmp, PY + ["-c", "import sys; sys.exit(3)"])
        r = verify(tmp)
        ok &= expect("failing run -> refuses to verify",
                     r.returncode == 1 and "recorded run FAILED" in r.stdout, r.stdout[-200:])

        print("\n" + ("ALL GUARDS HOLD" if ok else "SELF-TEST FAILED"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
