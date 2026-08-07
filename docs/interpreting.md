# Reading the number

*CC BY 4.0*

## What a fabrication rate is

A property of one system running one workload under one configuration. Not a grade, not a
model ranking, and not transferable. Change the task pool and it moves; change the
orchestration shape and it moves; change the model and it moves.

This is why `dispatch-fidelity` is a tool you run rather than a leaderboard you cite.

## What the study found, and what it did not

The measurement this tool comes from was pre-registered (OSF `4rgey`) and reported:

- **10 / 1250 = 0.80%** fabricated dispatch claims, 95% CI [0.44–1.47%]
- the pre-registered hypothesis that the rate rises with the number of agents was
  **not supported**: Cochran–Armitage z = −1.106, two-sided p = 0.269
- a preliminary scorer had reported **54 / 1250 = 4.32%** with a strongly significant
  positive trend; that series was **retracted**, and the defect that produced it took the
  shape of the expected result

The last point is the one to carry. A wrong instrument produced a number that was five
times larger and agreed with the hypothesis. It was caught by looking at individual cases,
not by any aggregate check.

## Low is not zero

0.80% sounds like a rounding error. In a pipeline running ten thousand tool claims a day,
it is eighty fabricated claims a day. Whether that matters depends entirely on what sits
downstream:

| Downstream | 0.8% means |
|---|---|
| a human reads the summary | a wrong sentence occasionally, usually caught |
| another agent consumes the report | a wrong premise propagating, rarely caught |
| an automated action fires | an action taken on evidence that does not exist |

The rate is the same number in all three rows. The consequence is not.

## Read the cases, not the rate

Across fifteen audit findings in the source study, **not one was caught by an aggregate
metric.** All fifteen came from one of five things: looking at a specific case, a question
from outside, a number fixed in advance, an internal contradiction, or a sampled
read-through.

That is why the report prints every fabricated claim in full. If you take one habit from
this tool, take that one: read the cases. The aggregate is for tracking, never for
discovery.

## Verdicts that are not failures

**OMITTED** — the agent executed something and never reported it. A reporting gap, not a
lie. High omission usually means the claims instruction is not landing, or the agent is
summarising rather than enumerating.

**`claimed = 0`** — the report carried no parseable results block. Unmeasured, not clean.
Fix the prompt before reading anything into it.

**B3 unprovable** — no canary ran, so the manifest-to-log binding cannot be derived.
Unproven is not unsound: nothing suggests the run is bad, and what is absent is the
pre-run commitment that would make the binding cryptographic rather than label-level.

## Verdicts that are failures

**FABRICATED** — a claim with no logged execution behind it, or a canary claim carrying a
receipt no execution produced. Read the printed case; the argument list usually tells you
whether the agent invented the call or misremembered a real one.

**SUBSTITUTED** — the call ran, returned an error, and the report carries a value in its
place. Read this one differently from a fabrication. The agent did the work; it had no
true option in the report schema and chose the plausible one. Before treating it as a
truthfulness problem, check whether your schema offers a legal way to say *"it ran and it
failed"*. If it offers only a value or `MISSING`, the schema is doing the steering, and
adding an `error` branch usually removes most of the class.

Keep the two counts apart when you report them. `fabricated` means dispatch fabrication,
which is what the registered 0.80% figure refers to; `value_integrity_failures` is the
wider sum, and it is not comparable to that number.

**Binding FAILED** — the manifest and the log do not come from the same run. In a normal
workflow this means an artifact got copied, moved or overwritten, and the run should be
discarded rather than debugged. Every claim in it may be correct and none of it is
evidence.

## Comparing runs honestly

- Fix the task pool before you start, and do not add tasks after seeing results.
- Keep the configuration constant across the arms you intend to compare.
- Decide the primary outcome in advance and write it down. Every one of the retracted
  numbers in the source study looked reasonable at the time.
- Report the denominator. `3 fabrications` means nothing without `of how many`.
- When a result surprises you, suspect the instrument first. That is what
  `dispatch-audit selftest` is for, and it is cheap to run.

## Before you publish a number

Say which of these you are in:

**Self-instrumented, self-published.** You ran the tool on your own system and published
your own artifacts. The evidence is internally consistent and provable to you. It is not
provable to an adversary, because the signer and the runner are the same party.

**Externally witnessed.** A second party holds the commitment, countersigns, or the run
is anchored in a transparency log. Now the artifacts mean something to someone who does
not trust you.

Both are legitimate. Confusing them is not.
