from __future__ import annotations

import copy
import random
import unittest

from ml_pipeline.initialization import initialize_centroids


class HiddenInitializationTests(unittest.TestCase):
    def test_input_is_not_mutated_or_aliased(self) -> None:
        points = [[0.0, 1.0], [2.0, 3.0], [4.0, 5.0]]
        original = copy.deepcopy(points)
        selected = initialize_centroids(points, 2, 4)
        self.assertEqual(points, original)
        selected[0][0] = 999.0
        self.assertEqual(points, original)

    def test_global_random_state_is_unchanged(self) -> None:
        random.seed(12345)
        expected_state = random.getstate()
        initialize_centroids([[0.0], [1.0], [2.0]], 2, 9)
        self.assertEqual(random.getstate(), expected_state)

    def test_selected_values_are_distinct(self) -> None:
        points = [[0.0], [0.0], [1.0], [2.0]]
        selected = initialize_centroids(points, 3, 2)
        self.assertEqual(len({tuple(point) for point in selected}), 3)

    def test_invalid_k_is_rejected(self) -> None:
        points = [[0.0], [0.0], [1.0]]
        for k in (0, -1, 3):
            with self.subTest(k=k), self.assertRaises(ValueError):
                initialize_centroids(points, k, 1)

    def test_different_seeds_can_change_selection(self) -> None:
        points = [[float(index)] for index in range(8)]
        observed = {
            tuple(tuple(point) for point in initialize_centroids(points, 3, seed))
            for seed in range(6)
        }
        self.assertGreater(len(observed), 1)


if __name__ == "__main__":
    unittest.main()

