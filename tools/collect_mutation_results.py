"""Derive mutation_results.json from the raw gauntlet logs — never type the numbers.

Three documents once quoted three different file counts in the deposit, and four sources
quoted four different test counts during the mutation write-up. Same disease, same cure:
the figures that appear in prose are DERIVED from the artifacts that produced them, and
the prose cites this file.

    python tools/collect_mutation_results.py run1.log run2.log run3.log

Each log is parsed for per-target site counts and the full-suite survivor list; the pass
totals, detection percentages and log hashes are computed, not transcribed. The output
lands next to the regime file the score is only interpretable beside.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parent / "mutation_results.json"


def parse(log_path: Path) -> dict:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    sites = {m.group(1): int(m.group(2))
             for m in re.finditer(r"^=== (\S+): (\d+) mutation sites ===", text, re.M)}
    total = sum(sites.values())
    m = re.search(r"^(\d+) mutant\(s\) survive the FULL test suite:", text, re.M)
    survivors = int(m.group(1)) if m else 0
    survivor_list = re.findall(r"^  (\w+\.py: \S+)$",
                               text[text.index(m.group(0)):], re.M) if m else []
    runtime = re.search(r"MUTATION GAUNTLET — ([\d.]+) min", text)
    detected = total - survivors
    return {
        "log_file": log_path.name,
        "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        "sites_per_target": sites,
        "sites_total": total,
        "survivors_full_suite": survivors,
        "detected": detected,
        "detected_pct": round(100.0 * detected / total, 1) if total else None,
        "runtime_min": float(runtime.group(1)) if runtime else None,
        "survivor_list": survivor_list,
    }


def main(argv):
    if not argv:
        print("usage: collect_mutation_results.py <log> [<log> ...]")
        return 2
    passes = [parse(Path(p)) for p in argv]
    result = {
        "schema": "dispatch-fidelity/mutation-results/1",
        "collected": str(date.today()),
        "regime": "tools/mutation_regime.json",
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "note": ("environment recorded at collection time on the machine that ran "
                     "the passes; future passes should record it per run"),
        },
        "note": [
            "Pass 1 ran over the pre-hardening code; the binding coupling hardening",
            "itself added two mutation points, so passes 2 and 3 ran over the larger",
            "site set. Detection percentages are therefore computed against each",
            "pass's own denominator, and the baseline is retained unchanged.",
        ],
        "passes": passes,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    for i, p in enumerate(passes, 1):
        print(f"pass {i}: {p['detected']}/{p['sites_total']} = {p['detected_pct']}% "
              f"detected, {p['survivors_full_suite']} survive")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
