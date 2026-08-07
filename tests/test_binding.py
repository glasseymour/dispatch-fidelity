"""Binding: do these two files describe the same run?

Every test here works with GENUINE artifacts. Nothing is corrupted, no hash is broken --
that is the whole point of the failure class. The evidence stays valid and stops being
about one execution.
"""
import json
import shutil

from agentaudit.demo import mock_agent
from agentaudit.fidelity.binding import check_binding, recover_nonce
from agentaudit.fidelity.proxy import load_log


def test_intact_run_binds(tmp_path):
    s, _ = mock_agent.faithful_artifacts(run_dir=tmp_path, run_id="a")
    r = check_binding(s.manifest_path, s.log_path)
    assert r.bound
    assert r.checks["B3_nonce_commitment"] is True


def test_log_from_another_run_is_caught(tmp_path):
    a, _ = mock_agent.faithful_artifacts(run_dir=tmp_path, run_id="a")
    b, _ = mock_agent.faithful_artifacts(run_dir=tmp_path, run_id="b")
    crossed = tmp_path / "x"
    crossed.mkdir()
    shutil.copy(a.manifest_path, crossed / "a.manifest.json")
    shutil.copy(b.log_path, crossed / "a.toollog.jsonl")

    r = check_binding(crossed / "a.manifest.json", crossed / "a.toollog.jsonl")
    assert not r.bound
    assert r.checks["B3_nonce_commitment"] is False


def test_binding_is_unprovable_without_a_canary_call(tmp_path):
    s, _ = mock_agent.faithful_artifacts(run_dir=tmp_path, run_id="c")
    records = [r for r in load_log(s.log_path) if not r["tool"].startswith("canary")]
    for i, rec in enumerate(records, 1):
        rec["seq"] = i
    s.log_path.write_text("\n".join(json.dumps(r) for r in records) + "\n",
                          encoding="utf-8")

    r = check_binding(s.manifest_path, s.log_path)
    assert r.checks["B3_nonce_commitment"] is None
    assert r.unprovable and "UNPROVEN" in r.unprovable[0]
    # unprovable is not a finding: nothing here says the run is unsound
    assert r.bound


def test_nonce_recovery_reads_the_probe_receipt(tmp_path):
    s, _ = mock_agent.faithful_artifacts(run_dir=tmp_path, run_id="d")
    assert recover_nonce(load_log(s.log_path)) == s._nonce
