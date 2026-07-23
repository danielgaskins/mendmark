from __future__ import annotations

import copy
import unittest

from ml_pipeline.split import split_rows


def rows_for_group_sizes(*sizes: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    row_id = 0
    for group_index, size in enumerate(sizes):
        for _ in range(size):
            rows.append(
                {
                    "row_id": row_id,
                    "entity_id": f"entity-{group_index}",
                    "feature": row_id * 0.25,
                }
            )
            row_id += 1
    return rows


class HiddenSplitTests(unittest.TestCase):
    def test_entities_never_cross_the_boundary(self) -> None:
        rows = rows_for_group_sizes(2, 3, 1, 4, 2, 5, 1)
        for seed in range(12):
            train, test = split_rows(rows, test_fraction=0.3, seed=seed)
            train_entities = {row["entity_id"] for row in train}
            test_entities = {row["entity_id"] for row in test}
            self.assertFalse(train_entities & test_entities)

    def test_fraction_is_near_the_best_complete_group_choice(self) -> None:
        rows = rows_for_group_sizes(8, 5, 4, 3, 2, 1)
        target = len(rows) * 0.3
        _, test = split_rows(rows, test_fraction=0.3, seed=5)
        # A complete-group selection can reach 7 rows (4 + 3), just 0.1 from
        # this target. Allow one row of slack without prescribing an algorithm.
        self.assertLessEqual(abs(len(test) - target), 1.1)

    def test_seed_can_change_selected_entities(self) -> None:
        rows = rows_for_group_sizes(2, 2, 2, 2, 2, 2, 2, 2)
        selections = set()
        for seed in range(8):
            _, test = split_rows(rows, test_fraction=0.25, seed=seed)
            selections.add(tuple(sorted({row["entity_id"] for row in test})))
        self.assertGreater(len(selections), 1)

    def test_input_is_not_mutated(self) -> None:
        rows = rows_for_group_sizes(3, 2, 4)
        original = copy.deepcopy(rows)
        split_rows(rows, test_fraction=0.35, seed=9)
        self.assertEqual(rows, original)

    def test_missing_entity_id_fails_clearly(self) -> None:
        rows = rows_for_group_sizes(2, 2)
        rows.append({"row_id": 99, "feature": 1.0})
        with self.assertRaises((KeyError, ValueError)) as caught:
            split_rows(rows, test_fraction=0.25, seed=2)
        self.assertIn("entity_id", str(caught.exception))

    def test_empty_rows_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            split_rows([], test_fraction=0.25, seed=2)


if __name__ == "__main__":
    unittest.main()

