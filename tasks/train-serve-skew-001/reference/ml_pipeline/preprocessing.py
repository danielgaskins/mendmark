from __future__ import annotations

import math
from typing import Any, Sequence


def _validate_features(features: Sequence[str]) -> tuple[str, ...]:
    ordered = tuple(features)
    if not ordered:
        raise ValueError("features must not be empty")
    if any(not isinstance(feature, str) or not feature for feature in ordered):
        raise ValueError("feature names must be non-empty strings")
    if len(set(ordered)) != len(ordered):
        raise ValueError("duplicate feature names are not allowed")
    return ordered


def _value(row: dict[str, Any], feature: str) -> float:
    if feature not in row:
        raise ValueError(f"row is missing feature {feature!r}")
    return float(row[feature])


def fit_standardizer(
    rows: list[dict[str, Any]], features: Sequence[str]
) -> dict[str, dict[str, float]]:
    if not rows:
        raise ValueError("rows must not be empty")
    ordered = _validate_features(features)
    stats: dict[str, dict[str, float]] = {}
    for feature in ordered:
        values = [_value(row, feature) for row in rows]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        stats[feature] = {"mean": mean, "scale": math.sqrt(variance) or 1.0}
    return stats


def transform(
    rows: list[dict[str, Any]],
    features: Sequence[str],
    stats: dict[str, dict[str, float]],
) -> list[list[float]]:
    ordered = _validate_features(features)
    output: list[list[float]] = []
    for row in rows:
        transformed: list[float] = []
        for feature in ordered:
            if feature not in stats:
                raise ValueError(f"statistics are missing feature {feature!r}")
            mean = float(stats[feature]["mean"])
            scale = float(stats[feature]["scale"])
            if scale <= 0:
                raise ValueError(f"scale for {feature!r} must be positive")
            transformed.append((_value(row, feature) - mean) / scale)
        output.append(transformed)
    return output

