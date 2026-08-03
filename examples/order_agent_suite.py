"""Small offline DeepEval suite used by the Mendmark quickstart."""

from __future__ import annotations

from deepeval.metrics import BaseMetric, ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall, ToolCallParams


TOOLS = [
    {
        "name": "lookup_order",
        "description": "Fetch an order before changing it",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
        "side_effecting": False,
    },
    {
        "name": "refund_order",
        "description": "Issue a refund after the order has been verified",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["order_id", "amount"],
        },
        "side_effecting": True,
    },
]

MENDMARK_POLICY = {
    "minimum_kill_rate": 1.0,
    "fail_on_critical_survivor": True,
    "fail_on_untested_tools": True,
}


class ExactOutputMetric(BaseMetric):
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
        self.reason = "The final output matches the expected result."
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self) -> str:
        return "Exact outcome"


def get_metrics() -> list[BaseMetric]:
    return [
        ToolCorrectnessMetric(
            threshold=1.0,
            evaluation_params=[
                ToolCallParams.INPUT_PARAMETERS,
                ToolCallParams.OUTPUT,
            ],
            should_consider_ordering=True,
            should_exact_match=True,
            strict_mode=True,
            include_reason=True,
        ),
        ExactOutputMetric(),
    ]


def get_cases() -> list[LLMTestCase]:
    lookup = ToolCall(
        name="lookup_order",
        input_parameters={"order_id": "order-104"},
        output={"status": "paid", "total": 29.99},
    )
    refund = ToolCall(
        name="refund_order",
        input_parameters={"order_id": "order-104", "amount": 29.99},
        output={"refund_id": "refund-8", "status": "accepted"},
    )
    return [
        LLMTestCase(
            name="refund-paid-order",
            input="Refund order 104 in full.",
            actual_output="Refund refund-8 was accepted for $29.99.",
            expected_output="Refund refund-8 was accepted for $29.99.",
            tools_called=[lookup, refund],
            expected_tools=[lookup, refund],
            metadata={"mendmark_case_id": "refund-paid-order"},
        )
    ]
