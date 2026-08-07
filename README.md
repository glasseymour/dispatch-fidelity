# dispatch-fidelity

*Dispatch-fidelity auditing for agentic systems.*

**Did your agent actually call what it says it called?**

An agentic system reports what it did. Somewhere between the tool layer and the summary,
a claim can appear that no execution backs — a search that never ran, a file never read,
a check never performed. The report reads correctly. The numbers look fine. Nothing in
your logs says otherwise, because nothing went wrong; something simply never happened.

`dispatch-fidelity` measures how often that occurs in your system, using ground truth the
agent cannot reach.

```bash
pip install https://github.com/glasseymour/dispatch-fidelity/releases/download/v0.3.0/dispatch_fidelity-0.3.0-py3-none-any.whl
dispatch-audit demo
```

*(Not on PyPI yet. This installs the **released wheel** — the exact bytes covered by the
software DOI and the published checksum. `git+…` would build whatever `main` happens to
be, which is a different artifact carrying the same version number; see finding #28.)*

The demo runs three scripted agents offline — no key, no network, no model.

| Agent | Result |
|---|---|
| **honest** | calls everything it reports, and reports the one call that *failed* as a failure → PASS |
| **lying** | adds three claims for calls it never made → each one printed in full |
| **substituting** | calls everything it reports, then writes a plausible number in place of an error → caught |

The third is the quiet one. Every dispatch claim it makes is true, and the report reads
perfectly. If a tool is going to tell you your system is fine, you should first watch it
tell you when something is not.

---

## The method in five steps

| Step | What happens | Why it is there |
|---|---|---|
| 1 | A nonce is generated and its **hash** written to a manifest **before** the run | A commitment made after the fact can be made to agree with anything |
| 2 | Every tool call goes through a proxy that logs **out of band** | A log the agent can write to is a log the agent can shape |
| 3 | A **canary** tool returns a value derived from the nonce | A claimed receipt becomes proof of execution, not a plausible sentence |
| 4 | A **deterministic** scorer compares claims against the log | Same inputs, same verdict — disagreements are about data, not mood |
| 5 | A **binding** check proves the manifest and log come from one run | Genuine artifacts from two runs assemble into a false proof |

Step 5 is the one most audit tooling skips. It exists here because an external reader
broke the earlier version: file-level integrity proves a file is unmodified, not that two
files **belong together**. Hash-valid artifacts drawn from different runs pass every
check while describing a run that never happened. Nothing is corrupted, so nothing
detects it — except a value that could only have come from both files sharing one
execution.

---

## Auditing your own system

```python
from dispatch_fidelity import AuditSession

session = AuditSession(tools={"search": my_search, "read_file": my_read})

# give the agent session.call as its ONLY route to a tool
report = run_my_agent(session.call, tools=session.tool_names)

score = session.score(report)
print(session.report())
```

The agent must end its answer with a fenced block naming what it called:

````
```json
{"results": [
  {"tool": "search", "args": {"q": "quarterly revenue"}, "result": "..."}
]}
```
````

`dispatch_fidelity.adapters.python_tools.claims_instruction()` returns that paragraph ready to
paste into a system prompt.

### Already have a tool loop?

```python
from dispatch_fidelity.adapters import openai_tools, anthropic_tools

tool_messages = openai_tools.execute_tool_calls(session, assistant_message)
result_blocks = anthropic_tools.execute_tool_use(session, message.content)
```

### Behind MCP

```bash
python -m dispatch_fidelity.adapters.mcp_stdio --run-dir audit_runs -- npx -y @scope/server
```

A pass-through logger between client and server. It records execution; it does not
inject a canary, because inventing a tool inside a relay would change the toolset the
server advertises. For canary coverage, add one to the server or use the in-process
session.

**If you write your own canary, the receipt format is a contract.** The binding check
recovers the nonce with the pattern `CANARY[label]:<hex>`. A canary returning the value
in any other shape makes B3 report `unprovable` — correct, and easy to miss if you did
not know the format mattered. Match the pattern, or pass your own:

```python
check_binding(manifest, log, nonce_pattern=r"my-canary=([0-9a-f]{16,})")
```

Artifacts are written to `audit_runs/` in the current working directory by default; pass
`run_dir=` to put them elsewhere.

### Scoring artifacts you already have

```bash
dispatch-audit score --claims report.md --log run.toollog.jsonl --manifest run.manifest.json
```

Three exit codes, because there are three outcomes:

| overall | exit | meaning |
|---|---|---|
| `PASS` | 0 | measured, nothing fabricated or substituted, binding proven |
| `FAIL` | 1 | something was claimed that did not happen |
| `INCONCLUSIVE` | 2 | the evidence does not support a verdict either way |

`INCONCLUSIVE` covers a report with no parseable claims, a binding that cannot be derived
(no canary ran), and a tool log with unreadable lines. It has its own code on purpose:
folded into `PASS` it hides, folded into `FAIL` it cries wolf until somebody disables the
gate. Treat exit 2 as "this run tells you nothing", not as "this run is fine".

---

## Prove the instrument before you trust it

```bash
dispatch-audit selftest
```

Twenty-eight cases, and both halves matter:

```
  sensitivity : 17/17   deliberate defects caught
  specificity : 11/11   harmless variations left alone
```

These figures are a pass over **declared regression cases**, not a statistical estimate.
The line the tool prints says so: `KNOWN FAILURE-CLASS REGRESSION MATRIX PASSED`. The
deeper validation is the source deposit's 18-class × 20-injection design; this matrix is
the fast guard that runs on every commit.

The positives are the defects: an invented call, an altered argument, a forged receipt,
a receipt too short to be evidence, swapped argument values, a phantom tool, one
execution reported as two, a value invented for a call that errored, and two splice
classes that cross artifacts between real runs.

**The negatives are the half most tools never publish.** A renamed parameter key. A
receipt reported with extra whitespace. Hex in upper case. A receipt truncated to exactly
sixteen characters. Every one of those is a faithful agent writing the truth in an
unexpected shape — and every one of them was scored as a fabrication by some earlier
version of this scorer. A checker that flags everything has perfect sensitivity and is
useless.

Add `--with-evidence` for ten more guards covering the evidence-discipline module.

---

## The second module: evidence discipline

Dispatch fidelity asks whether an agent's claims about tool calls are true. The same
question applies one level out, to an agent's claim that its checks passed:

```bash
dispatch-audit gate --label tests -- pytest -q     # writer: records the run
dispatch-audit verify                              # reader: read-only, fail-closed
```

| Guard | What it closes |
|---|---|
| **BINDING** | the green result came from the code currently on disk, and it exited 0 |
| **ANCHOR** | a number fixed *before* the change still holds |
| **WAIVER** | every `skip`, `xfail`, `noqa`, `ignore`, `disable` is declared with a reason |

The writer and the reader are separate programs. A verifier that regenerates the evidence
it verifies can never report a discrepancy — it replaces the evidence with whatever it
sees, then declares the result clean. That is not hypothetical: it is the worst defect
found in the original study's own tooling.

---

## What this measures, and what it does not

**It measures** four things:

1. whether a claimed tool call corresponds to a logged execution — `FABRICATED`
2. whether a call that ran and **failed** was reported as having produced a value —
   `SUBSTITUTED`
3. optionally, whether a call that **succeeded** was reported with a different result —
   `RESULT_MISMATCH`, opt-in via `--strict-results`
4. whether the evidence for a run holds together — the binding checks

`RESULT_MISMATCH` is off by default because agents legitimately reformat, round and
summarise results, and a strict rule calls that fabrication. Turn it on for systems whose
agents are told to copy results verbatim.

**It does not measure** whether a successful tool returned the *right* answer, whether
the agent's reasoning was sound, or whether the task was completed well. A perfectly
faithful agent can be perfectly wrong.

That boundary is narrower than it sounds, and an earlier version of this README drew it
in the wrong place. It said only "it does not measure whether the tool returned the right
answer", which reads as covering the case where a tool errors and the agent writes a
plausible number instead. It does not cover it, and the tool was blind to it: every
dispatch claim is true, argument matching succeeds, and the run came back **CLEAN**.

That is a dispatch-fidelity question, not a correctness one — the agent reported a value
**the execution never produced**. In the source measurement it accounted for 18 cases,
**19.8% of all errored calls**, and no injection probe was looking for it. It is now
finding #16, class `P8`, with two negative controls beside it. See
[CHANGELOG.md](CHANGELOG.md).

**The boundary worth stating plainly:** where the signer and the runner are the same
party, provenance is complete against accidental mixing and after-the-fact modification,
and absent against an actor fabricating at run time. If you instrument your own system
and publish your own results, this proves your artifacts are internally consistent — it
does not prove them to an adversary. For that you need an external countersignatory or a
transparency log. Say which situation you are in.

**Structured tool calls have no gap.** When a model emits an OpenAI `tool_calls` entry
and your loop executes it, the call *is* the claim; they cannot diverge. The gap opens in
the prose: the final summary a human reads, a sub-agent's report to an orchestrator, a
write-up assembled from memory rather than from the transcript. That text is what this
scores. If your system has no such text, it has no dispatch-fidelity surface, and the
honest answer is that you do not need this for that path.

---

## Interpreting a number

A fabrication rate is a property of a system-and-workload pair, not a grade. In the study
behind this tool the registered primary outcome was **10 / 1250 = 0.80%** [0.44–1.47%],
and the pre-registered hypothesis that the rate would rise with the number of agents was
**not supported** (Cochran–Armitage z = −1.106, p = 0.269).

Two things follow. A low rate is not zero, and rare failures in a pipeline that runs
thousands of times a day are not rare in absolute terms. And a number from one system on
one workload says nothing about yours — which is why this is a tool you run, not a
benchmark you cite.

One more finding is worth carrying over. Across fifteen audit findings in that study,
**not one was caught by an aggregate metric.** All fifteen came from looking at a specific
case, an outside question, a number fixed in advance, an internal contradiction, or a
sampled read-through. This tool prints every fabricated claim in full for that reason.

---

## Provenance

The method, the correction history and the failure classes come from the **Dispatch
Fidelity Benchmark**, a pre-registered measurement (OSF `4rgey`) deposited with its full
artifact set, seal chain and release gate:

> Varga, Z. *Who Validates the Validator? Instrument failure in the shape of the
> hypothesis.* Zenodo. https://doi.org/10.5281/zenodo.21812041

The deposit's correction protocol documents fifteen audit findings about the instrument
itself, including the receipt rules and the binding check reimplemented here. Reading it
is the fastest way to decide how much to trust this code.

---

## Contributing

Findings are the contribution this project wants most. If you can make the scorer miss a
real fabrication, or flag a faithful agent, open an issue with the artifacts — that is a
new row in the validation matrix, and every row there started as somebody's objection.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Citing

**The software** — which bytes you ran:

> Varga, Z. *dispatch-fidelity v0.3.0: dispatch-fidelity auditing for agentic systems.*
> Zenodo. https://doi.org/10.5281/zenodo.21841083
>
> Version DOI, because "which bytes you ran" is a question about one release. The concept
> DOI `10.5281/zenodo.21841082` resolves to the **latest** version and belongs in a
> sentence about the project, not about a result.

**The method** — what is measured and how it was validated:

> Varga, Z. *Who Validates the Validator? Instrument failure in the shape of the
> hypothesis.* Zenodo. https://doi.org/10.5281/zenodo.21812041

Cite both if you used the tool to produce a result. They answer different questions, and
a reader checking your number needs each of them.

## License

Code: [Apache-2.0](LICENSE). Documentation: CC BY 4.0.
