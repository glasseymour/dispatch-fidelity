"""Per-run nonce and the sealed run manifest.

The nonce is the reason this instrument can tell a real tool call from a convincing
sentence about one. It is generated before the run, committed to the manifest as a
SHA-256 hash, and handed only to the canary tool. An agent can obtain the plaintext
value in exactly one way: by actually calling the canary. Any other route -- guessing,
paraphrasing, remembering a previous run -- produces a receipt the log never issued.

The hash commitment is what makes the manifest and the tool log cryptographically
bound to each other. Both files must agree, and neither can be swapped in from another
run without the mismatch showing. That binding was added after an external finding
(item #15 of the correction protocol) pointed out that file-level integrity proves a
file is unmodified, not that two files belong together.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path


def new_nonce() -> str:
    """A fresh 128-bit nonce, hex encoded.

    `secrets` rather than `random`: the value must be unguessable, because the entire
    canary argument rests on an agent being unable to produce it without executing.
    """
    return secrets.token_hex(16)


def nonce_commitment(nonce: str) -> str:
    """The value stored in the manifest. The plaintext never touches disk."""
    return hashlib.sha256(nonce.encode()).hexdigest()


def seal_manifest(run_id: str, nonce: str, out_dir: Path, *, system: dict | None = None,
                  task_id: str | None = None, notes: str | None = None) -> Path:
    """Write the run manifest BEFORE the agent starts.

    Writing it afterwards would make the commitment worthless: a manifest built from a
    finished run can be made to agree with anything the run happened to produce.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "dispatch-fidelity/manifest/1",
        "run_id": run_id,
        "task_id": task_id,
        "nonce_sha256": nonce_commitment(nonce),
        "system": system or {},
        "notes": notes,
        "sealed_at": datetime.now(timezone.utc).isoformat(),
    }
    path = out_dir / f"{run_id}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_manifest(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def receipt_contains_nonce(claimed_text: str, nonce: str) -> bool:
    """Plain containment, used only where the canary returns the nonce verbatim.

    The scorer's receipt rule is stricter and lives in `scorer._receipt_matches`; this
    helper exists for callers writing their own canary tools.
    """
    return bool(nonce) and nonce in (claimed_text or "")
