from __future__ import annotations

import importlib.util
from pathlib import Path


def test_enterprise_outcome_golden_set_matches_pinned_contract() -> None:
    path = Path(__file__).parents[1] / "benchmarks" / "benchmark_outcome_golden_set.py"
    spec = importlib.util.spec_from_file_location("outcome_golden", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 0
