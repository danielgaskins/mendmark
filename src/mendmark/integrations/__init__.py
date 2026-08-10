"""Dependency-light adapters for popular Python agent harnesses.

The adapters use public, duck-typed harness objects so importing Mendmark never
imports or constrains the customer's agent framework.
"""

from .common import HarnessIntegrationError, suite_to_json, write_suite
from .multi_agent import CausalCaseBuilder

__all__ = [
    "HarnessIntegrationError",
    "CausalCaseBuilder",
    "suite_to_json",
    "write_suite",
]
