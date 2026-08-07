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

The direction of the resulting error is worth stating precisely, because it decides how
urgent this is. If the log line is lost and the report still names the call, the scorer
returns `FABRICATED` — a **false accusation**, not a false clean bill. If the whole
process dies, there is no report to score. A partially written log has been
`INCONCLUSIVE` since findings #20 and #24.

So at the level of the *verdict*, the gap is closed. At the level of the *record* it is
not, and the two are not the same thing: a run whose evidence is missing a call is not a
run about which nothing is wrong. This is a correctness item, and it is the only one on
the 0.4 list — `async_call`, typed canonicalisation and a signed chain are scaling.

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

**I6 — The proxy is transparent.** Return type, exception semantics, cancellation,
timeout, streaming and retry identity pass through unchanged. Today the proxy stringifies
every result and converts every exception to `ERROR:<type>` — an observer effect that
alters the system being measured, and one that finding #16's rule now depends on. The
replacement records the *typed* result and the *original* exception, and derives the
error classification for scoring rather than substituting it into the return path.

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
