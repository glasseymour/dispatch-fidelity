"""The documentation is a machine boundary too.

Findings #27 and #28, and they are the same family as #17–#20: a number that a human
reads diverging from the number a machine checks.

`ANCHOR.txt` held `sensitivity : 17/17` and the README held `15/15`. The anchor matches
the tool's own output, so `dispatch-audit verify` stayed green while the front page of
the project was wrong. The gate was not looking at what the reader looks at.

Fixing the two numbers would have fixed nothing. These tests draw the boundary instead:
figures quoted in prose are checked against the run that produces them, and the citation
metadata is checked against the release it claims to describe. A number nobody re-derives
is a number that drifts, and this project has a protocol section about that.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

from dispatch_fidelity import __version__
from dispatch_fidelity.inject import validate

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
CITATION = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
ANCHORS = (ROOT / "ANCHOR.txt").read_text(encoding="utf-8")

WORDS = {7: "seven", 10: "ten", 11: "eleven", 17: "seventeen",
         26: "twenty-six", 28: "twenty-eight"}


@pytest.fixture(scope="module")
def matrix():
    rows, ok = validate.run(verbose=False)
    assert ok, "the matrix must be green before its figures mean anything"
    pos = [r for r in rows if r.kind == "positive"]
    neg = [r for r in rows if r.kind == "negative"]
    return {"cases": len(rows), "sensitivity": len(pos), "specificity": len(neg)}


def test_readme_quotes_the_matrix_figures_the_tool_produces(matrix):
    sens = re.search(r"sensitivity\s*:\s*(\d+)/(\d+)", README)
    spec = re.search(r"specificity\s*:\s*(\d+)/(\d+)", README)
    assert sens and spec, "the README must quote both figures or neither"
    assert sens.group(1) == sens.group(2) == str(matrix["sensitivity"])
    assert spec.group(1) == spec.group(2) == str(matrix["specificity"])


def test_readme_case_count_matches_the_matrix(matrix):
    word = WORDS[matrix["cases"]]
    assert re.search(rf"\b{word}\b", README, re.I), (
        f"the README should say {word} cases; the matrix has {matrix['cases']}")


def test_anchor_figures_match_the_matrix(matrix):
    assert f"sensitivity : {matrix['sensitivity']}/{matrix['sensitivity']}" in ANCHORS
    assert f"specificity : {matrix['specificity']}/{matrix['specificity']}" in ANCHORS


def test_readme_and_anchors_cannot_disagree(matrix):
    """The specific shape of #27: both were checked, against different things."""
    readme = re.search(r"sensitivity\s*:\s*(\d+/\d+)", README).group(1)
    anchor = re.search(r"sensitivity\s*:\s*(\d+/\d+)", ANCHORS).group(1)
    assert readme == anchor


def test_evidence_guard_count_is_quoted_correctly():
    """`--with-evidence` adds N guards; the README says how many."""
    out = subprocess.run([sys.executable, "-m", "dispatch_fidelity.evidence.selftest"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", cwd=ROOT)
    guards = out.stdout.count("[ok  ]")
    quoted = re.search(r"for (\w+) more guards", README)
    assert quoted, "the README must state how many evidence guards there are"
    assert quoted.group(1) in (WORDS.get(guards), str(guards)), (
        f"README says {quoted.group(1)} guards, the self-test runs {guards}")


def test_citation_version_matches_the_package():
    version = re.search(r"^version:\s*(\S+)", CITATION, re.M).group(1)
    assert version == __version__


def test_citation_top_level_doi_is_the_version_doi_not_the_concept_doi():
    """#27. A concept DOI beside a fixed `version:` describes a different artifact every
    release, while the file still claims to describe this one."""
    top = re.search(r"^doi:\s*(\S+)", CITATION, re.M).group(1)
    described = [m.group(1) for m in
                 re.finditer(r"value:\s*(\S+)\n\s*description: Version DOI", CITATION)]
    assert described, "the identifiers block must name which DOI is the version DOI"
    assert top == described[0]


def test_install_instructions_do_not_point_at_a_moving_target():
    """#28. `git+…` builds whatever main is — a different artifact under the same
    version number, which is what the software DOI exists to prevent."""
    install = re.search(r"pip install (\S+)", README).group(1)
    assert not install.startswith("git+"), (
        "install from the released wheel or from PyPI, not from a branch")
    if install.startswith("http"):
        assert f"v{__version__}/" in install, (
            "the release URL must name the version this repository is at")
