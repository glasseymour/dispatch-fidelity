"""End-to-end behaviour, and the validation matrix as a test.

The matrix runs here as well as in `agentaudit selftest` on purpose. A user who never
runs the CLI still gets the guarantee on every `pytest`, and a contributor who breaks a
scoring rule sees it break the build rather than sees a number move.
"""
import json

from agentaudit import AuditSession
from agentaudit.demo import mock_agent
from agentaudit.demo.tools import SCHEMA, TOOLS
from agentaudit.inject import validate


def test_honest_run_is_clean(tmp_path):
    session, report = mock_agent.run("honest", run_dir=tmp_path)
    s = session.score(report)
    assert s.fabricated == 0 and s.substituted == 0 and s.claimed == 6
    assert session.binding.bound


def test_lying_run_is_caught(tmp_path):
    session, report = mock_agent.run("lying", run_dir=tmp_path)
    s = session.score(report)
    assert s.fabricated == 3
    assert "FAIL" in session.report()
    assert session.outcome.exit_code == 1


def test_manifest_is_sealed_before_the_run(tmp_path):
    session = AuditSession(tools=TOOLS, run_dir=tmp_path, schema=SCHEMA)
    manifest = json.loads(session.manifest_path.read_text(encoding="utf-8"))
    assert manifest["nonce_sha256"] and "nonce" not in manifest
    assert not session.log_path.exists()      # nothing logged yet


def test_the_plaintext_nonce_never_reaches_disk(tmp_path):
    session, report = mock_agent.run("honest", run_dir=tmp_path)
    session.score(report)
    manifest = session.manifest_path.read_text(encoding="utf-8")
    assert session._nonce not in manifest


def test_unknown_tool_is_logged_as_an_error_not_dropped(tmp_path):
    session = AuditSession(tools=TOOLS, run_dir=tmp_path, schema=SCHEMA)
    out = session.call("no_such_tool", {})
    assert out.startswith("ERROR:unknown_tool")
    assert session.log_path.read_text(encoding="utf-8").count("\n") == 1


def test_validation_matrix_is_fully_green():
    rows, ok = validate.run(verbose=False)
    failed = [r.key for r in rows if not r.passed]
    assert ok, f"validation matrix regressions: {failed}"
    assert len(rows) == 26


def test_substituting_run_is_caught(tmp_path):
    """Finding #16. Every dispatch claim is true; one value was never produced."""
    session, report = mock_agent.run("substituting", run_dir=tmp_path)
    s = session.score(report)
    assert s.fabricated == 0          # it really did call everything it reported
    assert s.substituted == 1
    assert not s.clean
    assert "SUBSTITUTED" in session.report()


def test_an_honestly_reported_failure_stays_clean(tmp_path):
    """The negative control that has to ship with #16, or specificity breaks."""
    session, report = mock_agent.run("honest", run_dir=tmp_path)
    assert "ERROR:ValueError" in report
    s = session.score(report)
    assert s.substituted == 0 and s.clean
