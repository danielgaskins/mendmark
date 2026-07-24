from __future__ import annotations

from typing import Any


def macro_task_success(records: list[dict[str, Any]]) -> dict[str, float]:
    """Return success by model.

    This implementation pools trials, allowing frequently retried tasks to
    dominate a model's score.
    """
    totals: dict[str, list[int]] = {}
    for record in records:
        model = record["model"]
        counts = totals.setdefault(model, [0, 0])
        counts[0] += int(record["passed"])
        counts[1] += 1
    return {model: passed / count for model, (passed, count) in sorted(totals.items())}

