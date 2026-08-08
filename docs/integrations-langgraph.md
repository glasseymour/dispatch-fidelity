# LangGraph integration notes

*CC BY 4.0. Working example: [`examples/langgraph_integration.py`](../examples/langgraph_integration.py) — offline, no model, no key.*

## Where the gap is in a graph

Inside `ToolNode`, nowhere. The `tool_calls` on a message are the execution plan; they
cannot diverge from what runs, and instrumenting that path audits nothing.

The gap is **between nodes**. A worker summarises its tool results into prose; a
supervisor builds the final report from that prose rather than from the transcript. Every
claim is then one paraphrase away from the evidence. The example's three scenarios walk
the surface: a faithful worker passes; a worker that forgets a call produces a visible
`OMITTED` (and still passes — under-reporting is a different defect from over-claiming);
a supervisor that pads a forgotten *failed* call with a plausible value produces
`SUBSTITUTED` and fails the gate, with every dispatch claim true.

## Wiring pattern

The graph's `@tool` functions are thin wrappers; the real implementations live behind
`session.call`, where the proxy logs them. The canary is injected by the session and
offered to the graph as an ordinary tool — without one call to it per run, the
manifest–log binding is `UNPROVEN` and the outcome `INCONCLUSIVE`, by design.

## What probing LangGraph taught the instrument

**`ToolNode` executes one message's tool calls in parallel, on separate threads.**
Measured, not read from documentation: three 0.3s tools completed in 0.31s wall-clock on
three thread ids. This is what surfaced finding #29 — the proxy's per-call open-append
lost executed calls under exactly this concurrency (13 of 20 probe runs, up to three
records per run, on Windows). The proxy now writes through one locked handle, and the
regression test drives it with a 16-worker pool.

**`wrap_tool_call` is the supported interception point, and its contract is a finding in
itself.** The hook receives the request and an `execute` callable that *may be invoked
multiple times* for retries. A call therefore needs a logical identity separate from its
attempt identity — the `logical_call_id` / `attempt_id` split ADR-004 left open now has an
empirical basis. The hook also receives the graph state (so `parent`/branch context IS
recoverable at call time) and a `tool_call_id` minted by the model layer.

**The proxy's string-error contract disables the framework's error handling.** Tools that
return `session.call(...)`'s `ERROR:...` string never raise, so `handle_tool_errors`,
retry policies and error-routing edges **never fire**. The instrument decides what the
agent sees on failure — the error-surface boundary condition of deposit v4, made concrete.
This example therefore runs under the named regime `proxy-normalized-type-only/1`; wiring
the native exception through instead is a *different named measurement*, and ToolNode's
`handle_tool_errors` (bool / str / handler / exception-tuple) is itself several distinct
error surfaces, not one.

## Known limitation

The example scripts the planner and worker instead of calling a model, so it runs in CI
and its verdicts are deterministic. The prose-gap it demonstrates is exactly where a real
model's paraphrasing lives; swap the planner for `llm.bind_tools(...)` and nothing else
changes.
