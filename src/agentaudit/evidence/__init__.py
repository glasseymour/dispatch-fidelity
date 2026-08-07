"""Evidence discipline: is the green result you are looking at evidence about THIS code?

Dispatch fidelity asks whether an agent's claims about tool calls are true. This module
asks the same question one level out, about the agent's claims that its checks passed.
Three guards:

  BINDING  the recorded run came from the tree currently on disk, and it exited 0.
           A result belonging to another tree state is genuine and irrelevant.
  ANCHOR   numbers fixed BEFORE the change still hold. Re-reading the output you just
           produced is not verification.
  WAIVER   every suppression (skip, xfail, ignore, disable) is declared with a reason.
           An undeclared exception looks the same whether it was deliberate or an accident.

The writer (`gate`) and the reader (`verify`) are separate programs on purpose. The
failure being guarded against is a checker that inspects its own output: a verifier that
regenerates the evidence it verifies can never report a discrepancy.
"""
from .gate import tree_digest

__all__ = ["tree_digest"]
