# Review provenance

Where each finding came from, stated at the level of precision that survives scrutiny.

Findings #16–#25 were identified during **model-assisted external review**. They were not
found by a human reading the code with fresh eyes, and calling them "external review"
without qualification would let a reader assume otherwise — the same plausible-but-
unverified shape this instrument exists to catch. In a project whose credibility rests on
saying exactly what happened, the provenance of its own findings is not an exception.

What the models did: generated the attack questions and the findings.
What the human did: reproduced each one against the code, classified it, decided the
measurement question, implemented the fix, and takes responsibility for all of it.

A model is a **review source**, not a reviewer. It did not stake a reputation, cannot be
held to its judgement tomorrow, and there is nobody to ask for approval before naming it.
That is the difference from finding #15 in the source deposit, which came from a named
person who reviewed and approved the text describing his own contribution before it was
published.

## Register

| Findings | Review source | Date | Reproduced by | Disposition |
|---|---|---|---|---|
| #16 | Anthropic Claude Opus 5 | 2026-08-07 | Zoltán Varga | accepted, fixed |
| #17–#23 | OpenAI GPT-5.6 Pro via ChatGPT | 2026-08-07 | Zoltán Varga | #17–#22 accepted and fixed; #23 accepted as a documented trade-off, rule unchanged and now version-tagged |
| #24 | Anthropic Claude Opus 5 | 2026-08-07 | Zoltán Varga | accepted, fixed |
| #25 | OpenAI GPT-5.6 Pro via ChatGPT | 2026-08-07 | Zoltán Varga | accepted, fixed |
| #27, #28 | OpenAI GPT-5.6 Pro via ChatGPT | 2026-08-08 | Zoltán Varga | accepted, fixed |

**Numbering collision, resolved.** Two reviews independently reached the same area and
both assigned `#24`. Claude Opus 5 used it for the torn-log-with-manifest path, found on
the `bind` command; GPT-5.6 Pro used it for the unchecked-binding path. Numbers are
assigned here in the order the findings arrived, so the torn-log case keeps `#24` and the
unchecked-binding case becomes `#25`. Recorded rather than quietly renumbered, because a
finding whose identifier moves without explanation is a finding that can be cited twice.

Both are the same family as #17–#20 and worth stating together: the validation matrix was
measuring this project's own convenience wiring rather than the command a user runs. `G4`
handed `decide()` a binding computed from the *intact* log while corrupting only the copy
the scorer saw, so the CLI path — where the damaged log goes into both — was never
covered. `G5` and `G6` close that.

## When a review source was wrong

**2026-08-08 — the crash-window error direction, in ADR-004.**

Claude Opus 5 stated that the failure mode of the proxy's crash window is a *false
accusation*: the log line is lost, the report still names the call, the scorer returns
`FABRICATED`. The claim was accepted and written into ADR-004, where it carried an
argument about urgency — the gap is unpleasant but does not produce a false clean bill,
so the work could wait.

The claim was true only for a single process whose report survives, and it was stated
without that condition. GPT-5.6 Pro found the general case: a worker that dies after the
side effect but before both the log write and its reply leaves a call in **neither** the
log nor the report, so the run can be `PASS` with a side effect that happened. With a
retry it is sharper still — the lost attempt ran, the second is logged, the report shows
one call, and the operation executed twice. That is a false clearance, and it is the
failure class this instrument exists to catch.

Two things follow, and both are recorded rather than quietly absorbed.

The ADR carried **an unsupported generalisation from a review source**, in a document
whose purpose is to fix invariants — the same shape as the fifteen findings in the method
deposit, arriving through the review channel instead of the code. The correction is dated
in the ADR text itself, not applied silently.

And the sequencing argument it supported partly collapsed. Deferring the durable-lifecycle
work behind real integrations is still the right call, but no longer because the gap is
harmless. The remaining reason is narrower and more honest: an event format must not be
designed against this repository's own harness, because earlier logs age with it.

This is the first entry in this register where a review source was wrong. It belongs here
more than the findings do. A provenance file that only records hits describes an oracle,
and the whole argument for naming these sources precisely is that they are not one.

## Naming

The models are named precisely because vagueness would be the misleading part. Naming
them is not a claim of endorsement, partnership or certification by Anthropic or OpenAI,
and no such claim is made anywhere in this repository.

Commit trailers use `Assisted-By:` and `Review-Source:` rather than `Co-Authored-By:`,
which asserts authorship a review source does not have.

## If a finding comes from a person

Then it is credited by name, and the text describing it is sent to them for approval
before publication — the procedure followed for #15 in the source deposit. A permanent
record naming a living person is worth the extra round.
