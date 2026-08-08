"""Mutation testing for the scorer and the binding check — the instrument's test suite
measured the way the deposit's §11 says such suites should be measured, instead of only
citing the literature that says so.

    python tools/mutation_gauntlet.py

External review put it plainly: the project delimits itself from mutation testing across
four paragraphs and never runs any. The 28-case matrix and the test suite are a FIXED
set, and a fixed set measures coverage of its author's error model. Mutation testing asks
the adequacy question directly: if the code under test is deliberately broken in a small
way, does some test notice?

Method, stdlib-only like everything else here:

  * parse the target file's AST and enumerate single-point mutations — comparison
    operators flipped, boolean and/or swapped, arithmetic +/- swapped, integer and
    boolean constants perturbed, `not` removed;
  * apply one mutation at a time, run the target's test files, restore the original;
  * a mutant is KILLED if the tests fail, SURVIVING if they pass.

A surviving mutant is a small deliberate defect no test notices. Some survivors are
equivalent mutants (the change does not alter behaviour); the honest number is reported
first and triaged second, because triage without the number is the failure mode this
project keeps writing findings about.

Scope honesty: each target runs only its OWN test files, for run-time reasons. That
under-approximates the suite (the matrix tests in test_session_and_matrix.py also
exercise the scorer), so a survivor here may still be caught by the full suite — each
survivor is re-checked against the full suite before being reported as such.
"""
from __future__ import annotations

import ast
import copy
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "dispatch_fidelity" / "fidelity"

TARGETS = {
    "scorer.py": ["tests/test_scorer.py"],
    "binding.py": ["tests/test_binding.py"],
    "outcome.py": ["tests/test_cli_and_adapters.py"],
}
FULL_SUITE = ["tests"]

CMP_SWAP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.LtE: ast.Gt,
            ast.Gt: ast.LtE, ast.GtE: ast.Lt, ast.In: ast.NotIn, ast.NotIn: ast.In,
            ast.Is: ast.IsNot, ast.IsNot: ast.Is}
BIN_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add}


class Enumerator(ast.NodeVisitor):
    """Collect (site_id, description) for every mutation point."""

    def __init__(self):
        self.sites = []

    def visit_Compare(self, node):
        for i, op in enumerate(node.ops):
            if type(op) in CMP_SWAP:
                self.sites.append(("cmp", node.lineno, i, type(op).__name__))
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.sites.append(("bool", node.lineno, 0, type(node.op).__name__))
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if type(node.op) in BIN_SWAP:
            self.sites.append(("bin", node.lineno, 0, type(node.op).__name__))
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.Not):
            self.sites.append(("not", node.lineno, 0, "Not"))
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            self.sites.append(("const_bool", node.lineno, 0, str(node.value)))
        elif isinstance(node.value, int) and node.value in (0, 1, 16):
            self.sites.append(("const_int", node.lineno, 0, str(node.value)))
        self.generic_visit(node)


class Mutator(ast.NodeTransformer):
    """Apply exactly the nth enumerated mutation."""

    def __init__(self, target_index):
        self.index = -1
        self.target = target_index
        self.applied = None

    def _hit(self, kind, lineno, sub, desc):
        self.index += 1
        if self.index == self.target:
            self.applied = f"{kind}@{lineno}:{desc}"
            return True
        return False

    def visit_Compare(self, node):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            if type(op) in CMP_SWAP and self._hit("cmp", node.lineno, i, type(op).__name__):
                node.ops[i] = CMP_SWAP[type(op)]()
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self._hit("bool", node.lineno, 0, type(node.op).__name__):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if type(node.op) in BIN_SWAP and self._hit("bin", node.lineno, 0, type(node.op).__name__):
            node.op = BIN_SWAP[type(node.op)]()
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._hit("not", node.lineno, 0, "Not"):
            return node.operand
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            if self._hit("const_bool", node.lineno, 0, str(node.value)):
                return ast.copy_location(ast.Constant(value=not node.value), node)
        elif isinstance(node.value, int) and node.value in (0, 1, 16):
            if self._hit("const_int", node.lineno, 0, str(node.value)):
                return ast.copy_location(ast.Constant(value=node.value + 1), node)
        return node


def run_tests(test_paths, timeout=240):
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *test_paths, "-x", "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout)
    return r.returncode == 0


def main():
    grand_survivors = []
    t0 = time.monotonic()
    for fname, test_paths in TARGETS.items():
        path = SRC / fname
        original = path.read_text(encoding="utf-8")
        tree = ast.parse(original)
        en = Enumerator()
        en.visit(tree)
        n = len(en.sites)
        print(f"\n=== {fname}: {n} mutation sites ===")

        killed = survived = broken = 0
        survivors = []
        try:
            for i in range(n):
                m = Mutator(i)
                mutated_tree = m.visit(copy.deepcopy(tree))
                ast.fix_missing_locations(mutated_tree)
                try:
                    code = ast.unparse(mutated_tree)
                except Exception:
                    broken += 1
                    continue
                path.write_text(code, encoding="utf-8")
                try:
                    passed = run_tests(test_paths)
                except subprocess.TimeoutExpired:
                    killed += 1      # a hang is a detected mutant
                    continue
                if passed:
                    survived += 1
                    survivors.append(m.applied or f"site {i}")
                else:
                    killed += 1
        finally:
            path.write_text(original, encoding="utf-8")

        print(f"  killed {killed} / survived {survived} / unparseable {broken}")
        if survivors:
            print(f"  survivors vs OWN tests ({len(survivors)}):")
            for s in survivors:
                print(f"    {s}")
            # a survivor only counts if the FULL suite also misses it
            print("  re-checking survivors against the full suite ...")
            for i in range(n):
                m = Mutator(i)
                mt = m.visit(copy.deepcopy(tree))
                ast.fix_missing_locations(mt)
                if (m.applied or f"site {i}") not in survivors:
                    continue
                path.write_text(ast.unparse(mt), encoding="utf-8")
                try:
                    if run_tests(FULL_SUITE, timeout=600):
                        grand_survivors.append(f"{fname}: {m.applied}")
                        print(f"    SURVIVES FULL SUITE: {m.applied}")
                    else:
                        print(f"    killed by full suite: {m.applied}")
                finally:
                    path.write_text(original, encoding="utf-8")

    dt = time.monotonic() - t0
    print("\n" + "=" * 74)
    print(f"MUTATION GAUNTLET — {dt/60:.1f} min")
    if grand_survivors:
        print(f"{len(grand_survivors)} mutant(s) survive the FULL test suite:")
        for s in grand_survivors:
            print(f"  {s}")
        print("Each one is a small deliberate defect no test notices — a finding")
        print("candidate after triage for equivalence.")
    else:
        print("No mutant survives the full suite. The suite is adequate against THIS")
        print("mutation operator set — which is a bounded claim, not a general one.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
