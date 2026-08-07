# Wiring it into a real system

*CC BY 4.0*

## Where the gap actually is

Before choosing an adapter, be clear about which surface you are auditing. This decides
whether the exercise is worth anything.

**No gap.** A model emits a structured `tool_calls` entry and your loop executes it. The
call *is* the claim. They cannot diverge, and no instrument can find a divergence that
the protocol makes impossible.

**Gap.** Any point where a natural-language statement about tool use is produced and then
consumed:

- the final summary a human reads and acts on
- a sub-agent reporting to an orchestrator in prose
- a hand-off between stages where the receiving stage trusts the sending stage's account
- a report assembled after the fact from memory rather than from the transcript

The last one is the most common in practice and the least visible. An agent that ran nine
tools and writes its summary from working memory rather than the transcript will
occasionally describe a tenth.

Audit the gap. If your system does not have one, it has no dispatch-fidelity surface, and
the honest answer is that you do not need this for that path.

## Plain Python

The simplest case needs no adapter:

```python
from agentaudit import AuditSession

session = AuditSession(
    tools={"search": my_search, "read_file": my_read},
    schema={"search": {"params": ["query"]},
            "read_file": {"params": ["path"]}},
)

report = run_my_agent(session.call, tool_names=session.tool_names)
session.score(report)
print(session.report())
```

If your dispatch is already written and you would rather not rewrite the call sites:

```python
from agentaudit.adapters.python_tools import instrument

wrapped = instrument(MY_TOOLS, session)     # same names, now logged
```

The wrappers take keyword arguments only. Positional arguments would have to be guessed
into parameter names to be logged, and a log entry built from a guess is not evidence.

## OpenAI-style

```python
from agentaudit.adapters import openai_tools

tools = openai_tools.tool_specs(session, descriptions={"search": "Search the corpus."})

resp = client.chat.completions.create(model=..., messages=messages, tools=tools)
messages.append(resp.choices[0].message)
messages += openai_tools.execute_tool_calls(session, resp.choices[0].message)
# ... loop until no more tool calls ...

session.score(final_message.content)
```

Unparseable arguments are logged as an error rather than dropped. A call the model made
badly still happened, and an audit log with a hole in it is not an audit log.

## Anthropic-style

```python
from agentaudit.adapters import anthropic_tools

tools = anthropic_tools.tool_specs(session)
msg = client.messages.create(model=..., messages=messages, tools=tools)

results = anthropic_tools.execute_tool_use(session, msg.content)
messages.append({"role": "user", "content": results})
# ... loop ...

session.score(anthropic_tools.final_text(final_msg))
```

## MCP

```bash
python -m agentaudit.adapters.mcp_stdio --run-dir audit_runs -- npx -y @scope/server
```

Point your client at this instead of the server. Every `tools/call` request and its
matching response get recorded; everything else is relayed byte-for-byte, so a protocol
version the proxy has never seen still works.

**Stated limitation.** This records execution and does not inject a canary. A canary has
to be a tool the agent believes in, and inventing one inside a relay would change the
toolset the server advertises — the measurement would alter the system it measures. For
canary coverage, add a canary tool to the server itself, or use the in-process session.

Without a canary you still detect invented calls and altered arguments. What you lose is
proof that the agent knows what a call returned, and the B3 binding check reports itself
**unprovable** rather than passing quietly.

## Asking the agent for its claims

The audit needs the agent to state what it did:

```python
from agentaudit.adapters.python_tools import claims_instruction

system_prompt = MY_PROMPT + "\n\n" + claims_instruction()
```

Two failure modes to expect on first contact, both fixable in the prompt:

- **No block at all.** Scored as `claimed = 0`, reported as unmeasured. Look for it in
  the output before blaming the tool.
- **A block listing the plan instead of the calls.** An agent that lists what it intended
  to do will show fabrications for anything it planned and skipped. That is a real
  finding about your prompt, and arguably about your system.

## Scoring artifacts after the fact

```bash
agentaudit score \
  --claims report.md \
  --log audit_runs/run-xxx.toollog.jsonl \
  --manifest audit_runs/run-xxx.manifest.json \
  --schema tools.json \
  --json result.json
```

Exit 1 when anything is fabricated or the binding fails. In CI that is the whole
integration.

## Running many runs

One score is an anecdote. A fabrication rate is a property of a system-and-workload pair,
and it needs a grid: several tasks, several repetitions, fixed configuration.

Use a distinct `run_id` per run, keep every manifest and log, and score them together.
Then read [interpreting.md](interpreting.md) before quoting the number to anyone.
