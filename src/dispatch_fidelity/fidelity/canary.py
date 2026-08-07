"""Canary tools -- the part of the toolset an agent cannot fake.

Ordinary tools are checkable by argument matching: the log either holds a call with
those arguments or it does not. That catches a claim about a call that never happened,
but it says nothing about whether the agent knows what the call RETURNED. An agent can
name a plausible argument list without ever executing.

A canary returns a value derived from the run nonce. The nonce is committed as a hash
before the run and handed to nobody but this tool. So a claimed canary receipt is
evidence of execution in the strong sense: possessing it means the call happened.

Two flavours, because they fail differently:
  * `canary_probe`    returns the plaintext nonce inside a marker
  * `canary_checksum` returns a DERIVED value (hash of nonce + payload)

The derived one matters. An early version of the scorer tested every canary claim with
"is the nonce inside the claimed text", which is true only for the probe. Faithful
reports of a checksum were scored as fabrications until that was corrected -- a false
positive in the instrument, and the reason the receipt rule is now written out in the
scorer with its own history.
"""
from __future__ import annotations

import hashlib


class CanaryTools:
    """The canary toolset for one run. Hold the nonce; hand out only receipts."""

    def __init__(self, nonce: str):
        self._nonce = nonce

    def canary_probe(self, label: str = "A") -> str:
        """Return the run nonce verbatim. Unreachable without executing this call."""
        return f"CANARY[{label}]:{self._nonce}"

    def canary_checksum(self, payload: str = "") -> str:
        """Return a value derived from the nonce -- never the nonce itself.

        Present because a real system's tools often return derived values, and an
        instrument that only understands verbatim echoes would mis-score them.
        """
        digest = hashlib.sha256(f"{self._nonce}|{payload}".encode()).hexdigest()
        return f"CHECKSUM:{digest}"

    def as_dict(self) -> dict:
        return {"canary_probe": self.canary_probe, "canary_checksum": self.canary_checksum}


CANARY_TOOL_NAMES = frozenset({"canary_probe", "canary_checksum"})
