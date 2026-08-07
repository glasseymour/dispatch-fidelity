"""Gate — run a project's check command and RECORD what happened. Writer side.

This program writes; `verify.py` reads. They are deliberately separate, because the
failure this package guards against is a checker that inspects its own output. A verifier
that regenerates the evidence it verifies can never report a discrepancy — it replaces
the evidence with whatever it happens to see, then declares the result clean.

What gets recorded:
  * the command, verbatim, and its exit code
  * the FULL raw output, unsummarised, in a separate file
  * a digest of the working tree at the moment the command ran

The tree digest is the load-bearing part. A green result proves nothing unless it came
from the code currently on disk: stale runs, cached results, the wrong branch and the
wrong container all produce genuine, valid output belonging to a different state.

Usage:
    python gate.py -- pytest -q
    python gate.py --label lint -- ruff check .

Exit code mirrors the command's own. Recording happens either way — a failing run is
evidence too.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VERIFY_DIR = ".verify"
SKIP_DIRS = {".git", ".verify", "__pycache__", ".pytest_cache", "node_modules",
             ".venv", "venv", ".mypy_cache", ".ruff_cache", "dist", "build"}


def _git(root: Path, *args):
    """Run git and decode as UTF-8 regardless of the machine's code page.

    Without the explicit encoding, Python decodes with the locale codec. On a Windows
    box set to cp1250 a diff containing any byte outside that page raises inside the
    subprocess reader thread, and the digest silently degrades to the walk path -- a
    quieter, weaker check on exactly the machines least likely to notice.
    """
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
        return out.stdout if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _significant(status: str) -> str:
    """Porcelain lines minus the tooling's own droppings.

    A test run writes .pytest_cache, an import writes __pycache__, and gate.py itself
    writes .verify. Counting those as tree changes makes every recording report that the
    tree moved during the run — a warning that fires always, which is a warning that says
    nothing. Genuinely new source files stay visible.
    """
    keep = []
    for line in status.splitlines():
        path = line[3:].strip().strip('"')
        path = path.split(" -> ")[-1]          # renames report `old -> new`
        parts = path.replace("\\", "/").split("/")
        if any(part in SKIP_DIRS for part in parts):
            continue
        keep.append(line)
    return "\n".join(sorted(keep))


def tree_digest(root: Path) -> dict:
    """Identity of the working tree. Git when available, a file walk otherwise.

    Under git the digest covers HEAD plus the uncommitted delta, so an edited tree is a
    different state from the commit it sits on — which is the state agents actually work in.
    """
    head = _git(root, "rev-parse", "HEAD")
    if head is not None:
        status = _significant(_git(root, "status", "--porcelain") or "")
        diff = _git(root, "diff", "HEAD") or ""
        h = hashlib.sha256((status + "\x00" + diff).encode("utf-8", "replace")).hexdigest()
        return {"method": "git", "head": head.strip(), "dirty": bool(status.strip()),
                "delta_sha256": h}

    h = hashlib.sha256()
    count = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(x in SKIP_DIRS for x in p.relative_to(root).parts):
            continue
        h.update(p.relative_to(root).as_posix().encode())
        h.update(hashlib.sha256(p.read_bytes()).hexdigest().encode())
        count += 1
    return {"method": "walk", "files": count, "delta_sha256": h.hexdigest()}


def main(argv):
    label = "check"
    if argv and argv[0] == "--label":
        label, argv = argv[1], argv[2:]
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print(__doc__.strip().splitlines()[-4])
        print("usage: python gate.py [--label NAME] -- <command> [args...]")
        return 2

    root = Path.cwd()
    outdir = root / VERIFY_DIR
    outdir.mkdir(exist_ok=True)

    before = tree_digest(root)
    proc = subprocess.run(argv, cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    after = tree_digest(root)

    raw = outdir / f"{label}.raw.txt"
    raw.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")

    record = {
        "label": label,
        "command": argv,
        "exit_code": proc.returncode,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "tree_before": before,
        "tree_after": after,
        "tree_changed_during_run": before != after,
        "raw_output": f"{VERIFY_DIR}/{raw.name}",
        "raw_output_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "raw_output_lines": len((proc.stdout or "").splitlines())
                            + len((proc.stderr or "").splitlines()),
    }
    (outdir / f"{label}.run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"[gate] {' '.join(argv)}  ->  exit {proc.returncode}")
    print(f"[gate] raw output : {record['raw_output']}  ({record['raw_output_lines']} lines)")
    print(f"[gate] tree       : {before['method']} {before.get('head', '')[:12]}"
          f"{' +dirty' if before.get('dirty') else ''}")
    if record["tree_changed_during_run"]:
        print("[gate] WARNING: the working tree changed while the command ran — the result "
              "describes no single state")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
