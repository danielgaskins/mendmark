from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from mendmark.ci_outputs import write_junit, write_sarif


def report() -> dict:
    return {
        "gate": {"passed": False, "failures": ["1 critical mutation survived"]},
        "mutations": [
            {
                "mutant_id": "case:domain.bad:one",
                "source_case_id": "case",
                "operator": "domain.bad",
                "description": "A domain failure was introduced",
                "severity": "critical",
                "tool_name": "charge",
                "status": "survived",
                "evaluation_errors": [],
            }
        ],
        "tools": {"contract_issues": []},
        "regressions": {"regressed": []},
        "provenance": {"mendmark_version": "0.4.0"},
    }


def test_junit_contains_privacy_safe_mutation_failure(tmp_path: Path) -> None:
    path = tmp_path / "mendmark.xml"
    write_junit(path, report())

    root = ET.parse(path).getroot()
    assert root.attrib["failures"] == "2"
    failure = root.find("./testcase/failure")
    assert failure is not None
    assert "case=case" in (failure.text or "")


def test_sarif_contains_survivor_rule(tmp_path: Path) -> None:
    path = tmp_path / "mendmark.sarif"
    write_sarif(path, report())

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == "2.1.0"
    result = data["runs"][0]["results"][0]
    assert result["ruleId"] == "mendmark/domain.bad"
    assert result["level"] == "error"
