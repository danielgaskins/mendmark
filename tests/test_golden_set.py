from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = PROJECT_ROOT / "golden" / "agent-eval-v1"


def _benchmark_module():
    path = PROJECT_ROOT / "benchmarks" / "benchmark_golden_set.py"
    spec = importlib.util.spec_from_file_location("benchmark_golden_set", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_eval_golden_set_matches_pinned_contract() -> None:
    result = _benchmark_module().run_golden_set(GOLDEN_ROOT)

    assert result["contract_passed"] is True
    assert result["dataset"] == "Mendmark Agent Eval Golden Set"
    assert result["cases"] == 24
    assert result["tools"] == 13
    assert result["mutations"] == 263
    assert result["profiles"]["complete"]["summary"]["kill_rate"] == 1.0
    assert result["profiles"]["response-only"]["summary"]["survived"] == 176
    assert result["profiles"]["trace-only"]["summary"]["survived"] == 48


def test_published_golden_results_match_manifest_contract() -> None:
    manifest = json.loads((GOLDEN_ROOT / "manifest.json").read_text(encoding="utf-8"))
    results = json.loads((GOLDEN_ROOT / "results.json").read_text(encoding="utf-8"))

    assert results["dataset"] == manifest["name"]
    assert results["dataset_version"] == manifest["version"]
    assert results["contract_passed"] is True
    for profile, expected in manifest["profiles"].items():
        assert results["profiles"][profile]["summary"] == expected["expected_summary"]
        assert (
            results["profiles"][profile]["operator_statuses"]
            == expected["operator_statuses"]
        )
