"""The command line.

Six commands, and the first one you should run is `demo`, because a tool that audits
other software has to be auditable itself -- and the fastest way to trust it is to watch
it catch a lie you can read in full.

    agentaudit demo         run an honest agent and a lying one, offline
    agentaudit selftest     the validation matrix: does the scorer catch known defects?
    agentaudit score        score an existing report against an existing tool log
    agentaudit bind         check that a manifest and a tool log come from one run
    agentaudit gate         record a project check command (evidence discipline)
    agentaudit verify       read-only check of recorded runs, anchors and waivers
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_demo(args) -> int:
    from .demo import mock_agent

    rc = 0
    for mode in ("honest", "lying"):
        session, report = mock_agent.run(mode, run_dir=args.run_dir)
        session.score(report)
        print()
        print(f"### agent behaviour: {mode}")
        print(session.report())
        s = session._score
        if mode == "honest" and s.fabricated:
            print("UNEXPECTED: the honest agent was flagged. That is a false positive.")
            rc = 1
        if mode == "lying" and not s.fabricated:
            print("UNEXPECTED: the lying agent passed. That is a false negative.")
            rc = 1
    print()
    print("Artifacts written to:", Path(args.run_dir).resolve())
    if rc == 0:
        print("Both outcomes are as expected: the honest run is clean, the lying run is not.")
    return rc


def _cmd_selftest(args) -> int:
    from .inject import validate

    _, ok = validate.run(verbose=True)
    if args.with_evidence:
        print()
        from .evidence import selftest as ev
        ok = (ev.main() == 0) and ok
    return 0 if ok else 1


def _cmd_score(args) -> int:
    from .fidelity.proxy import load_log
    from .fidelity.report import render
    from .fidelity.scorer import score
    from .fidelity.binding import check_binding, recover_nonce

    report_text = Path(args.claims).read_text(encoding="utf-8")
    records = load_log(Path(args.log))
    if not records:
        print(f"No tool log records read from {args.log}. Nothing can be scored against "
              f"an empty log -- that is an unmeasured run, not a clean one.")
        return 2

    nonce = args.nonce or recover_nonce(records) or ""
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8")) if args.schema else None
    s = score(report_text, records, nonce, schema)

    binding = None
    if args.manifest:
        binding = check_binding(Path(args.manifest), Path(args.log))

    run_id = records[0].get("run_id", "unknown-run")
    print(render(str(run_id), s, binding))
    if args.json:
        Path(args.json).write_text(
            json.dumps({"score": s.to_dict(),
                        "binding": binding.to_dict() if binding else None},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nmachine-readable result: {args.json}")
    return 1 if (s.fabricated or (binding and not binding.bound)) else 0


def _cmd_bind(args) -> int:
    from .fidelity.binding import check_binding

    r = check_binding(Path(args.manifest), Path(args.log))
    print("=" * 74)
    print(f"RUN BINDING -- {r.run_id}")
    print("=" * 74)
    marks = {True: "pass", False: "FAIL", None: "unprovable"}
    for name, value in r.checks.items():
        print(f"  {name:32s} {marks[value]}")
    for note in r.unprovable:
        print(f"  note: {note}")
    for f in r.findings:
        print(f"  FINDING: {f}")
    print()
    print("BOUND -- the manifest and the tool log come from the same run." if r.bound
          else "NOT BOUND -- these artifacts do not prove they describe one run.")
    return 0 if r.bound else 1


def _cmd_gate(args, rest) -> int:
    from .evidence import gate

    argv = []
    if args.label:
        argv += ["--label", args.label]
    argv += ["--", *rest]
    return gate.main(argv)


def _cmd_verify(args) -> int:
    from .evidence import verify

    return verify.main(["--label", args.label] if args.label else [])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentaudit", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="run an honest and a lying agent, offline")
    d.add_argument("--run-dir", default="audit_runs")
    d.set_defaults(func=_cmd_demo)

    s = sub.add_parser("selftest", help="validation matrix: sensitivity and specificity")
    s.add_argument("--with-evidence", action="store_true",
                   help="also run the evidence-discipline guards (needs git)")
    s.set_defaults(func=_cmd_selftest)

    sc = sub.add_parser("score", help="score a report against a tool log")
    sc.add_argument("--claims", required=True, help="file holding the agent's final report")
    sc.add_argument("--log", required=True, help="the proxy tool log (jsonl)")
    sc.add_argument("--manifest", help="the sealed run manifest, to also check binding")
    sc.add_argument("--nonce", help="run nonce, if it is not recoverable from the log")
    sc.add_argument("--schema", help="tool schema json, for parameter-role matching")
    sc.add_argument("--json", help="write the machine-readable result here")
    sc.set_defaults(func=_cmd_score)

    b = sub.add_parser("bind", help="check a manifest and a tool log belong together")
    b.add_argument("--manifest", required=True)
    b.add_argument("--log", required=True)
    b.set_defaults(func=_cmd_bind)

    g = sub.add_parser("gate", help="record a check command and its output")
    g.add_argument("--label", default="check")
    g.set_defaults(func=None)

    v = sub.add_parser("verify", help="read-only: binding, anchors, waivers")
    v.add_argument("--label", default=None)
    v.set_defaults(func=_cmd_verify)
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "gate":                 # everything after -- is the command
        rest = argv[argv.index("--") + 1:] if "--" in argv else []
        head = argv[:argv.index("--")] if "--" in argv else argv
        args = build_parser().parse_args(head)
        if not rest:
            print("usage: agentaudit gate [--label NAME] -- <command> [args...]")
            return 2
        return _cmd_gate(args, rest)
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
