"""Fault injection: proving the scorer catches what it claims to catch."""
from .classes import CLASSES, InjectionClass
from .validate import Row, run

__all__ = ["CLASSES", "InjectionClass", "Row", "run"]
