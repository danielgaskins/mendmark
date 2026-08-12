#!/usr/bin/env python3
"""Verify the Enterprise Outcome Golden Set contract offline."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mendmark.enterprise_demo import run_enterprise_demo  # noqa: E402


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = PROJECT_ROOT / "golden" / "outcome-v1"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    expected = json.loads((root / "results.json").read_text(encoding="utf-8"))["profiles"]
    if _digest(root / "suite.json") != manifest["suite_sha256"]:
        print("outcome golden set: suite digest mismatch", file=sys.stderr)
        return 1
    asset_paths = {
        "README.md": root / "README.md",
        "results.json": root / "results.json",
        "suite-v1.schema.json": PROJECT_ROOT
        / "src"
        / "mendmark"
        / "schemas"
        / "suite-v1.schema.json",
        "report-v1.schema.json": PROJECT_ROOT
        / "src"
        / "mendmark"
        / "schemas"
        / "report-v1.schema.json",
    }
    for name, expected_digest in manifest["assets"].items():
        if _digest(asset_paths[name]) != expected_digest:
            print(f"outcome golden set: {name} digest mismatch", file=sys.stderr)
            return 1
    with tempfile.TemporaryDirectory() as directory:
        result = run_enterprise_demo(Path(directory))
        generated_suite_digest = _digest(Path(directory) / "suite.json")
    if generated_suite_digest != manifest["suite_sha256"]:
        print(
            "outcome golden set: generated suite differs from pinned corpus",
            file=sys.stderr,
        )
        return 1
    observed = {}
    for source, target in (("state_only", "state-only"), ("protected", "outcome-contract")):
        report = result[source]
        observed[target] = {
            "status": report["business_assurance"]["status"],
            **{key: report["summary"][key] for key in ("cases", "mutants", "killed", "survived", "kill_rate")},
            "affected_workflows": report["business_assurance"]["affected_workflows"],
            "estimated_exposure_usd": report["business_assurance"]["estimated_exposure_usd"],
            "critical_survivors": report["summary"]["critical_survivors"],
        }
    if observed != expected:
        print(f"outcome golden set: expected {expected!r}, got {observed!r}", file=sys.stderr)
        return 1
    protected = result["protected"]
    operator_counts = {
        name: coverage["mutants"]
        for name, coverage in protected["coverage"]["by_operator"].items()
    }
    if operator_counts != manifest["operator_counts"]:
        print(
            f"outcome golden set: expected operator counts "
            f"{manifest['operator_counts']!r}, got {operator_counts!r}",
            file=sys.stderr,
        )
        return 1
    print("outcome golden set: PASS (state-only 32/64; outcome-contract 64/64)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
