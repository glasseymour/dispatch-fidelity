# Mutation analysis

*CC BY 4.0. Numbers in this document are derived from the raw run logs by
[`tools/collect_mutation_results.py`](../tools/collect_mutation_results.py) into
[`tools/mutation_results.json`](../tools/mutation_results.json); the operator set and
protocol are declared in [`tools/mutation_regime.json`](../tools/mutation_regime.json),
and the score is only interpretable beside them.*

Mutation analysis was used as a **test-adequacy diagnostic**: if the code under test is
deliberately broken in a small way, does some test notice? The declared regression matrix
measures coverage of known failure classes; this measures the suite's sensitivity to
small systematic code changes it was never written against.

## The three passes

| Pass | Sites | Detected | Rate | Survive full suite |
|---|---|---|---|---|
| 1 — baseline, pre-hardening code | 130 | 102 | **78.5%** | 28 |
| 2 — after hardening + first test additions | 132 | 118 | **89.4%** | 14 |
| 3 — after survivor-driven test repairs | 132 | 124 | **93.9%** | 8 |

The pass-1 baseline is **retained unchanged**; the raw logs ship in `tools/` with their
SHA-256 recorded in the results file. The hardening itself added two mutation points, so
passes 2 and 3 ran over the larger site set — each percentage is computed against its own
pass's denominator.

## What the survivors produced

**One structural strengthening.** The binding report's displayed check values and its
overall status lived on separate derivation paths: the data model permitted a failed
displayed check and a `PROVEN` status to coexist when the corresponding explanatory
entry was absent. A constructive probe ran first — across all 256 combinations of eight
structural input dimensions, no enumerated input produced a displayed check contradicting
the verdict, so `check_binding` had always written the two together. Nothing enforced it.
The status is now derived canonically from the tri-state check values. The `add_check`
helper couples values and explanations where a check has a single explanatory path;
checks with multiple possible explanations remain assembled explicitly. Regression
coverage pins the `PROVEN`, `UNPROVEN` and `FAILED` mappings and the precedence rule
(contradicted evidence beats incomplete evidence). A wheel probe recorded the measured
fact with its correct scope in the triage register: the `None` branch of the exported
field is producer-reachable and was handled correctly by the released code; the
erroneous combination arose only through unsupported direct construction.
`BindingResult`, `DispatchScore` and `Outcome` are **producer-owned result objects**:
supported instances are obtained from `check_binding()`, `score()` and `decide()`
respectively, and direct construction with internally inconsistent fields is outside
the supported API contract.

**A set of test-contract repairs.** The surviving mutants exposed contracts the suite
stated nowhere: exact counter values, the `strict_results=False` default — a published
behavioural promise that had no test — the single-claim clean run, parser acceptance
boundaries, and the receipt fallback for an empty logged receipt. Notably, **triage of
pass 2 found five of the newly added tests themselves too weak to kill their targets**
(substring overlap between chosen test values, empty-string containment); pass 3 exists
because the loop was applied to its own repairs.

**Eight remaining survivors, judged on review** — classified per mutant in
[`tools/mutation_triage.json`](../tools/mutation_triage.json) as equivalent on the valid
input domain (A1), unreachable under the documented contract (A2), or
representation-only (A3). Equivalence is undecidable in general, so these are recorded
judgements, not asserted facts, and **no adjusted score is derived from them**: an A2
branch can become reachable when the input contract widens, so the raw figure stands.

## The output-type sweep

The binding hardening raised an obvious follow-up: do the other exported result types
carry the same pattern — two representations of one fact, coupled only by the producer?
They do. `DispatchScore`'s counters and its `detail` list are written together by
`score()`; `Outcome`'s `overall` and `reasons` are written together by `decide()`; in
both, a hand-constructed instance can hold contradictory values (`exit_code` is the
exception — it derives from `overall`). The resolution differs from the binding case
deliberately: canonicalising `DispatchScore`'s counters out of `detail` would change the
serialised shape that earlier deposited artifacts already carry, so for these two types
the invariant is a **documented producer guarantee**, stated in their docstrings, rather
than a self-derived property. The classification reasoning — why the binding case got
the canonicalisation and none of the three got a finding number — is recorded in
[`tools/mutation_triage.json`](../tools/mutation_triage.json) under
`classification_decisions`.

## Scope

These figures characterise the selected modules (`scorer.py`, `binding.py`,
`outcome.py`), the declared mutation operators, the platform and the test configuration
recorded in the results file. **They are not estimates of overall software
correctness.** A richer operator set would find more; the regime file exists so that a
different measurement is a comparison, not an anomaly.

The gauntlet is not part of the per-commit CI matrix. Its place is release gates and
changes touching the measured modules: the ordinary suite checks declared behaviour
classes, the mutation gate checks whether the tests would notice small systematic
changes to the code that computes verdicts.
