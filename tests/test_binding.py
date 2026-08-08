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


def test_a_displayed_false_check_is_load_bearing():
    """From mutation analysis. In the shipped code every False check value was
    accompanied by a finding -- verified constructively across 256 structural input
    combinations -- but nothing enforced the coupling, so an edit could flip a displayed
    check with no effect on the verdict. The display and the gate now derive from one
    state: a False check makes the binding FAILED even if no finding was recorded."""
    from dispatch_fidelity.fidelity.binding import BindingResult

    r = BindingResult(run_id="r", checks={"B1_manifest_self_identifies": False})
    assert r.status == "FAILED"
    assert not r.bound

    r2 = BindingResult(run_id="r", checks={"B3_nonce_commitment": None})
    assert r2.status == "UNPROVEN"

    r3 = BindingResult(run_id="r", checks={"B1_manifest_self_identifies": True})
    assert r3.status == "PROVEN"


def test_a_mixed_id_log_shows_B2_false_and_names_the_reason(tmp_path):
    """The B2 check VALUE and its finding are asserted separately, so neither the
    threshold nor the displayed value can drift without a test noticing."""
    import json

    from dispatch_fidelity.fidelity.nonce import new_nonce, seal_manifest

    nonce = new_nonce()
    mp = seal_manifest("mix", nonce, tmp_path)
    recs = [
        {"seq": 1, "run_id": "mix", "tool": "canary_probe", "args": {},
         "result": f"CANARY[A]:{nonce}"},
        {"seq": 2, "run_id": "other", "tool": "t", "args": {}, "result": "x"},
    ]
    lp = tmp_path / "mix.toollog.jsonl"
    lp.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")

    r = check_binding(mp, lp)
    assert r.checks["B2_log_self_identifies"] is False
    assert any("mixes run ids" in f for f in r.findings)
    assert r.status == "FAILED"


def test_status_derives_canonically_from_the_tri_state_checks():
    """The four mappings, plus precedence: contradicted evidence beats incomplete."""
    from dispatch_fidelity.fidelity.binding import BindingResult

    assert BindingResult("r", checks={"a": True, "b": True}).status == "PROVEN"
    assert BindingResult("r", checks={"a": True, "b": False}).status == "FAILED"
    assert BindingResult("r", checks={"a": False, "b": None}).status == "FAILED"
    assert BindingResult("r", checks={"a": True, "b": None}).status == "UNPROVEN"


def test_explanatory_lists_do_not_override_the_checks():
    """The lists explain the verdict; the checks decide it."""
    from dispatch_fidelity.fidelity.binding import BindingResult

    r = BindingResult("r", checks={"a": True}, findings=["stray narrative"])
    assert r.status == "PROVEN"


def test_add_check_couples_value_and_explanation():
    from dispatch_fidelity.fidelity.binding import BindingResult

    r = BindingResult("r")
    r.add_check("B1", False, "why it failed")
    r.add_check("B3", None, "why it is unprovable")
    r.add_check("B4", True, "never recorded for a pass")
    assert r.checks == {"B1": False, "B3": None, "B4": True}
    assert r.findings == ["why it failed"]
    assert r.unprovable == ["why it is unprovable"]
    assert r.status == "FAILED"


def test_every_false_check_carries_an_explanation_end_to_end(tmp_path):
    """Across the real pipeline, a False check never appears bare."""
    import json

    from dispatch_fidelity.fidelity.nonce import new_nonce, seal_manifest

    nonce = new_nonce()
    mp = seal_manifest("e2e", nonce, tmp_path)
    recs = [{"seq": 1, "run_id": "someone-else", "tool": "t", "args": {}, "result": "x"}]
    lp = tmp_path / "e2e.toollog.jsonl"
    lp.write_text("\n".join(json.dumps(x) for x in recs) + "\n", encoding="utf-8")

    r = check_binding(mp, lp)
    false_checks = [k for k, v in r.checks.items() if v is False]
    assert false_checks and r.findings, "a False check must be explained"
    assert r.status == "FAILED"
