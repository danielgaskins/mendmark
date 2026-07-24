from __future__ import annotations

import unittest

from ml_pipeline.initialization import initialize_centroids


class PublicInitializationTests(unittest.TestCase):
    def test_returns_requested_number(self) -> None:
        points = [[0.0], [1.0], [2.0], [3.0]]
        self.assertEqual(len(initialize_centroids(points, 2, 7)), 2)

    def test_same_seed_repeats_selection(self) -> None:
        points = [[0.0], [1.0], [2.0], [3.0]]
        first = initialize_centroids([row[:] for row in points], 2, 11)
        second = initialize_centroids([row[:] for row in points], 2, 11)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

