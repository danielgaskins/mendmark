from __future__ import annotations

import random


def initialize_centroids(
    points: list[list[float]], k: int, seed: int
) -> list[list[float]]:
    """Choose initial centroids, currently mutating data and global RNG state."""
    random.seed(seed)
    random.shuffle(points)
    return points[:k]

