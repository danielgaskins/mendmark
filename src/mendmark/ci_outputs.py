"""Privacy-safe CI report renderers for Mendmark audit metadata."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def write_junit(path: str | Path, report: dict[str, Any]) -> None:
    """Write mutation and gate outcomes as JUnit XML."""
    mutations = report["mutations"]
    gate_failures = report["gate"]["failures"]
    failures = sum(item["status"] == "survived" for item in mutations)
    errors = sum(item["status"] == "error" for item in mutations)
    suite = ET.Element(
        "testsuite",
        {
            "name": "mendmark",
            "tests": str(len(mutations) + 1),
            "failures": str(failures + bool(gate_failures)),
            "errors": str(errors),
        },
    )
    for item in mutations:
        test = ET.SubElement(
            suite,
            "testcase",
            {"classname": f"mendmark.{item['operator']}", "name": item["mutant_id"]},
        )
        if item["status"] == "survived":
            failure = ET.SubElement(
                test,
                "failure",
                {"type": "survived-mutation", "message": item["description"]},
            )
            failure.text = (
                f"severity={item['severity']}; case={item['source_case_id']}; "
                f"tool={item['tool_name'] or 'none'}"
            )
        elif item["status"] == "error":
            error = ET.SubElement(
                test,
                "error",
                {"type": "evaluator-error", "message": "Evaluator error"},
            )
            error.text = ", ".join(item["evaluation_errors"])
    policy = ET.SubElement(
        suite, "testcase", {"classname": "mendmark", "name": "release-policy"}
    )
    if gate_failures:
        failure = ET.SubElement(
            policy,
            "failure",
            {"type": "policy-failure", "message": "Mendmark release gate failed"},
        )
        failure.text = "\n".join(gate_failures)
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(destination, encoding="utf-8", xml_declaration=True)


def _sarif_result(
    rule_id: str, message: str, *, level: str = "error"
) -> dict[str, Any]:
    return {"ruleId": rule_id, "level": level, "message": {"text": message}}


def write_sarif(path: str | Path, report: dict[str, Any]) -> None:
    """Write survivors, evaluator errors, contracts, and regressions as SARIF."""
    results: list[dict[str, Any]] = []
    rules: dict[str, str] = {}
    for item in report["mutations"]:
        if item["status"] not in {"survived", "error"}:
            continue
        rule_id = f"mendmark/{item['operator']}"
        rules[rule_id] = item["description"]
        status = "survived" if item["status"] == "survived" else "could not be evaluated"
        results.append(
            _sarif_result(
                rule_id,
                f"{item['severity']} mutation {status}: {item['mutant_id']}",
                level="error" if item["severity"] == "critical" else "warning",
            )
        )
    for issue in report["tools"]["contract_issues"]:
        rule_id = "mendmark/tool-contract"
        rules[rule_id] = "A tool call does not match its declared contract"
        location = (
            f"case {issue['case_id']}, {issue['trace']} trace, "
            f"call {issue['call_index']}, tool {issue['tool_name']}"
        )
        field = f", field {issue['field']}" if "field" in issue else ""
        results.append(_sarif_result(rule_id, f"{issue['issue']} ({location}{field})"))
    for mutant_id in report["regressions"]["regressed"]:
        rule_id = "mendmark/evaluator-regression"
        rules[rule_id] = "A previously killed mutation now survives or errors"
        results.append(_sarif_result(rule_id, f"Evaluator regression: {mutant_id}"))
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Mendmark",
                        "version": report.get("provenance", {}).get("mendmark_version"),
                        "informationUri": "https://github.com/danielgaskins/mendmark",
                        "rules": [
                            {"id": rule_id, "shortDescription": {"text": description}}
                            for rule_id, description in sorted(rules.items())
                        ],
                    }
                },
                "results": results,
            }
        ],
    }
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(sarif, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
