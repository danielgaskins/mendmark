from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from mendmark.agent_cases import (
    AgentCase,
    AgentEvent,
    AgentSpec,
    ToolCallRecord,
    ToolSpec,
    case_graph_issues,
)
from mendmark.json_adapter import JsonAdapterError, JsonCommandEvaluator, load_json_suite
from mendmark.mutations import generate_mutants


def minimal_suite(case_id: str = "case") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "tools": [],
        "cases": [{"case_id": case_id, "input": "input", "actual_output": "ok"}],
    }


def test_suite_rejects_invalid_utf8_without_traceback(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_bytes(b'{"schema_version":"1.0","cases":[]}' + b"\xff")

    with pytest.raises(JsonAdapterError, match="not valid UTF-8"):
        load_json_suite(path)


def test_suite_rejects_excessive_json_nesting(tmp_path: Path) -> None:
    document = minimal_suite()
    nested: object = "value"
    for _ in range(70):
        nested = {"next": nested}
    document["cases"][0]["metadata"] = {"nested": nested}  # type: ignore[index]
    path = tmp_path / "nested.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(JsonAdapterError, match="nesting limit"):
        load_json_suite(path)


def test_suite_rejects_unbounded_identifier_length(tmp_path: Path) -> None:
    path = tmp_path / "long-id.json"
    path.write_text(json.dumps(minimal_suite("x" * 513)), encoding="utf-8")

    with pytest.raises(JsonAdapterError, match="at most 512 characters"):
        load_json_suite(path)


def test_evaluator_response_byte_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    response = json.dumps(
        {
            "schema_version": "1.0",
            "evaluations": [
                {
                    "evaluation_id": "evaluation-0",
                    "results": [{"name": "metric", "passed": True}],
                }
            ],
        }
    )
    monkeypatch.setattr(
        "mendmark.json_adapter.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=response, stderr=""
        ),
    )
    evaluator = JsonCommandEvaluator(("evaluator",), maximum_output_bytes=10)

    with pytest.raises(JsonAdapterError, match="response exceeds"):
        evaluator.evaluate(AgentCase("case", "input", "output"))


def generated_graph(seed: int) -> tuple[AgentCase, tuple[ToolSpec, ...]]:
    randomizer = random.Random(seed)
    root = AgentSpec("root", allowed_tools=())
    workers = tuple(
        AgentSpec(f"worker-{index}", allowed_tools=("lookup",))
        for index in range(3)
    )
    events: list[AgentEvent] = []
    result_ids = []
    for index, worker in enumerate(workers):
        delegation_id = f"delegate-{index}"
        tool_id = f"tool-{index}"
        result_id = f"result-{index}"
        events.extend(
            [
                AgentEvent(
                    delegation_id,
                    "delegation",
                    "root",
                    worker.agent_id,
                    payload={"request_id": f"request-{index}", "seed": seed},
                ),
                AgentEvent(
                    tool_id,
                    "tool_call",
                    worker.agent_id,
                    depends_on=(delegation_id,),
                    tool_call=ToolCallRecord(
                        "lookup",
                        {"record_id": f"record-{seed}-{index}"},
                        {"value": randomizer.randint(0, 1000)},
                    ),
                ),
                AgentEvent(
                    result_id,
                    "agent_result",
                    worker.agent_id,
                    "root",
                    depends_on=(tool_id,),
                    payload={"request_id": f"request-{index}", "status": "ready"},
                ),
            ]
        )
        result_ids.append(result_id)
    events.append(
        AgentEvent(
            "aggregate",
            "message",
            "root",
            depends_on=tuple(result_ids),
            payload={"status": "complete"},
        )
    )
    randomizer.shuffle(events)
    case = AgentCase(
        f"generated-{seed}",
        "process records",
        "complete",
        expected_output="complete",
        agents=(root,) + workers,
        events=tuple(events),
        expected_events=tuple(events),
        root_agent_id="root",
    )
    return case, (ToolSpec("lookup"),)


@pytest.mark.parametrize("seed", range(20))
def test_generated_valid_dags_have_stable_non_noop_mutations(seed: int) -> None:
    case, tools = generated_graph(seed)
    original = copy.deepcopy(case)

    first = generate_mutants((case,), tools)
    second = generate_mutants((case,), tools)

    assert not case_graph_issues(case)
    assert tuple(item.mutant_id for item in first) == tuple(
        item.mutant_id for item in second
    )
    assert len({item.mutant_id for item in first}) == len(first)
    for mutant in first:
        assert mutant.case != case
        assert mutant.case.expected_output == case.expected_output
        assert mutant.case.expected_events == case.expected_events
        assert not case_graph_issues(mutant.case)
    assert case == original
