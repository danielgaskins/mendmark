from __future__ import annotations

import random


def initialize_centroids(
    points: list[list[float]], k: int, seed: int
) -> list[list[float]]:
    unique = list(dict.fromkeys(tuple(float(value) for value in point) for point in points))
    if k <= 0:
        raise ValueError("k must be positive")
    if k > len(unique):
        raise ValueError("k cannot exceed the number of distinct points")
    selected = random.Random(seed).sample(unique, k)
    return [list(point) for point in selected]

