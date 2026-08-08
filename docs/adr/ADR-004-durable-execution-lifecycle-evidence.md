# ADR-004 — Durable execution lifecycle evidence

**Status:** proposed · **Date:** 2026-08-07 · **Supersedes:** the single-record proxy of 0.1.0–0.3.0

*CC BY 4.0*

## The question this answers

Not "did the agent call what it says it called" — that is what the instrument already
measures. One level down:

> **Did the measuring layer faithfully record the execution lifecycle itself?**

Everything the scorer concludes rests on the tool log being a complete account of what
ran. That assumption has never been examined, and it does not hold.

## The defect

`LoggingProxy.call` executes the tool, waits for the result, then appends the record. A
hard kill between the side effect and the append leaves an executed call **with no trace
at all**.

**The direction of the error depends on what survives the crash.**

In a single process whose report still gets written, the lost log line produces a *false
accusation*: the report names the call, the log does not hold it, and the scorer returns
`FABRICATED`.

Where the crash takes a worker but not the orchestrator, the exposure reverses. The
worker dies after the side effect but before both the log write and its reply; the
orchestrator reports on what it received; the call appears in **neither** the log nor the
report, and the run can be `PASS` with a side effect that happened. With a retry it is
sharper still — the lost attempt ran, the second is logged, the report shows one
successful call, the verdict is clean, and the operation executed twice.

That second case is a false clearance, which is the failure class this instrument exists
to catch. So the gap is not closed at the verdict level, and the reason to sequence this
work behind real integrations is narrower than convenience: an event format must not be
designed against this repository's own harness, because earlier logs age with it.
`async_call`, typed canonicalisation and a signed chain remain scaling.

## Why an ADR before code

The event model would otherwise be designed against this project's own test harness,
which is exactly the mistake `G4` was: the matrix measured the module's convenience
wiring rather than the command a user runs. A real orchestration will say what `call_id`
must carry, how parallel branches order, and whether `parent_call_id` is recoverable from
the framework's state at all.

An event format is also the one thing here that is painful to change later: earlier logs
age with it. So the invariants are fixed now; the wire format waits for evidence from a
real integration.

## Invariants

**I1 — Commitment precedes effect.** A durable `CALL_STARTED` record exists before any
tool capable of a side effect begins executing. The same shape as the nonce commitment:
the obligation reaches disk while the outcome is still unknown.

**I2 — At most one terminal event.** Each `CALL_STARTED` is followed by at most one of
`CALL_SUCCEEDED`, `CALL_FAILED`, `CALL_ABORTED`.

**I3 — An unterminated call is INCONCLUSIVE, never absent.** A `CALL_STARTED` with no
terminal event means the measuring layer lost track of a call that had begun. It is not
"did not happen", and it is not "happened". It becomes a first-class state, and a run
containing one cannot be `PASS`.

**I4 — Identity is per call, not per sequence.** Every call carries `call_id`; hierarchy
travels in `parent_call_id`, `agent_id`, `run_id`, optionally `span_id`.

**I5 — Order is partial.** A single global counter is not a truth model under concurrency.
Evidence rests on lifecycle and causal linkage, not on a total order imposed afterwards.
The current `seq` gap check becomes a per-agent-stream check, and cross-stream ordering
is not claimed where it was never observed.

### Three planes, currently two

I6 is bigger than "exception handling changes shape". The proxy today fuses three jobs:

```
1. execute the tool
2. record what happened
3. produce the error representation the AGENT sees
```

Because of (3) it is not an observer. It is an intervention: it decides what information
the agent has to reason from after a failure, and the silent-substitution rate is measured
through that decision. `ERROR:<ExceptionType>` is terse, regular and easy to recognise. A
native framework error may be a structured object, a one-line message, a long traceback, a
silently retried call, or an exception that aborts the graph. These are not the same
stimulus.

The measurement and presentation planes must therefore separate:

```
original exception
   ├──▶ recorder            status = FAILED
   │                        exception_type, message_hash, traceback_hash
   │
   ├──▶ error presenter     policy = normalized-type-only/1
   │                                 native-message/1
   │                                 structured-error/1
   │                                 full-traceback/1
   │
   └──▶ agent
```

The scorer reads **only** the recorder's typed status. Finding #16's rule stops asking
whether a logged string starts with `ERROR` and becomes:

```
matching execution status == FAILED
and the final claim asserts a successful value
and no later successful attempt exists for the same logical_call_id
```

`normalized-type-only/1` is kept, named and versioned, so the deposit's measurement stays
reproducible. The transparent mode does not replace it — it creates a second, named
measurement regime, which is what makes the error-surface experiment possible at all.

**I6 — The proxy is transparent.** Return type, exception semantics, cancellation,
timeout, streaming and retry identity pass through unchanged. Today the proxy stringifies
every result and converts every exception to `ERROR:<type>` — an observer effect that
alters the system being measured, and one that finding #16's rule now depends on. The
replacement records the *typed* result and the *original* exception, and derives the
error classification for scoring rather than substituting it into the return path.

### I7 — the measurement-plane axiom

This one is not a property of the event system; it is how the whole system behaves when
the measurement itself becomes uncertain. I1–I6 govern the record. I7 governs what the
absence of a record is allowed to mean.

> **No loss of measurement capability may be represented as the absence of a finding.**
> Recorder failure is an explicit evidence state, and it must reach both the human verdict
> and the machine gate.

Shorter: **the absence of measurement cannot be encoded as the absence of a defect.**

This is the abstract shape of four findings already fixed:

| # | what was missing | what it used to produce |
|---|---|---|
| #18 | no measurable claim | `PASS` |
| #20 | part of the log unreadable | `PASS` |
| #24 | damaged evidence | a wrong `FAIL` |
| #25 | binding never run | `PASS` |

Three collapsed into the benign state and one into the accusing state. Both directions
are the same error: an empty place in the evidence being read as a value. Downstream
systems default it to zero, and zero looks like nothing wrong.

**I7 — Recorder failure is visible.** If the recorder cannot write, the run does not
silently become "unaudited but successful". It fails, or it is marked `INCONCLUSIVE`.
A measuring layer that disappears quietly is the failure this whole project is about.

## Consequences

- The log becomes a stream of lifecycle events rather than one record per completed call.
  A reader is provided for the current format; old logs stay readable.
- `ToolLog` gains an unterminated-call check, and `Outcome` a reason for it.
- `I6` changes what the scorer sees. The `ERROR:` prefix that finding #16's rule keys on
  becomes a derived classification, so that rule is rewritten against typed status — and
  it needs its negative controls re-run, not assumed.
- `I1` costs a durable write per call. That is the price of the guarantee and it is the
  same price the nonce commitment already pays.

## Open, pending real integrations

Whether `parent_call_id` is recoverable from LangGraph state, from an OpenAI Responses
run, or across an MCP relay — and what a canary looks like when the tool layer is a
separate process. These decide the wire format, and none of them can be answered from
inside this repository.

## Not decided here

Signed or hash-chained events. Worth having, and a different question: chaining protects
a record against later modification, while everything above is about the record being
complete in the first place. Ordering them the other way would secure an account that is
still missing entries.
