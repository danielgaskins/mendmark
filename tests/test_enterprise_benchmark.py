from __future__ import annotations

import importlib.util
from pathlib import Path

from mendmark.agent_cases import ToolSpec


PROJECT_ROOT = Path(__file__).parents[1]


def benchmark_module():
    path = PROJECT_ROOT / "benchmarks" / "benchmark_enterprise.py"
    spec = importlib.util.spec_from_file_location("benchmark_enterprise", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scale_harness_covers_reports_and_incremental_single_and_multi_audits() -> None:
    benchmark = benchmark_module()
    tools = (ToolSpec("lookup"), ToolSpec("write", side_effecting=True))

    single = benchmark.measure(benchmark.single_cases(10), tools)
    multi = benchmark.measure(benchmark.multi_cases(5), tools)

    for result in (single, multi):
        assert result["kill_rate"] == 1.0
        assert result["mutations"] > result["cases"]
        assert 0 < result["incremental_mutations"] <= result["mutations"]
        assert result["report_bytes"] > 0
        assert result["junit_bytes"] > 0
        assert result["sarif_bytes"] > 0
