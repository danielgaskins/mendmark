from __future__ import annotations

import random
from typing import Any


def split_rows(
    rows: list[dict[str, Any]],
    test_fraction: float = 0.25,
    seed: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split observations into train and test partitions.

    The implementation is deterministic, but it incorrectly treats observations
    as independent even when several rows belong to the same entity.
    """
    if not 0.0 < test_fraction < 1.0:
        raise ValueError("test_fraction must be between zero and one")
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    test_size = max(1, round(len(shuffled) * test_fraction))
    return shuffled[test_size:], shuffled[:test_size]

