from __future__ import annotations

import unittest

from ml_pipeline.preprocessing import fit_standardizer, transform


class PublicPreprocessingTests(unittest.TestCase):
    def test_fit_computes_population_statistics(self) -> None:
        rows = [{"x": 1.0}, {"x": 3.0}]
        self.assertEqual(fit_standardizer(rows, ["x"]), {"x": {"mean": 2.0, "scale": 1.0}})

    def test_training_batch_is_centered(self) -> None:
        rows = [{"x": 1.0}, {"x": 3.0}]
        stats = fit_standardizer(rows, ["x"])
        self.assertEqual(transform(rows, ["x"], stats), [[-1.0], [1.0]])


if __name__ == "__main__":
    unittest.main()

