from __future__ import annotations

import random
from typing import Any


def split_rows(
    rows: list[dict[str, Any]],
    test_fraction: float = 0.25,
    seed: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0.0 < test_fraction < 1.0:
        raise ValueError("test_fraction must be between zero and one")
    if not rows:
        raise ValueError("rows must not be empty")

    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        if "entity_id" not in row:
            raise ValueError("every row must contain entity_id")
        groups.setdefault(row["entity_id"], []).append(row)
    if len(groups) < 2:
        raise ValueError("at least two distinct entity_id values are required")

    ordered_groups = list(groups.values())
    random.Random(seed).shuffle(ordered_groups)
    target = len(rows) * test_fraction

    # Exact subset-sum dynamic programming chooses the closest attainable row
    # count. Iteration order, randomized above, provides deterministic tie breaks.
    choices: dict[int, tuple[int, ...]] = {0: ()}
    for index, group in enumerate(ordered_groups):
        additions = {
            total + len(group): selected + (index,)
            for total, selected in list(choices.items())
            if total + len(group) < len(rows)
        }
        for total, selected in additions.items():
            choices.setdefault(total, selected)

    valid_choices = {
        total: selected
        for total, selected in choices.items()
        if 0 < total < len(rows)
    }
    selected_indices = set(
        min(
            valid_choices.items(),
            key=lambda item: (abs(item[0] - target), item[0]),
        )[1]
    )
    test = [
        row
        for index, group in enumerate(ordered_groups)
        if index in selected_indices
        for row in group
    ]
    train = [
        row
        for index, group in enumerate(ordered_groups)
        if index not in selected_indices
        for row in group
    ]
    return train, test
