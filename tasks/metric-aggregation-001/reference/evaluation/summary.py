from __future__ import annotations

from collections import defaultdict
from typing import Any


def macro_task_success(records: list[dict[str, Any]]) -> dict[str, float]:
    if not records:
        raise ValueError("records must not be empty")
    task_counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    observed: set[tuple[str, str, int]] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(f"record {index} must be a dictionary")
        model = record.get("model")
        task_id = record.get("task_id")
        trial = record.get("trial")
        passed = record.get("passed")
        if not isinstance(model, str) or not model:
            raise ValueError("model must be a non-empty string")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("task_id must be a non-empty string")
        if isinstance(trial, bool) or not isinstance(trial, int):
            raise TypeError("trial must be an integer")
        if not isinstance(passed, bool):
            raise TypeError("passed must be a boolean")
        identifier = (model, task_id, trial)
        if identifier in observed:
            raise ValueError(f"duplicate trial: {identifier!r}")
        observed.add(identifier)
        counts = task_counts[(model, task_id)]
        counts[0] += int(passed)
        counts[1] += 1

    model_rates: dict[str, list[float]] = defaultdict(list)
    for (model, _), (passed_count, trial_count) in task_counts.items():
        model_rates[model].append(passed_count / trial_count)
    return {
        model: sum(rates) / len(rates)
        for model, rates in sorted(model_rates.items())
    }

