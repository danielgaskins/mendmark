from __future__ import annotations

import unittest

from ml_pipeline.split import split_rows


ROWS = [
    {"row_id": index, "entity_id": f"customer-{index // 2}", "value": index / 10}
    for index in range(20)
]


class PublicSplitTests(unittest.TestCase):
    def test_partitions_every_row_once(self) -> None:
        train, test = split_rows(ROWS, test_fraction=0.3, seed=7)
        observed = [row["row_id"] for row in train + test]
        self.assertEqual(sorted(observed), list(range(20)))
        self.assertEqual(len(observed), len(set(observed)))

    def test_is_deterministic(self) -> None:
        first = split_rows(ROWS, test_fraction=0.3, seed=17)
        second = split_rows(ROWS, test_fraction=0.3, seed=17)
        self.assertEqual(first, second)

    def test_rejects_invalid_fraction(self) -> None:
        with self.assertRaises(ValueError):
            split_rows(ROWS, test_fraction=0.0)


if __name__ == "__main__":
    unittest.main()

