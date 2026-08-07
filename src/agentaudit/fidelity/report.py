"""Rendering a result a person can act on.

Two rules shape this file. First, the headline is the count, never a grade: "3 of 14
claims fabricated" tells you what to do, "score 0.79" does not. Second, every fabricated
claim is printed in full. An aggregate that hides its cases is the exact failure this
instrument was built to measure -- in the study behind it, not one of fifteen audit
findings was caught by an aggregate metric. All fifteen came from looking at a case, an
outside question, a number fixed in advance, an internal contradiction, or a sampled
read-through.
"""
from __future__ import annotations

from .scorer import DispatchScore

BAR = "=" * 74


def render(run_id: str, score: DispatchScore, binding=None, log=None) -> str:
    from .outcome import decide

    result = decide(score, binding, log)
    lines = [BAR, f"DISPATCH FIDELITY -- {run_id}", BAR]

    if score.claimed == 0:
        lines += [
            "  claims found : 0",
            "",
            "  The report carried no parseable results block, so there is nothing to",
            "  score. This is not a clean run -- it is an unmeasured one. Check that the",
            "  agent emits a fenced ```json block containing {\"results\": [...]}.",
            "",
            BAR,
            f"{result.overall} -- exit {result.exit_code}. Nothing was measured, which is "
            f"not the same as nothing being wrong.",
            BAR,
        ]
        return "\n".join(lines)

    rate = score.fabrication_rate
    srate = score.substitution_rate
    lines += [
        f"  claims        : {score.claimed}",
        f"  matched       : {score.matched}",
        f"  FABRICATED    : {score.fabricated}"
        + (f"   ({rate:.1%} of claims)" if score.fabricated else "")
        + "   (claimed, never executed)",
        f"  SUBSTITUTED   : {score.substituted}"
        + (f"   ({srate:.1%} of claims)" if score.substituted else "")
        + "   (executed, errored, value invented)",
    ]
    if score.mismatched:
        lines.append(f"  RESULT_MISMATCH: {score.mismatched}"
                     f"   (executed, succeeded, result rewritten)")
    lines.append(f"  omitted       : {score.omitted}   (logged, never reported)")
    if score.canary_claimed:
        lines.append(f"  canary claims : {score.canary_claimed}, "
                     f"of which fabricated {score.canary_fabricated}")

    if binding is not None:
        lines += ["", f"  -- run binding: {binding.status} --"]
        for name, value in binding.checks.items():
            mark = {True: "pass", False: "FAIL", None: "unprovable"}[value]
            lines.append(f"     {name:32s} {mark}")
        for note in binding.unprovable:
            lines.append(f"     note: {note}")
        for f in binding.findings:
            lines.append(f"     FINDING: {f}")

    for verdict, title in (("FABRICATED", "every fabricated claim"),
                           ("SUBSTITUTED", "every substituted value"),
                           ("RESULT_MISMATCH", "every rewritten result")):
        cases = [v for v in score.detail if getattr(v, "verdict", "") == verdict]
        if not cases:
            continue
        lines += ["", f"  -- {title} ({len(cases)}) --"]
        for v in cases:
            lines.append(f"     {v.tool}({_args(v.args)})")
            if v.reason:
                lines.append(f"        why      : {v.reason}")
            if v.claimed_result:
                lines.append(f"        claimed  : {v.claimed_result[:150]}")

    lines += ["", BAR]
    headline = {
        "PASS": f"PASS -- all {score.claimed} claimed tool calls are backed by a logged "
                f"execution, and the run binds.",
        "FAIL": f"FAIL -- {score.value_integrity_failures} of {score.claimed} claims are "
                f"not supported by what actually executed.",
        "INCONCLUSIVE": "INCONCLUSIVE -- nothing here says the run is bad, and nothing "
                        "here proves it is good.",
    }[result.overall]
    lines.append(f"{headline}  (exit {result.exit_code})")
    for reason in result.reasons:
        lines.append(f"   - {reason}")
    lines.append(BAR)
    return "\n".join(lines)


def _args(args: dict) -> str:
    if not args:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in args.items())
