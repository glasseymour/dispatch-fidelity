"""dispatch-fidelity -- did your agent actually call what it says it called?

The short version of the method:

  1. A nonce is generated and committed as a hash BEFORE the run.
  2. Every tool call goes through a proxy that logs it out of band, where the agent
     cannot reach the record.
  3. A canary tool returns a value derived from the nonce, so a claimed receipt is
     proof of execution rather than a plausible sentence.
  4. A deterministic scorer compares what the agent CLAIMED against what was LOGGED.
  5. A binding check proves the manifest and the log came from the same run, because
     genuine artifacts from two different runs assemble into a false proof.

Provenance: the method and its correction history come from the Dispatch Fidelity
Benchmark, a pre-registered measurement (OSF 4rgey) deposited at
https://doi.org/10.5281/zenodo.21812041 -- whose correction protocol records the
instrument's own audit findings, not one of which was caught by an aggregate metric.
"""
from .fidelity import (
    AuditSession,
    BindingResult,
    CanaryTools,
    DispatchScore,
    LoggingProxy,
    Verdict,
    check_binding,
    extract_claims,
    score,
)

__version__ = "0.3.1rc1"
__all__ = [
    "AuditSession", "LoggingProxy", "CanaryTools", "DispatchScore", "Verdict",
    "BindingResult", "check_binding", "score", "extract_claims", "__version__",
]
