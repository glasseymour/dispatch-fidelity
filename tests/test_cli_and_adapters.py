"""The command line and the adapters, exercised the way a user meets them."""
import json

from agentaudit.adapters import anthropic_tools, openai_tools, python_tools
from agentaudit.cli import main
from agentaudit.demo import mock_agent
from agentaudit.demo.tools import SCHEMA, TOOLS
from agentaudit.fidelity.session import AuditSession


def test_demo_command_exits_zero(tmp_path, capsys):
    assert main(["demo", "--run-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out and "FAIL" in out


def test_score_command_flags_a_lying_run(tmp_path, capsys):
    session, report = mock_agent.run("lying", run_dir=tmp_path)
    claims = tmp_path / "report.md"
    claims.write_text(report, encoding="utf-8")
    result = tmp_path / "result.json"

    rc = main(["score", "--claims", str(claims), "--log", str(session.log_path),
               "--manifest", str(session.manifest_path), "--json", str(result)])
    assert rc == 1
    assert json.loads(result.read_text(encoding="utf-8"))["score"]["fabricated"] == 3
    assert "FABRICATED" in capsys.readouterr().out


def test_bind_command_reports_a_crossed_pair(tmp_path, capsys):
    a, _ = mock_agent.faithful_artifacts(run_dir=tmp_path, run_id="a")
    b, _ = mock_agent.faithful_artifacts(run_dir=tmp_path, run_id="b")
    assert main(["bind", "--manifest", str(a.manifest_path),
                 "--log", str(b.log_path)]) == 1
    assert "NOT BOUND" in capsys.readouterr().out


def test_python_adapter_logs_through_the_session(tmp_path):
    session = AuditSession(tools={}, run_dir=tmp_path, schema=SCHEMA, with_canary=False)
    session._toolset.update(TOOLS)
    session.proxy._tools.update(TOOLS)
    wrapped = python_tools.instrument(TOOLS, session)
    assert wrapped["calculator"](expression="6*7") == "42"
    assert '"tool": "calculator"' in session.log_path.read_text(encoding="utf-8")


def test_openai_adapter_executes_and_returns_tool_messages(tmp_path):
    session = AuditSession(tools=TOOLS, run_dir=tmp_path, schema=SCHEMA)
    message = {"tool_calls": [
        {"id": "c1", "function": {"name": "calculator",
                                  "arguments": json.dumps({"expression": "6*7"})}}]}
    out = openai_tools.execute_tool_calls(session, message)
    assert out == [{"role": "tool", "tool_call_id": "c1", "name": "calculator",
                    "content": "42"}]
    assert any(t["function"]["name"] == "canary_probe"
               for t in openai_tools.tool_specs(session))


def test_openai_adapter_survives_unparseable_arguments(tmp_path):
    session = AuditSession(tools=TOOLS, run_dir=tmp_path, schema=SCHEMA)
    message = {"tool_calls": [{"id": "c1", "function": {"name": "calculator",
                                                        "arguments": "{not json"}}]}
    out = openai_tools.execute_tool_calls(session, message)
    assert out[0]["content"].startswith("ERROR:")      # logged, never silently dropped


def test_anthropic_adapter_executes_tool_use_blocks(tmp_path):
    session = AuditSession(tools=TOOLS, run_dir=tmp_path, schema=SCHEMA)
    blocks = [{"type": "text", "text": "thinking"},
              {"type": "tool_use", "id": "u1", "name": "doc_lookup",
               "input": {"key": "doc-1"}}]
    out = anthropic_tools.execute_tool_use(session, blocks)
    assert out[0]["tool_use_id"] == "u1"
    assert "quick brown fox" in out[0]["content"]
    assert anthropic_tools.final_text({"content": blocks}) == "thinking"


def test_claims_instruction_documents_the_contract():
    text = python_tools.claims_instruction()
    assert '"results"' in text and "```json" in text


# --- findings #17-#20: what the screen says, the exit code must say too -------------
def _write(tmp_path, report):
    p = tmp_path / "report.md"
    p.write_text(report, encoding="utf-8")
    return p


def test_substituted_run_exits_1(tmp_path):
    """#17. It was scored, printed, and left out of the gate."""
    session, report = mock_agent.run("substituting", run_dir=tmp_path)
    assert main(["score", "--claims", str(_write(tmp_path, report)),
                 "--log", str(session.log_path),
                 "--manifest", str(session.manifest_path)]) == 1


def test_unmeasured_run_exits_2_not_0(tmp_path, capsys):
    """#18. An empty trailing results block used to turn a scoreable run into a pass."""
    session, report = mock_agent.run("lying", run_dir=tmp_path)
    bypass = report + '\n```json\n{"results": []}\n```\n'
    rc = main(["score", "--claims", str(_write(tmp_path, bypass)),
               "--log", str(session.log_path), "--manifest", str(session.manifest_path)])
    assert rc == 2
    assert "INCONCLUSIVE" in capsys.readouterr().out


def test_unprovable_binding_exits_2(tmp_path, capsys):
    """#19. No canary call means B3 cannot be derived -- that is not BOUND."""
    session, report = mock_agent.run("honest", run_dir=tmp_path)
    kept = [json.loads(l) for l in session.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    kept = [r for r in kept if not r["tool"].startswith("canary")]
    for i, rec in enumerate(kept, 1):
        rec["seq"] = i
    stripped = tmp_path / "nocanary.toollog.jsonl"
    stripped.write_text("\n".join(json.dumps(r) for r in kept) + "\n", encoding="utf-8")

    assert main(["bind", "--manifest", str(session.manifest_path),
                 "--log", str(stripped)]) == 2
    assert "UNPROVEN" in capsys.readouterr().out


def test_a_torn_log_line_exits_2(tmp_path, capsys):
    """#20. A corrupt last line used to vanish, leaving a gap-free prefix behind."""
    session, report = mock_agent.run("honest", run_dir=tmp_path)
    torn = tmp_path / "torn.toollog.jsonl"
    torn.write_text(session.log_path.read_text(encoding="utf-8") + "{not json\n",
                    encoding="utf-8")
    rc = main(["score", "--claims", str(_write(tmp_path, report)), "--log", str(torn)])
    assert rc == 2
    assert "unreadable line" in capsys.readouterr().out


def test_strict_results_flags_a_rewritten_value(tmp_path):
    """#21, opt-in. Without the flag the same run is a pass."""
    session, report = mock_agent.run("honest", run_dir=tmp_path)
    tampered = report.replace('"result": "51"', '"result": "52"')
    claims = _write(tmp_path, tampered)
    assert main(["score", "--claims", str(claims), "--log", str(session.log_path)]) == 0
    assert main(["score", "--claims", str(claims), "--log", str(session.log_path),
                 "--strict-results"]) == 1
