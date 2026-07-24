from __future__ import annotations

import math
from typing import Any, Sequence


def fit_standardizer(
    rows: list[dict[str, Any]], features: Sequence[str]
) -> dict[str, dict[str, float]]:
    if not rows:
        raise ValueError("rows must not be empty")
    stats: dict[str, dict[str, float]] = {}
    for feature in features:
        values = [float(row[feature]) for row in rows]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        stats[feature] = {"mean": mean, "scale": math.sqrt(variance) or 1.0}
    return stats


def transform(
    rows: list[dict[str, Any]],
    features: Sequence[str],
    stats: dict[str, dict[str, float]],
) -> list[list[float]]:
    """Standardize rows, incorrectly refitting on the inference batch."""
    online_stats = fit_standardizer(rows, features)
    return [
        [
            (float(row[feature]) - online_stats[feature]["mean"])
            / online_stats[feature]["scale"]
            for feature in features
        ]
        for row in rows
    ]

