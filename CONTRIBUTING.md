# Contributing

## The contribution this project wants most

**Break the scorer.** If you can make it miss a real fabrication, or flag an agent that
told the truth, that is the most valuable issue you can open. Both directions count:

- **False negative** — a fabricated claim scored as MATCHED. An audit tool that misses is
  worse than no tool, because it issues a clean bill of health.
- **False positive** — a faithful agent scored as FABRICATED. Every negative control in
  the validation matrix started as one of these, found by somebody who was annoyed.

Attach the artifacts: the report text, the tool log, the manifest. A finding with
artifacts becomes a new row in `src/dispatch_fidelity/inject/classes.py` and is then guarded
forever. A finding without them is a conversation.

The most useful finding in this project's history came from a reader who never ran the
code. He pointed out that the seal chain proved every file was unmodified and proved
nothing about whether two files belonged together. That became the binding check.

## Setup

```bash
git clone https://github.com/glasseymour/dispatch-fidelity
cd dispatch-fidelity
pip install -e ".[dev]"
pytest -q
dispatch-audit selftest --with-evidence
```

No runtime dependencies, and none will be added without a reason that survives the
question "what does this let a user do that they could not do before?". An audit
instrument that drags in a dependency tree is a bigger attack surface than the thing it
measures, and it cannot be dropped into the locked-down environments where audits are
most often needed.

## House rules

**Every scoring rule change needs a matrix row.** If you loosen a rule, add the negative
control that made you loosen it. If you tighten one, add the positive class it now
catches. A rule change with no row is a number that moved for reasons nobody recorded.

**Keep the correction history in the comments.** The long comments in `scorer.py` are not
clutter. Each one marks a place where this code produced a plausible, wrong answer.
Deleting them makes the file shorter and the instrument less trustworthy.

**The writer and the reader stay separate.** `evidence/gate.py` writes; `evidence/verify.py`
never does. A verifier that regenerates its own evidence cannot fail, and that specific
defect is why this rule exists.

**Suppressions get declared.** Any `noqa`, `skip`, `xfail` or `ignore` you add goes in
`waivers.txt` with a written reason. `dispatch-audit verify` fails otherwise, and it runs on
this repository too.

**Say what you did not do.** A pull request that names its own gaps is easier to merge
than one that leaves them to be discovered.

## Scope

In scope: scoring rules, injection classes, adapters for real agent runtimes, clearer
reports, documentation of failure modes.

Out of scope for now: scoring whether a tool returned the *right* answer, or whether the
agent reasoned well. Those are different measurements with different ground truth, and
mixing them into this one would make a clean result mean less, not more.
