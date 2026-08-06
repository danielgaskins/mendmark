from __future__ import annotations

from pathlib import Path

from mendmark.audit import run_audit
from mendmark.deepeval import load_deepeval_suite


PROJECT_ROOT = Path(__file__).parents[1]


def test_example_deepeval_suite_kills_every_builtin_mutation() -> None:
    suite = load_deepeval_suite(PROJECT_ROOT / "examples" / "order_agent_suite.py")
    report = run_audit(
        cases=suite.cases,
        tools=suite.tools,
        evaluator=suite.evaluator,
        policy=suite.policy,
    )

    assert report["summary"] == {
        "cases": 1,
        "mutants": 19,
        "killed": 19,
        "survived": 0,
        "errors": 0,
        "kill_rate": 1.0,
        "critical_survivors": 0,
    }
    assert report["gate"]["passed"] is True
    assert report["tools"]["untested"] == []
