from __future__ import annotations

import copy
import unittest

from ml_pipeline.preprocessing import fit_standardizer, transform


class HiddenPreprocessingTests(unittest.TestCase):
    def test_inference_uses_training_statistics(self) -> None:
        training = [{"x": 8.0}, {"x": 10.0}, {"x": 12.0}]
        stats = fit_standardizer(training, ["x"])
        transformed = transform([{"x": 100.0}], ["x"], stats)
        self.assertAlmostEqual(transformed[0][0], (100.0 - 10.0) / stats["x"]["scale"])

    def test_same_row_is_batch_invariant(self) -> None:
        stats = fit_standardizer([{"x": 0.0}, {"x": 2.0}], ["x"])
        alone = transform([{"x": 5.0}], ["x"], stats)[0]
        grouped = transform([{"x": 5.0}, {"x": -40.0}], ["x"], stats)[0]
        self.assertEqual(alone, grouped)

    def test_constant_feature_uses_unit_scale(self) -> None:
        stats = fit_standardizer([{"x": 3.0}, {"x": 3.0}], ["x"])
        self.assertEqual(stats["x"]["scale"], 1.0)

    def test_inputs_and_stats_are_not_mutated(self) -> None:
        rows = [{"x": 2.0, "y": 4.0}]
        stats = {"x": {"mean": 1.0, "scale": 2.0}, "y": {"mean": 2.0, "scale": 1.0}}
        original_rows, original_stats = copy.deepcopy(rows), copy.deepcopy(stats)
        transform(rows, ["y", "x"], stats)
        self.assertEqual(rows, original_rows)
        self.assertEqual(stats, original_stats)

    def test_duplicate_and_missing_features_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            fit_standardizer([{"x": 1.0}], ["x", "x"])
        with self.assertRaisesRegex((KeyError, ValueError), "missing"):
            fit_standardizer([{"x": 1.0}], ["y"])


if __name__ == "__main__":
    unittest.main()

