from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]


def benchmark_module():
    path = PROJECT_ROOT / "benchmarks" / "benchmark_multi_agent_golden_set_v2.py"
    spec = importlib.util.spec_from_file_location("multi_agent_golden_v2", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_multi_agent_golden_v2_matches_every_pinned_contract() -> None:
    assert benchmark_module().main() == 0
