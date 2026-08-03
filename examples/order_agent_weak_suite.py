"""Deliberately weak agent eval used to demonstrate surviving mutations."""

from __future__ import annotations

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from order_agent_suite import TOOLS, get_cases


MENDMARK_POLICY = {
    "minimum_kill_rate": 1.0,
    "fail_on_critical_survivor": True,
    "fail_on_untested_tools": True,
}


class FinalResponseOnlyMetric(BaseMetric):
    """Pass when the final response matches, regardless of tool behavior."""

    def __init__(self) -> None:
        self.threshold = 1.0
        self.score = 0.0
        self.success = False
        self.reason = None
        self.error = None
        self.async_mode = False

    def measure(self, test_case: LLMTestCase) -> float:
        self.score = float(test_case.actual_output == test_case.expected_output)
        self.success = self.score == 1.0
        self.reason = "The final response matches the expected response."
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self) -> str:
        return "Final response only"


def get_metrics() -> list[BaseMetric]:
    return [FinalResponseOnlyMetric()]
