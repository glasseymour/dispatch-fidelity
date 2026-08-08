"""Binding: do these two files describe the same run?

Every test here works with GENUINE artifacts. Nothing is corrupted, no hash is broken --
that is the whole point of the failure class. The evidence stays valid and stops being
about one execution.
"""
import json
import shutil

from dispatch_fidelity.demo import mock_agent
from dispatch_fidelity.fidelity.binding import check_binding, recover_nonce
from dispatch_fidelity.fidelity.proxy import load_log


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
    assert any("UNPROVEN" in u for u in r.unprovable)
    # Finding #19 reversed what this test used to assert. Unprovable is still not a
    # finding -- nothing here says the run is unsound -- but it is not a pass either,
    # and the earlier `assert r.bound` wrote that collapse into the test suite.
    assert r.status == "UNPROVEN"
    assert not r.bound


def test_nonce_recovery_reads_the_probe_receipt(tmp_path):
    s, _ = mock_agent.faithful_artifacts(run_dir=tmp_path, run_id="d")
    assert recover_nonce(load_log(s.log_path)) == s._nonce


def test_concurrent_calls_lose_nothing(tmp_path):
    """Finding #29, from the LangGraph integration probe.

    ToolNode executes one message's tool calls in parallel on separate threads. The
    proxy's sequence increment was a read-modify-write and its append a separate
    open-write-close, so a 64-call batch dropped up to three EXECUTED calls from the
    log — 13 of 20 probe runs lost at least one. The instrument's own evidence layer
    violated I7 under the concurrency a real framework actually uses.
    """
    import concurrent.futures as cf

    from dispatch_fidelity import AuditSession

    def spin(n: int) -> str:
        x = 0
        for i in range(4000):
            x += i
        return f"r{n}"

    session = AuditSession(tools={"spin": spin}, run_dir=tmp_path, run_id="conc",
                           schema={"spin": {"params": ["n"]}}, with_canary=False)
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(lambda i: session.call("spin", {"n": i}), range(64)))

    records = load_log(session.log_path)
    assert records.intact
    assert len(records) == 64, "an executed call vanished from the log"
    assert sorted(r["seq"] for r in records) == list(range(1, 65))
    assert {r["args"]["n"] for r in records} == set(range(64))
