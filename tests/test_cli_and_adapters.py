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
    assert "CLEAN" in out and "NOT CLEAN" in out


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
