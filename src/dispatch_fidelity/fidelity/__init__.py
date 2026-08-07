"""Dispatch fidelity: did the agent actually call what it says it called?"""
from .binding import BindingResult, check_binding
from .canary import CANARY_TOOL_NAMES, CanaryTools
from .nonce import new_nonce, nonce_commitment, seal_manifest
from .proxy import LoggingProxy, load_log
from .report import render
from .scorer import DispatchScore, Verdict, extract_claims, receipt_matches, score
from .session import AuditSession

__all__ = [
    "AuditSession", "LoggingProxy", "CanaryTools", "DispatchScore", "Verdict",
    "BindingResult", "check_binding", "score", "extract_claims", "receipt_matches",
    "render", "load_log", "new_nonce", "nonce_commitment", "seal_manifest",
    "CANARY_TOOL_NAMES",
]
