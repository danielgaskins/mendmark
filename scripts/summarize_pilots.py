#!/usr/bin/env python3
"""Validate privacy-safe pilot records and calculate the external-utility gate."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def summarize(root: Path) -> dict[str, object]:
    schema = json.loads((root / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    records = []
    evidence_root = root / "evidence"
    for path in sorted(evidence_root.glob("*.json")) if evidence_root.is_dir() else []:
        record = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
        if errors:
            location = ".".join(str(item) for item in errors[0].path) or "record"
            raise ValueError(f"{path}: {location}: {errors[0].message}")
        if record["status"] == "completed":
            measures = record["measures"]
            if measures["mutations_reviewed"] > measures["mutations_generated"]:
                raise ValueError(f"{path}: reviewed mutations exceed generated mutations")
            if (
                measures["realistic_mutations"] + measures["equivalent_mutations"]
                > measures["mutations_reviewed"]
            ):
                raise ValueError(
                    f"{path}: classified mutations exceed reviewed mutations"
                )
            if measures["remediated_blind_spots"] > measures["new_blind_spots"]:
                raise ValueError(f"{path}: remediated blind spots exceed discoveries")
        records.append(record)
    completed = [record for record in records if record["status"] == "completed"]
    measures = [record["measures"] for record in completed]
    reviewed = sum(item["mutations_reviewed"] for item in measures)
    realistic = sum(item["realistic_mutations"] for item in measures)
    equivalent = sum(item["equivalent_mutations"] for item in measures)
    discovered = sum(item["new_blind_spots"] for item in measures)
    remediated = sum(item["remediated_blind_spots"] for item in measures)
    retained = sum(item["retained_in_ci"] for item in measures)
    criteria = {
        "at_least_three_completed": len(completed) >= 3,
        "includes_multi_agent": any(
            record["organization_profile"]["agent_topology"] in {"multi-agent", "mixed"}
            for record in completed
        ),
        "median_first_audit_at_most_ten_minutes": bool(measures)
        and statistics.median(item["time_to_first_audit_minutes"] for item in measures) <= 10,
        "realistic_rate_at_least_80_percent": reviewed > 0 and realistic / reviewed >= 0.8,
        "equivalent_rate_below_10_percent": reviewed > 0 and equivalent / reviewed < 0.1,
        "blind_spots_found_in_at_least_two_pilots": sum(item["new_blind_spots"] > 0 for item in measures) >= 2,
        "at_least_half_of_blind_spots_remediated": discovered > 0 and remediated / discovered >= 0.5,
        "at_least_two_retained_in_ci": retained >= 2,
        "all_completed_records_approved": bool(completed)
        and all(
            record["review"]["customer_approved_aggregation"]
            and record["review"]["evaluator_owner_reviewed"]
            and record["review"]["independent_reviewer_count"] >= 1
            for record in completed
        ),
    }
    return {
        "schema_version": "1.0",
        "records": len(records),
        "completed": len(completed),
        "aggregate": {
            "mutations_reviewed": reviewed,
            "realistic_mutations": realistic,
            "equivalent_mutations": equivalent,
            "new_blind_spots": discovered,
            "remediated_blind_spots": remediated,
            "retained_in_ci": retained,
        },
        "criteria": criteria,
        "utility_gate_passed": all(criteria.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-root", type=Path, default=Path("pilot"))
    parser.add_argument("--require-completed", type=int, default=0)
    args = parser.parse_args()
    try:
        result = summarize(args.pilot_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"pilot evidence: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["completed"] < args.require_completed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
