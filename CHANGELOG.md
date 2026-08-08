# Changelog

Findings get numbers here, continuing the numbering of the correction protocol in the
[method deposit](https://doi.org/10.5281/zenodo.21812041). The deposit records fifteen;
this file starts at sixteen. A number marks **released behaviour reachable through a
supported usage path** — output-type invariant gaps and test-contract gaps get fixes and
non-silent register entries, not numbers, so the ledger keeps meaning something.

The reason for one shared sequence: a finding about the instrument is a finding about the
instrument, whether it lands in a research harness or in a package. Restarting the count
at 1 here would make the tool look younger than its correction history.

## Unreleased

### Mutation analysis — a test-adequacy baseline, hardening, and rerun

Full write-up in [docs/mutation-testing.md](docs/mutation-testing.md); every figure is
derived from the raw run logs by `tools/collect_mutation_results.py` into
`tools/mutation_results.json`, beside the declared operator set in
`tools/mutation_regime.json`.

Three passes over the same gauntlet: a retained **78.5%** baseline (102/130 detected,
pre-hardening code), then **89.4%** and **93.9%** over the post-hardening 132 sites —
the hardening itself added two mutation points. Survivor triage produced one structural
strengthening and a set of test-contract repairs:

- **Binding status is now derived canonically from the tri-state check values** through
  a single `add_check` path; the explanatory lists explain the verdict and no longer
  participate in deciding it. A constructive probe ran first: across all 256
  combinations of eight structural input dimensions, no enumerated input to the shipped
  code produced a displayed check contradicting the verdict — `check_binding` had always
  written the two together, and nothing enforced it. Regression coverage pins the
  `PROVEN`/`UNPROVEN`/`FAILED` mappings and the precedence of contradicted over
  incomplete evidence.
- **Test-contract repairs, no finding numbers**: exact counter values, the
  `strict_results=False` default (a published behavioural promise that had no test),
  single-claim clean runs, parser boundaries, the empty-receipt fallback, strict-mode
  classification of errored calls, and insensitivity to the LOGGED argument insertion
  order. Triage of pass 2 found five of the new tests themselves too weak to kill their
  targets; pass 3 exists because the loop was applied to its own repairs.
- The eight remaining survivors are **judged on review** — per-mutant register in
  `tools/mutation_triage.json` — and no adjusted score is derived from them.
- **Classification, decided rather than left implicit.** On the released v0.3.0, direct
  construction of the exported `BindingResult` type with a `False` check and no finding
  reported `PROVEN`. Weighed for a finding number and classified as **hardening without
  one**: `BindingResult` is an output type — hand-constructing one with contradictory
  fields fabricates a result object rather than exercising a supported usage path, and
  no such path produced a wrong verdict. The numbering rule gains the clause this edge
  exposed: *a finding number marks released behaviour reachable through a supported
  usage path.* The full weighing, including the counter-position, is recorded in the
  triage register.

### Finding #29 — the proxy lost executed calls under parallelism

Found by the LangGraph integration probe, before any example was written. `ToolNode`
executes one message's tool calls **in parallel on separate threads** (measured: three
0.3-second tools, 0.31s wall-clock). Under that concurrency the proxy's per-call
open-append-close dropped **executed calls** from the log — 13 of 20 probe runs lost
records from a 64-call batch, up to three at a time, with every `call()` returning
success. The instrument's own evidence layer violated I7 under the concurrency a real
framework actually uses.

In every observed run the loss left a sequence gap, which `B2` catches. Nothing
guarantees that: a lost tail write leaves a gap-free prefix, which is finding #20's
geometry produced by the recorder itself.

**Fix.** Sequence assignment, record composition and the write happen under one lock
against one shared handle held for the log's life; `LoggingProxy` gains `close()`. An
intermediate fix that serialized per-call opens under the lock *still* lost lines on
Windows — the defence is to stop reopening, not to reopen carefully. Regression test
drives the proxy with a 16-worker pool; 25 consecutive stress runs clean.

### LangGraph integration

`examples/langgraph_integration.py` (offline, deterministic) and
`docs/integrations-langgraph.md`. The gap in a graph is not `ToolNode` — structured
execution cannot diverge — but the **prose between nodes**: a worker summarises its
results into text, a supervisor reports from that text, and the embellishing scenario
produces `SUBSTITUTED` with every dispatch claim true. Also recorded: `wrap_tool_call`'s
`execute` may run multiple times (empirical basis for the `logical_call_id`/`attempt_id`
split in ADR-004), graph state is recoverable at call time, and the proxy's
`ERROR:` string contract means the framework's own error handling never fires — the
error-surface boundary condition made concrete.

### Finding #27 — the README and the anchors disagreed, and the gate saw only one

`ANCHOR.txt` said `sensitivity : 17/17`; the README said `15/15` and "twenty-six cases".
The anchor matches what the tool prints, so `dispatch-audit verify` stayed green while the
front page of the project was wrong.

This is #17's shape on a documentation surface: **the machine gate was not looking at what
the human reads.** Correcting the two numbers would have fixed nothing, so the fix is
`tests/test_release_facts.py` — the figures quoted in prose are now re-derived from the
matrix that produces them, and the README and `ANCHOR.txt` cannot disagree.

Same file, same family: `CITATION.cff` carried the **concept** DOI beside a fixed
`version: 0.3.0`, and the README put the concept DOI under the words "which bytes you
ran". A concept DOI resolves to the latest version by definition, so in six months both
would identify a different artifact while still claiming to describe this one. Version DOI
in both places; the concept DOI belongs in a sentence about the project.

### Finding #28 — the install line built a moving target

`pip install git+…/dispatch-fidelity` builds whatever `main` happens to be — two commits
past the tag, with `pyproject.toml` still reading `0.3.0`. Two different byte sets under
one version number, which is precisely what the software DOI exists to prevent. The README
now installs the **released wheel**, and a test refuses any install line pointing at a
branch.

### Numbering

These are **#27 and #28**, not #26. Correction #26 is the deposit's release-gate fix,
published yesterday in Zenodo v3 under `10.5281/zenodo.21840553` — a permanent record. The
same collision as #24 on 2026-08-07, except one side is now immutable, so arrival order
does not decide it: the published number wins. Recorded in
[REVIEW_PROVENANCE.md](REVIEW_PROVENANCE.md).

### Boundary condition on the 19.8% (deposit v4)

The silent-substitution figure behind finding #16 was reported without stating what the
agent could **see** after a tool failed. The proxy produces that representation —
`ERROR:<ExceptionType>`, no message, no traceback — so it was an **interface intervention**
as well as a recorder, and the rate is conditional on it. All 18 cases also arose on one
tool.

Recorded in the method deposit as v4, [10.5281/zenodo.21848501](https://doi.org/10.5281/zenodo.21848501),
with a machine-readable regime identifier (`docs/error_surface.json`,
`proxy-normalized-type-only/1`). The registered primary outcome is unaffected: 10/1250 =
0.80% asks whether a claimed call happened, which does not depend on how a failure was
displayed.

The consequence for this repository is a wording change with teeth: **a fidelity rate is a
property of a system–interface–workload configuration.** "System" was too large a box.

ADR-004 gains the three-plane separation this implies — execution, measurement,
presentation — and the restatement of #16's rule against typed status rather than an
`ERROR` string prefix.

### Also

- **`publish.yml` restructured.** Triggered by the tag, not by a published release, and it
  creates the release complete instead of uploading with `--clobber`. Both were backwards
  under immutable releases, which refuse new assets on a live release. Actions pinned to
  commit SHAs: a moving major tag means the workflow that built a release cannot be
  reconstructed from the record of it.
- **The SBOM now describes a runtime-only environment.** It was taken from the
  verification venv, which contains `pytest` and the SBOM tool itself, and then attested
  **to the wheel** — asserting a dependency set the wheel does not have. Two environments
  now, with an assertion that test tooling has not leaked into the attested one. The
  runtime SBOM is nearly empty, which is the point.
- **`SECURITY.md` no longer describes the pipeline in the present tense.** It had never
  run. It now says what happened for v0.3.0, what will happen from v0.3.1, and states
  plainly that the workflow is a plan in version control rather than a property of any
  downloadable artifact.
- **ADR-004's crash-window paragraph rewritten** to state the error direction
  conditionally. It is a false accusation only where the report survives; where a worker
  dies and the orchestrator does not, the call appears in neither the log nor the report
  and the run can pass with a side effect that happened.
- **I7 raised to a measurement-plane axiom** in ADR-004: *the absence of measurement
  cannot be encoded as the absence of a defect.* It is the abstract shape of #18, #20, #24
  and #25.

**Software DOI for v0.3.0: `10.5281/zenodo.21841083`** (concept
`10.5281/zenodo.21841082`). Created by hand, because the release predates the
Zenodo–GitHub integration. This reverses a call made earlier the same day: the argument
against it was that a manual record opens a second hand-maintained path, which correction
#26 had just closed. It does not — it is a one-off backfill, and later releases are
archived automatically as new versions of this same concept series. The reason to have it
is that the method DOI and the software DOI answer different questions: what is measured
and how it was validated, versus exactly which bytes somebody ran.

Method deposit, citable throughout: `10.5281/zenodo.21812041`.

## 0.3.0 — 2026-08-07

**Every finding in this release is the same shape: the screen said one thing and the exit
code said another.** A verdict that only exists in a human-readable report is not a gate.
Anyone who wired 0.2.0 into CI was green on runs a person would have stopped.

They were found by model-assisted external review, not by this project's own matrix —
because nothing in that matrix looked at exit codes. It does now: the `G` rows below test
the machine boundary directly, which is the only durable fix for a class like this.

**Provenance.** #17–#23 identified during a model-assisted external review using OpenAI
GPT-5.6 Pro via ChatGPT on 2026-08-07; #24 during a model-assisted external review using
Anthropic Claude Opus 5 on the same date; #25 from the GPT-5.6 Pro review. All reproduced,
classified and implemented by Zoltán Varga. See [REVIEW_PROVENANCE.md](REVIEW_PROVENANCE.md),
including how the two reviews' colliding `#24` was resolved.

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

### Finding #24 — damaged evidence became FAIL once a manifest was supplied

`check_binding` put tool-log damage into `findings`, which made the binding `FAILED`,
which `decide()` treats as a hard failure. So the same torn log produced INCONCLUSIVE
without a manifest and FAIL with one — two paths, two verdicts, one input. The printed
text already said "no result over it is conclusive"; now the state agrees with the
sentence. Log damage is `unprovable`, not a finding. A genuine contradiction, such as a
manifest and log from two different runs, is still `FAILED`.

### Finding #25 — a binding that was never checked reported as PASS

`--manifest` is optional, and a run scored without one came back PASS while the report
described a proven binding. No binding check had run at all. Binding now has a fourth
state, `NOT_CHECKED`, and it is INCONCLUSIVE.

Absent evidence and contradicted evidence are different things, and only the second is a
failure. #24 and #25 are the two ways that distinction was missing.

### Why the matrix missed #24 and #25

`G0`–`G4` tested this module's own composition rather than the paths a user takes. `G4`
handed `decide()` a binding computed from the **intact** log while corrupting only the
copy the scorer saw, so the CLI path — where the damaged log goes into both — was never
covered. A matrix that tests its own convenience wiring proves nothing about the command
someone runs. `G5` and `G6` close it.

### Matrix

19 → **28 cases**, sensitivity **17/17**, specificity **11/11**. New rows: `P8` (#16),
`N7`, `N8`, `P9`/`N9` (#21, strict), and `G0`–`G6`, which assert exit codes for the clean,
substituted, unmeasured, unprovable, torn-log, unchecked-binding and torn-log-with-manifest
paths.

### Renamed

The distribution, package and command are now `dispatch-fidelity`, `dispatch_fidelity`
and `dispatch-audit`. Formerly developed under the pre-release name `agentaudit`. No tag
or release existed under the old name, so nothing depends on it; the new name is the
project's actual distinguishing concept and ties the package to the method deposit.

## 0.2.0 — 2026-08-07

### Finding #16 — silent substitution

**The defect.** A tool call runs, returns an error, and the agent reports a plausible
value in its place. Until this release `dispatch-fidelity` scored that run **CLEAN**:

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

**Provenance.** Identified during a model-assisted external review using Anthropic Claude
Opus 5 on 2026-08-07; reproduced against this code before the fix, classified and
implemented by Zoltán Varga. The rule is ported from `analysis/silent_substitution.py` in the deposit, and follows
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
