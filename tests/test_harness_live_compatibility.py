from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from mendmark.integrations.crewai import case_from_events, tool_specs as crewai_tools
from mendmark.integrations.langchain import case_from_messages, tool_specs as lc_tools
from mendmark.integrations.openai_agents import (
    case_from_result,
    tool_specs as openai_tools,
)


PROFILE = os.environ.get("MENDMARK_HARNESS")


@pytest.mark.skipif(PROFILE != "langgraph", reason="LangGraph compatibility profile")
def test_current_langchain_core_public_objects() -> None:
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.tools import tool

    @tool
    def lookup_order(order_id: str) -> str:
        """Look up an order."""
        return order_id

    messages = [
        AIMessage(
            content="",
            tool_calls=[{"name": "lookup_order", "args": {"order_id": "7"}, "id": "c1"}],
        ),
        ToolMessage(content='{"status":"paid"}', tool_call_id="c1"),
        AIMessage(content="Paid."),
    ]
    case = case_from_messages(
        messages,
        case_id="live",
        input="check 7",
        expected_output="Paid.",
        approve_observed=True,
    )
    assert case.tools_called[0].name == "lookup_order"
    assert lc_tools([lookup_order])[0].input_schema["required"] == ["order_id"]


@pytest.mark.skipif(PROFILE != "openai-agents", reason="OpenAI Agents compatibility profile")
def test_current_openai_agents_public_objects() -> None:
    from agents import Agent, ToolCallItem, ToolCallOutputItem, function_tool

    @function_tool
    def lookup_order(order_id: str) -> str:
        """Look up an order."""
        return order_id

    agent = Agent(name="billing", tools=[lookup_order])
    call = ToolCallItem(
        agent=agent,
        raw_item={
            "type": "function_call",
            "name": "lookup_order",
            "arguments": '{"order_id":"7"}',
            "call_id": "c1",
        },
    )
    output = ToolCallOutputItem(
        agent=agent,
        raw_item={"type": "function_call_output", "call_id": "c1", "output": "paid"},
        output="paid",
    )
    case = case_from_result(
        SimpleNamespace(new_items=[call, output], final_output="Paid."),
        case_id="live",
        input="check 7",
        expected_output="Paid.",
        approve_observed=True,
    )
    assert case.tools_called[0].output == "paid"
    assert openai_tools([lookup_order])[0].input_schema["required"] == ["order_id"]


@pytest.mark.skipif(PROFILE != "crewai", reason="CrewAI compatibility profile")
def test_current_crewai_public_objects() -> None:
    from crewai.events.types.tool_usage_events import ToolUsageFinishedEvent
    from crewai.tools import BaseTool

    class LookupOrder(BaseTool):
        name: str = "lookup_order"
        description: str = "Look up an order"

        def _run(self, order_id: str) -> str:
            return order_id

    tool = LookupOrder()
    now = datetime.now(timezone.utc)
    event = ToolUsageFinishedEvent(
        tool_name="lookup_order",
        tool_args={"order_id": "7"},
        output="paid",
        started_at=now,
        finished_at=now,
    )
    case = case_from_events(
        [event, SimpleNamespace(type="agent_execution_completed", output="Paid.")],
        case_id="live",
        input="check 7",
        expected_output="Paid.",
        approve_observed=True,
    )
    assert case.tools_called[0].output == "paid"
    assert crewai_tools([tool])[0].input_schema["type"] == "object"
