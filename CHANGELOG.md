# Changelog

Findings get numbers here, continuing the numbering of the correction protocol in the
[method deposit](https://doi.org/10.5281/zenodo.21812041). The deposit records fifteen;
this file starts at sixteen.

The reason for one shared sequence: a finding about the instrument is a finding about the
instrument, whether it lands in a research harness or in a package. Restarting the count
at 1 here would make the tool look younger than its error history.

## 0.3.0 — 2026-08-07

**Every finding in this release is the same shape: the screen said one thing and the exit
code said another.** A verdict that only exists in a human-readable report is not a gate.
Anyone who wired 0.2.0 into CI was green on runs a person would have stopped.

They were found by external review, not by this project's own matrix — because nothing in
that matrix looked at exit codes. It does now: the `G` rows below test the machine
boundary directly, which is the only durable fix for a class like this.

### Finding #17 — `SUBSTITUTED` never reached the exit code

The verdict added in 0.2.0 was scored, printed, and counted in the report's NOT CLEAN
line. The CLI's return statement looked only at `fabricated` and the binding. Finding #16
was therefore invisible to every automated consumer from the moment it shipped — a
finding that could not fail a build.

### Finding #18 — an unmeasured run exited 0

A report with no parseable claims printed "unmeasured, not clean" and returned 0. It is
also a bypass rather than an accident waiting to happen: the scorer takes the **last**
valid results block, so appending an empty one turns a scoreable report into an
unmeasured one.

### Finding #19 — an unprovable binding reported BOUND

The documentation distinguished *unsound* from *unproven* correctly. The code collapsed
them: `bound` meant "no explicit finding", so a `None` B3 passed. The sharpest case was a
manifest with an **empty** tool log — B1 held, an empty sequence is trivially gap-free,
B4 and B5 had nothing to contradict, B3 was merely unprovable, and `bind` printed BOUND
over evidence containing no evidence.

This mattered most exactly where the documentation had already warned it would: behind an
MCP relay, which deliberately injects no canary, so B3 is always unprovable. Every such
run reported a successful binding.

`BindingResult.status` is now `PROVEN | UNPROVEN | FAILED`, and `bound` means what the
word says. A test in this repository asserted the old behaviour as correct; it now
asserts the opposite, with the reversal written down.

### Finding #20 — unreadable log lines vanished

`load_log()` skipped malformed JSON lines silently. A corrupted middle line usually shows
up as a sequence gap; a corrupted **last** line leaves no trace at all, and the surviving
prefix stays gap-free. Every downstream check then reported a clean run over incomplete
evidence.

`load_log` now returns a `ToolLog` — a list subclass, so every caller keeps working —
carrying `malformed` line numbers. A single unreadable line makes the run INCONCLUSIVE.

### The three-state outcome model

Two states caused all four findings, so there are now three:

| overall | exit | meaning |
|---|---|---|
| `PASS` | 0 | measured, nothing fabricated/substituted/mismatched, binding proven |
| `FAIL` | 1 | something was claimed that did not happen |
| `INCONCLUSIVE` | 2 | the evidence does not support a verdict either way |

`INCONCLUSIVE` gets its own code rather than being folded into a neighbour. Folded into
`PASS` it hides; folded into `FAIL` it cries wolf until somebody disables the gate, which
hides it again more permanently.

### Finding #21 — `RESULT_MISMATCH`, opt-in

The successful-call twin of #16: logged 42, reported 43, verdict MATCHED. Ordinary tool
matching is decided by name and arguments and never looked at the value.

**Off by default**, via `--strict-results` / `strict_results=True`, and the reason is this
project's own discipline. Agents legitimately reformat, round, summarise and translate
results; a tool returning `words=1 chars=2` reported as "1 word, 2 characters" is
faithful. Strict matching calls that a fabrication, and prose restatement of results is
the normal case, not the exception. On by default it would be the largest false-positive
source in the tool. Enable it for systems whose agents are instructed to copy results
verbatim.

### Finding #22 — three gaps in the evidence-discipline module

- **The raw output hash was written and never checked.** `gate.py` stored a SHA-256;
  `verify.py` only checked that the file existed. Recorded evidence could be edited after
  the fact and still verify. A hash written but never recomputed is decoration.
- **Anchor exit codes were ignored.** Only the substring was tested, so a command that
  crashed while printing the expected text counted as an anchor holding.
- **Untracked file contents were invisible to the tree digest.** `git diff HEAD` covers
  tracked changes only, so an untracked file contributed its name and nothing else — and
  a new source file is untracked precisely while it is being written, which is when an
  agent is most likely to be running checks against it.

Guards 8, 9 and 10 in the evidence self-test cover these.

### Finding #23 — argument canonicalisation collapses types, and stays that way

`canon_args` coerces every value to `str`, so `1` and `"1"` compare equal. Raised in
review, and **not changed** — with the trade written down instead. LLM reports serialise
numbers as strings constantly; type-strict matching would turn the common case (a real
call reported with `"42"`) into a fabrication in order to catch the rare one (two distinct
calls differing only in an argument's type). That is the wrong side of this project's own
specificity discipline.

What was actually wrong is that the choice was invisible. Every result now carries
`arg_canonicalisation: "coerce-str/1"`, so a reader can see which rule produced a number
and a future change can be named rather than silently applied.

### Wording

`INSTRUMENT VALIDATED` became **`KNOWN FAILURE-CLASS REGRESSION MATRIX PASSED`**. The
figures are a pass over declared regression cases, not a statistical sensitivity or
specificity estimate, and the old line invited the stronger reading. The deposit's
18-class × 20-injection design is the deeper validation; this matrix is the fast guard.

### Matrix

19 → **26 cases**, sensitivity **15/15**, specificity **11/11**. New rows: `P8` (#16),
`N7`, `N8`, `P9`/`N9` (#21, strict), and `G0`–`G4`, which assert exit codes for the clean,
substituted, unmeasured, unprovable and torn-log paths.

## 0.2.0 — 2026-08-07

### Finding #16 — silent substitution

**The defect.** A tool call runs, returns an error, and the agent reports a plausible
value in its place. Until this release `agentaudit` scored that run **CLEAN**:

```
proxy returned: ERROR:TypeError
claimed 1  matched 1  FABRICATED 0
CLEAN -- all 1 claimed tool calls are backed by a logged execution.
```

Argument matching succeeded, the tool was not a canary, so the returned value was never
inspected — by design, and the design was too narrow.

**Why it is in scope.** This is not "the tool returned a wrong answer". The agent
reported a value **the execution never produced**, which is a dispatch-fidelity question.
The previous README drew the boundary in a place that made a reader believe this case was
covered. It was not.

**Scale.** In the source measurement the class accounted for 18 cases, **19.8% of all
errored calls**. It was found by a human reading MATCHED verdicts one at a time; no
injection probe was looking for it, and neither registered metric could see it.

**The fix.** A new verdict, `SUBSTITUTED`. For a non-canary claim: if every logged call
matching it returned an `ERROR` and the claim does not mention an error anywhere, the
value was invented.

**Counted apart from `FABRICATED`, deliberately.** The registered primary outcome of the
source measurement is dispatch fabrication — 10/1250 = 0.80% — and that figure sits in a
permanent DOI record. Widening what `fabricated` means would silently change what a
published number refers to, which is the exact failure this project exists to catch. Both
verdicts make a run NOT CLEAN; `value_integrity_failures` gives the wider, post-hoc sum.

**Provenance.** External review, 2026-08-07, reproduced against this code before the fix.
The rule is ported from `analysis/silent_substitution.py` in the deposit, and follows
rule 4.3 of the developer note: *a failed call needs its own legal branch*. A schema that
offers only `value` or `MISSING` steers the agent toward the plausible number, because
`MISSING` implies it did not work — when it did work, and failed.

**Added with it:**

- `P8` silent substitution — positive class
- `N7` error reported in the agent's own words — negative control
- `N8` value reported after a successful retry — negative control; if any matching call
  returned a value, reporting it is legitimate, or every retry becomes a finding
- a third demo agent, `substituting`, so the class is visible in the first four minutes
- matrix: 16 → 19 cases, sensitivity 10/10, specificity 9/9

**Known narrowness, stated rather than hidden.** A missing or empty claimed result is not
counted as substitution — reporting nothing is an omission of the error, not an invented
value. That trades a false negative for a false positive, on purpose.

### Also in this release

- **Canary receipt format documented as a contract.** B3 recovers the nonce with
  `CANARY[label]:<hex>`. A custom canary in another shape left the binding silently
  `unprovable`; the message now says so and names the pattern, and `check_binding` and
  `recover_nonce` accept `nonce_pattern`.
- **`audit_runs/` location documented.** Written to the current working directory by
  default; `run_dir=` moves it.

## 0.1.0 — 2026-08-07

First release. Dispatch-fidelity scoring, run binding (B1–B5), adapters for plain Python,
OpenAI `tool_calls`, Anthropic `tool_use` and MCP stdio, a 16-case validation matrix, the
evidence-discipline guards, and an offline demo.

Method and correction history #1–#15 from the deposit: DOI
[10.5281/zenodo.21812041](https://doi.org/10.5281/zenodo.21812041), pre-registration OSF
`4rgey`.
