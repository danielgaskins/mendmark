from __future__ import annotations

import unittest

from evaluation.summary import macro_task_success


class PublicSummaryTests(unittest.TestCase):
    def test_equal_trial_counts(self) -> None:
        records = [
            {"model": "model-a", "task_id": "one", "trial": 0, "passed": True},
            {"model": "model-a", "task_id": "one", "trial": 1, "passed": False},
            {"model": "model-a", "task_id": "two", "trial": 0, "passed": False},
            {"model": "model-a", "task_id": "two", "trial": 1, "passed": True},
        ]
        self.assertEqual(macro_task_success(records), {"model-a": 0.5})

    def test_multiple_models_are_sorted(self) -> None:
        records = [
            {"model": "zeta", "task_id": "one", "trial": 0, "passed": True},
            {"model": "alpha", "task_id": "one", "trial": 0, "passed": False},
        ]
        self.assertEqual(list(macro_task_success(records)), ["alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()

