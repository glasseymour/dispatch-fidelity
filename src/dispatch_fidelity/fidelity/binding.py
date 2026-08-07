"""Run binding -- do the manifest and the tool log belong to the same run?

This module exists because of an external finding. The original deposit shipped a seal
chain and a file manifest, both green, and a reader pointed out that they prove
file-level integrity only: each file is unmodified and is what it claims to be. Neither
says anything about whether two files BELONG TOGETHER. Genuine, hash-valid artifacts
drawn from different runs assemble into an evidence set that passes every check while
describing a run that never happened.

Nothing is modified in such an attack, so hashing cannot see it. What sees it is a
binding: a value that could only have been produced by these two files coming from one
execution.

Five checks, weakest to strongest:

  B1  the manifest's run_id matches its filename
  B2  the tool log's run_id is uniform and its sequence numbers have no gaps
  B3  sha256(nonce recovered from the log) equals the manifest's pre-run commitment
  B4  the manifest and the log agree on run_id
  B5  the log's records all carry the same run_id as the manifest

B3 is the load-bearing one, and it is the only one that cannot be forged by relabelling.
It is also the only one that can be UNPROVABLE rather than false: if no canary was called
during a run, the nonce never entered the log and there is nothing to recover. Unproven
is not unsound. Those runs are reported separately instead of being folded into either
total, because a check that can never pass is as uninformative as one that can never fail.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .nonce import load_manifest
from .proxy import load_log

# THE CANARY RECEIPT FORMAT IS A CONTRACT, not an implementation detail. B3 recovers
# the plaintext nonce by reading it out of a receipt, so a canary that returns the value
# in some other shape leaves the binding silently `unprovable` -- correctly reported, and
# easy to miss if you did not know the format mattered. Anyone writing their own canary
# (which is the normal case behind an MCP relay) must either match this pattern or pass
# their own via `nonce_pattern`. Documented in README and docs/method.md after external
# review, 2026-08-07.
NONCE_RE = re.compile(r"CANARY\[[^\]]*\]:([0-9a-f]{16,})")


PROVEN, UNPROVEN, FAILED = "PROVEN", "UNPROVEN", "FAILED"


@dataclass
class BindingResult:
    run_id: str
    checks: dict = field(default_factory=dict)
    unprovable: list = field(default_factory=list)
    findings: list = field(default_factory=list)

    @property
    def status(self) -> str:
        """PROVEN, UNPROVEN or FAILED -- three states, because there are three.

        Finding #19, and it reverses an earlier decision in this file. `bound` used to
        mean "no explicit finding", which made an UNPROVEN run indistinguishable from a
        proven one at every machine boundary. The documentation drew the distinction
        correctly and the code collapsed it, which is the worse of the two ways to be
        inconsistent.

        The sharpest case: a manifest with an EMPTY tool log passed every check. B1 held,
        an empty sequence is trivially gap-free, B4 and B5 have nothing to contradict, and
        B3 was merely unprovable -- so `bind` printed BOUND over evidence containing no
        evidence. It now returns UNPROVEN, which exits 2, not 0.

        This matters most behind an MCP relay, where the documentation already says the
        canary cannot be injected and B3 will be unprovable. Every such run was reporting
        a successful binding.
        """
        if self.findings:
            return FAILED
        if any(v is None for v in self.checks.values()):
            return UNPROVEN
        return PROVEN

    @property
    def bound(self) -> bool:
        """Kept for callers, now meaning exactly what the word says: B3 was derived."""
        return self.status == PROVEN

    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "checks": self.checks,
                "unprovable": self.unprovable, "findings": self.findings,
                "status": self.status, "bound": self.bound}


def recover_nonce(log_records: list[dict], nonce_pattern=None) -> str | None:
    """Pull the plaintext nonce out of a canary receipt in the log.

    Only `canary_probe` returns it verbatim; a run that used the checksum canary alone
    leaves B3 unprovable, which is reported rather than hidden.

    `nonce_pattern` accepts a compiled regex whose first group is the nonce, for canaries
    that use a different receipt shape.
    """
    rx = nonce_pattern or NONCE_RE
    if isinstance(rx, str):
        rx = re.compile(rx)
    for rec in log_records:
        m = rx.search(str(rec.get("result", "")))
        if m:
            return m.group(1)
    return None


def check_binding(manifest_path: Path, log_path: Path, nonce_pattern=None) -> BindingResult:
    manifest_path, log_path = Path(manifest_path), Path(log_path)
    manifest = load_manifest(manifest_path)
    records = load_log(log_path)
    run_id = str(manifest.get("run_id", ""))
    r = BindingResult(run_id=run_id)

    stem = manifest_path.name.replace(".manifest.json", "")
    r.checks["B1_manifest_self_identifies"] = (stem == run_id)
    if stem != run_id:
        r.findings.append(f"B1: manifest run_id {run_id!r} does not match filename {stem!r}")

    # Finding #24. Damage to the log used to enter `findings`, which made the binding
    # FAILED, which `decide` treats as a hard failure -- so the same torn log produced
    # INCONCLUSIVE without a manifest and FAIL with one. Two paths, two verdicts, one
    # input. Incomplete evidence is not proven falsehood: the text already said "no
    # result over it is conclusive", and now the state agrees with the sentence.
    log_damage = list(getattr(records, "findings", lambda: [])())
    if log_damage:
        r.checks["B0_log_intact"] = None
        r.unprovable.extend(f"B0: {f}" for f in log_damage)

    if not records:
        r.unprovable.append(
            "B0: the tool log holds no records, so every check below is trivially "
            "satisfiable -- there is nothing here to bind"
        )
        r.checks["B0_log_has_records"] = None
    else:
        r.checks["B0_log_has_records"] = True

    log_ids = {str(rec.get("run_id")) for rec in records}
    seqs = [rec.get("seq") for rec in records if isinstance(rec.get("seq"), int)]
    gapless = seqs == list(range(1, len(records) + 1))
    r.checks["B2_log_self_identifies"] = (len(log_ids) <= 1 and gapless)
    if len(log_ids) > 1:
        r.findings.append(f"B2: tool log mixes run ids {sorted(log_ids)}")
    if records and not gapless:
        r.findings.append("B2: tool log sequence numbers have gaps or repeats")

    committed = str(manifest.get("nonce_sha256", ""))
    recovered = recover_nonce(records, nonce_pattern)
    if not committed:
        r.checks["B3_nonce_commitment"] = None
        r.unprovable.append("B3: the manifest carries no nonce commitment")
    elif recovered is None:
        r.checks["B3_nonce_commitment"] = None
        r.unprovable.append(
            "B3: no recoverable canary receipt in the log, so the nonce cannot be "
            "recovered -- UNPROVEN, which is a different claim from unsound. If this run "
            "DID call a canary, check its receipt format: B3 reads the nonce with the "
            "pattern CANARY[label]:<hex>, and a custom canary needs `nonce_pattern`"
        )
    else:
        ok = hashlib.sha256(recovered.encode()).hexdigest() == committed
        r.checks["B3_nonce_commitment"] = ok
        if not ok:
            r.findings.append(
                "B3: the nonce in the tool log does not match the manifest's pre-run "
                "commitment -- these two files are not from the same run"
            )

    r.checks["B4_manifest_log_agree"] = (not log_ids or log_ids == {run_id})
    if log_ids and log_ids != {run_id}:
        r.findings.append(f"B4: manifest run_id {run_id!r} absent from the tool log")

    stray = [rec.get("seq") for rec in records if str(rec.get("run_id")) != run_id]
    r.checks["B5_no_stray_records"] = not stray
    if stray:
        r.findings.append(f"B5: {len(stray)} log record(s) carry a different run id")

    return r
