from __future__ import annotations

import json
from importlib import resources
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from mendmark.agent_cases import AgentCase
from mendmark.json_adapter import JsonCommandEvaluator
from mendmark.json_adapter import JsonAdapterError


def schema(name: str) -> dict:
    path = resources.files("mendmark").joinpath("schemas", name)
    return json.loads(path.read_text(encoding="utf-8"))


def test_batch_protocol_conforms_and_invokes_evaluator_once(monkeypatch) -> None:
    request_schema = schema("evaluator-request-v1.schema.json")
    response_schema = schema("evaluator-response-v1.schema.json")
    suite_schema = schema("suite-v1.schema.json")
    registry = Registry().with_resource(
        suite_schema["$id"], Resource.from_contents(suite_schema)
    )
    calls = []

    def run(command, **kwargs):
        request = json.loads(kwargs["input"])
        Draft202012Validator(request_schema, registry=registry).validate(request)
        calls.append(request)
        response = {
            "schema_version": "1.0",
            "evaluations": [
                {
                    "evaluation_id": item["evaluation_id"],
                    "results": [{"name": "always", "passed": True, "score": 1}],
                }
                for item in request["evaluations"]
            ],
        }
        Draft202012Validator(response_schema).validate(response)
        return SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr="")

    monkeypatch.setattr("mendmark.json_adapter.subprocess.run", run)
    evaluator = JsonCommandEvaluator(("evaluator",))
    cases = (
        AgentCase("case-a", "input", "output"),
        AgentCase("case-b", "input", "output"),
    )

    results = evaluator.evaluate_many(cases)

    assert len(calls) == 1
    assert [item["evaluation_id"] for item in calls[0]["evaluations"]] == [
        "evaluation-0",
        "evaluation-1",
    ]
    assert [result[0].name for result in results] == ["always", "always"]


def test_evaluator_batches_large_suites_without_reordering(monkeypatch) -> None:
    calls = []

    def run(command, **kwargs):
        request = json.loads(kwargs["input"])
        calls.append(request)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "schema_version": request["schema_version"],
                    "evaluations": [
                        {
                            "evaluation_id": item["evaluation_id"],
                            "results": [
                                {"name": "always", "passed": True, "score": 1}
                            ],
                        }
                        for item in request["evaluations"]
                    ],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("mendmark.json_adapter.subprocess.run", run)
    evaluator = JsonCommandEvaluator(("evaluator",), batch_size=2)
    cases = tuple(
        AgentCase(f"case-{index}", "input", "output") for index in range(5)
    )

    results = evaluator.evaluate_many(cases)

    assert len(results) == 5
    assert [len(call["evaluations"]) for call in calls] == [2, 2, 1]


def test_evaluator_rejects_oversized_request_before_spawn(monkeypatch) -> None:
    def unexpected_run(*args, **kwargs):
        raise AssertionError("evaluator must not be spawned")

    monkeypatch.setattr("mendmark.json_adapter.subprocess.run", unexpected_run)
    evaluator = JsonCommandEvaluator(("evaluator",), maximum_request_bytes=10)

    with pytest.raises(JsonAdapterError, match="request exceeds"):
        evaluator.evaluate(AgentCase("case", "input", "output"))
