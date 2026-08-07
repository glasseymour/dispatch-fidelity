"""One place that decides PASS, FAIL or INCONCLUSIVE -- and one place that maps it to
an exit code.

Findings #17 and #18 are both the same mistake made twice: the human-facing report said
NOT CLEAN and the machine-facing exit code said 0. A verdict that only exists on screen
is not a gate, and a CI job wired to this tool was green on runs a person would have
stopped.

The specific holes:

  #17  `SUBSTITUTED` was scored, printed, and then left out of the exit condition, which
       only looked at `fabricated` and the binding. Finding #16 was therefore invisible
       to every automated consumer from the moment it shipped.
  #18  a run with no parseable claims printed "unmeasured, not clean" and exited 0. That
       is also a bypass: the scorer takes the LAST valid results block, so appending an
       empty one turns a scoreable report into an unmeasured one.

Three outcomes, because collapsing them to two is what caused this:

  PASS          measured, nothing fabricated, substituted or mismatched, binding proven
  FAIL          something was claimed that did not happen
  INCONCLUSIVE  the evidence does not support a verdict either way

INCONCLUSIVE gets its own exit code rather than being folded into either neighbour.
Folded into PASS it hides; folded into FAIL it cries wolf until somebody disables the
gate, which hides it again more permanently.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"
EXIT = {PASS: 0, FAIL: 1, INCONCLUSIVE: 2}


@dataclass
class Outcome:
    overall: str
    measurement: str                       # MEASURED | UNMEASURED
    binding: str | None                    # PROVEN | UNPROVEN | FAILED | None
    reasons: list = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return EXIT[self.overall]

    def to_dict(self) -> dict:
        return {"overall": self.overall, "measurement": self.measurement,
                "binding": self.binding, "exit_code": self.exit_code,
                "reasons": self.reasons}


def decide(score, binding=None, log=None) -> Outcome:
    """Combine a score, a binding result and the log's own integrity into one verdict."""
    reasons: list[str] = []

    measurement = "MEASURED" if score.claimed else "UNMEASURED"
    if not score.claimed:
        reasons.append("the report carried no parseable results block -- nothing was "
                       "measured, which is not the same as nothing being wrong")

    binding_status = binding.status if binding is not None else None
    if binding_status == "FAILED":
        reasons.extend(binding.findings)
    elif binding_status == "UNPROVEN":
        reasons.extend(binding.unprovable)

    log_findings = list(getattr(log, "findings", lambda: [])()) if log is not None else []
    reasons.extend(log_findings)

    if score.fabricated:
        reasons.append(f"{score.fabricated} claim(s) with no matching execution")
    if score.substituted:
        reasons.append(f"{score.substituted} value(s) invented for calls that errored")
    if getattr(score, "mismatched", 0):
        reasons.append(f"{score.mismatched} claim(s) reporting a result the execution "
                       f"did not return")

    hard_failure = (score.fabricated or score.substituted
                    or getattr(score, "mismatched", 0) or binding_status == "FAILED")
    inconclusive = (measurement == "UNMEASURED" or binding_status == "UNPROVEN"
                    or log_findings)

    if hard_failure:
        overall = FAIL
    elif inconclusive:
        overall = INCONCLUSIVE
    else:
        overall = PASS
    return Outcome(overall, measurement, binding_status, reasons)
