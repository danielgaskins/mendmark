"""Export Mendmark fault-injected traces as paired counterfactual JSONL for LatchGate calibration.

Mendmark discovers silent evaluator and workflow blind spots in CI; ``export_latchgate_pairs``
converts clean baseline cases and their planted fault mutations into the ``latchgate.pair.v1``
counterfactual JSONL contract consumed by ``latchgate fit``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_cases import AgentCase, ToolCallRecord, ToolSpec
from .mutations import (
    AGENT_EVAL_V1_MUTATIONS,
    DEFAULT_MUTATIONS,
    MULTI_AGENT_V1_MUTATIONS,
    OUTCOME_FIRST_MUTATIONS,
    Mutant,
    MutationOperator,
    generate_mutants,
)

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _serialize_tool_calls_and_output(case: AgentCase) -> str:
    """Format a case's ordered tool trace and final output into a canonical completion string."""
    lines: list[str] = []
    calls: tuple[ToolCallRecord, ...] = case.actual_tool_calls()
    for call in calls:
        payload = {
            "tool": call.name,
            "arguments": call.input_parameters,
        }
        if call.output is not None:
            payload["output"] = call.output
        lines.append("TOOL_CALL: " + json.dumps(payload, sort_keys=True, separators=(",", ":")))
    if case.outcome is not None and case.outcome.actual_state:
        lines.append(
            "OUTCOME_STATE: "
            + json.dumps(case.outcome.actual_state, sort_keys=True, separators=(",", ":"))
        )
    if case.actual_output:
        lines.append(case.actual_output.strip())
    return "\n".join(lines)


def _system_tool_contract(tools: tuple[ToolSpec, ...]) -> str:
    if not tools:
        return "Execute only authorized tool calls that satisfy declared schemas and outcome invariants."
    summaries = []
    for tool in tools:
        req = tool.input_schema.get("required", [])
        req_str = ",".join(str(r) for r in req) if isinstance(req, list) else ""
        side = "side_effecting" if tool.side_effecting else "read_only"
        summaries.append(f"{tool.name}({req_str}) [{side}]")
    return (
        "Available tool contracts: "
        + "; ".join(summaries)
        + ". Emit faithful TOOL_CALL records before summarizing the outcome."
    )


def _load_survivor_ids(report_path: str | Path) -> set[str]:
    resolved = Path(report_path).expanduser().resolve()
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Mendmark report does not exist: {resolved}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in Mendmark report: {resolved}") from error
    if not isinstance(data, dict) or not isinstance(data.get("mutations"), list):
        raise ValueError(f"invalid Mendmark report structure: {resolved}")
    return {
        str(item["mutant_id"])
        for item in data["mutations"]
        if isinstance(item, dict) and item.get("status") == "survived" and "mutant_id" in item
    }


def build_latchgate_pairs(
    cases: tuple[AgentCase, ...],
    tools: tuple[ToolSpec, ...],
    *,
    operators: tuple[MutationOperator, ...] = DEFAULT_MUTATIONS,
    min_severity: str = "high",
    survivor_mutant_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Build ``latchgate.pair.v1`` counterfactual dictionaries from ``cases`` and ``operators``."""
    if min_severity not in _SEVERITY_RANK:
        raise ValueError(
            "min_severity must be one of: " + ", ".join(sorted(_SEVERITY_RANK))
        )
    min_rank = _SEVERITY_RANK[min_severity]
    cases_by_id = {case.case_id: case for case in cases}
    mutants: list[Mutant] = generate_mutants(cases, tools, operators)
    sys_prompt = _system_tool_contract(tools)

    pairs: list[dict[str, Any]] = []
    for mutant in mutants:
        if _SEVERITY_RANK.get(mutant.severity, 0) < min_rank:
            continue
        if survivor_mutant_ids is not None and mutant.mutant_id not in survivor_mutant_ids:
            continue
        base_case = cases_by_id[mutant.source_case_id]
        honest_completion = _serialize_tool_calls_and_output(base_case)
        bad_completion = _serialize_tool_calls_and_output(mutant.case)
        if honest_completion == bad_completion:
            continue

        honest_messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": base_case.input},
        ]
        bad_messages = [
            {
                "role": "system",
                "content": (
                    f"{sys_prompt} Operational fault pressure ({mutant.operator}): "
                    f"{mutant.description}."
                ),
            },
            {"role": "user", "content": mutant.case.input},
        ]

        pairs.append(
            {
                "schema_version": "latchgate.pair.v1",
                "pair_id": mutant.mutant_id,
                "honest_messages": honest_messages,
                "bad_messages": bad_messages,
                "honest_completion": honest_completion,
                "bad_completion": bad_completion,
                "category": mutant.operator,
                "severity": mutant.severity,
                "metadata": {
                    "source_case_id": mutant.source_case_id,
                    "mutation_category": mutant.category,
                    "tool_name": mutant.tool_name,
                    "agent_id": mutant.agent_id,
                    "event_id": mutant.event_id,
                },
            }
        )
    return pairs


def export_latchgate_pairs(
    suite_path: str | Path,
    output_path: str | Path,
    *,
    mutation_profile: str = "current",
    min_severity: str = "high",
    survivors_from: str | Path | None = None,
) -> dict[str, Any]:
    """Export paired counterfactual traces from a Mendmark JSON or DeepEval Python suite to JSONL."""
    resolved_suite = Path(suite_path).expanduser().resolve()
    if not resolved_suite.is_file():
        raise ValueError(f"suite file does not exist: {resolved_suite}")

    profile_map = {
        "current": DEFAULT_MUTATIONS,
        "agent-eval-v1": AGENT_EVAL_V1_MUTATIONS,
        "multi-agent-v1": MULTI_AGENT_V1_MUTATIONS,
        "outcome-first": OUTCOME_FIRST_MUTATIONS,
    }
    if mutation_profile not in profile_map:
        raise ValueError(f"unsupported mutation profile: {mutation_profile!r}")

    if resolved_suite.suffix.lower() == ".py":
        from .deepeval import load_deepeval_suite

        loaded_py = load_deepeval_suite(resolved_suite)
        cases = loaded_py.cases
        tools = loaded_py.tools
        operators = loaded_py.operators if mutation_profile == "current" else profile_map[mutation_profile]
    else:
        from .json_adapter import load_json_suite

        loaded_json = load_json_suite(resolved_suite)
        cases = loaded_json.cases
        tools = loaded_json.tools
        operators = profile_map[mutation_profile]

    survivor_ids = _load_survivor_ids(survivors_from) if survivors_from is not None else None
    pairs = build_latchgate_pairs(
        cases,
        tools,
        operators=operators,
        min_severity=min_severity,
        survivor_mutant_ids=survivor_ids,
    )

    out_file = Path(output_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(row, sort_keys=True) + "\n" for row in pairs)
    out_file.write_text(body, encoding="utf-8")

    return {
        "exported_pairs": len(pairs),
        "cases": len(cases),
        "min_severity": min_severity,
        "filtered_to_survivors": survivor_ids is not None,
        "output_path": str(out_file),
    }
