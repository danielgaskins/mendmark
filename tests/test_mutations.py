from __future__ import annotations

from mendmark.agent_cases import AgentCase, ToolCallRecord, ToolSpec
from mendmark.mutations import generate_mutants


def example_case() -> AgentCase:
    lookup = ToolCallRecord("lookup", {"id": "1"}, {"status": "ready"})
    charge = ToolCallRecord("charge", {"id": "1", "amount": 10}, {"id": "c1"})
    return AgentCase(
        case_id="case-1",
        input="charge it",
        actual_output="charged",
        expected_output="charged",
        tools_called=(lookup, charge),
        expected_tools=(lookup, charge),
    )


def test_default_mutations_cover_agent_tool_failures() -> None:
    tools = (
        ToolSpec("lookup"),
        ToolSpec("charge", side_effecting=True),
    )
    mutants = generate_mutants((example_case(),), tools)
    operators = {mutant.operator for mutant in mutants}

    assert operators == {
        "tool.removed",
        "tool.arguments_changed",
        "tool.output_corrupted",
        "tool.side_effect_duplicated",
        "tool.order_reversed",
        "tool.unknown_added",
        "recovery.false_success",
        "response.omitted",
        "response.replaced",
    }
    assert len({mutant.mutant_id for mutant in mutants}) == len(mutants)


def test_side_effect_mutation_requires_declared_side_effect() -> None:
    tools = (ToolSpec("lookup"), ToolSpec("charge"))
    mutants = generate_mutants((example_case(),), tools)
    assert "tool.side_effect_duplicated" not in {
        mutant.operator for mutant in mutants
    }
