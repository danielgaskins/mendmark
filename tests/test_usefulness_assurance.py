from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from mendmark.cli import main
from mendmark.json_adapter import load_json_suite
from mendmark.mutations import generate_mutants


PROJECT_ROOT = Path(__file__).parents[1]
MULTI_SUITE = PROJECT_ROOT / "examples" / "multi_agent_suite.json"


def test_independent_multi_agent_event_order_is_not_a_false_positive(
    tmp_path: Path,
) -> None:
    document = json.loads(MULTI_SUITE.read_text(encoding="utf-8"))
    events = document["cases"][0]["events"]
    events[0], events[1] = events[1], events[0]
    reordered_suite = tmp_path / "reordered-suite.json"
    reordered_suite.write_text(json.dumps(document), encoding="utf-8")
    report_path = tmp_path / "report.json"

    result = main(
        [
            "audit-json",
            str(reordered_suite),
            "--evaluator-command",
            f"{sys.executable} {PROJECT_ROOT / 'examples' / 'multi_agent_evaluator.py'}",
            "--output",
            str(report_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result == 0
    assert report["gate"]["passed"] is True
    assert report["summary"]["killed"] == report["summary"]["mutants"] == 44


def test_output_only_multi_agent_evaluator_exposes_coordination_blind_spots(
    tmp_path: Path, capsys: object
) -> None:
    report_path = tmp_path / "weak-report.json"

    result = main(
        [
            "audit-json",
            str(MULTI_SUITE),
            "--evaluator-command",
            f"{sys.executable} {PROJECT_ROOT / 'examples' / 'multi_agent_weak_evaluator.py'}",
            "--output",
            str(report_path),
        ]
    )

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result == 1
    assert report["summary"] == {
        "cases": 1,
        "mutants": 44,
        "killed": 5,
        "survived": 39,
        "errors": 0,
        "kill_rate": 0.113636,
        "critical_survivors": 27,
    }
    assert report["coverage"]["by_category"]["coordination"]["survived"] == 6
    assert report["coverage"]["by_category"]["causality"]["survived"] == 8
    assert report["coverage"]["by_operator"]["delegation.removed"]["survived"] == 2
    assert "Survivors by category:" in output
    assert "coordination=6" in output
    assert "agent=billing" in output
    assert "event=billing-result" in output
    assert "27 critical mutation(s) survived" in output


def test_built_in_mutations_are_non_noop_and_preserve_eval_oracles() -> None:
    for suite_path in (
        PROJECT_ROOT / "examples" / "order_agent_suite.json",
        MULTI_SUITE,
    ):
        suite = load_json_suite(suite_path)
        originals = copy.deepcopy(suite.cases)

        mutants = generate_mutants(suite.cases, suite.tools)

        assert mutants
        by_id = {case.case_id: case for case in suite.cases}
        assert len({mutant.mutant_id for mutant in mutants}) == len(mutants)
        for mutant in mutants:
            source = by_id[mutant.source_case_id]
            assert mutant.case != source
            assert mutant.case.expected_output == source.expected_output
            assert mutant.case.expected_tools == source.expected_tools
            assert mutant.case.expected_events == source.expected_events
            assert mutant.case.agents == source.agents
            assert mutant.case.metadata == source.metadata
            assert mutant.case.tags == source.tags
        assert suite.cases == originals
