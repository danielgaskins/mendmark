from __future__ import annotations

import unittest

from evaluation.summary import macro_task_success


class HiddenSummaryTests(unittest.TestCase):
    def test_tasks_receive_equal_weight(self) -> None:
        records = [
            *(
                {"model": "a", "task_id": "frequent", "trial": trial, "passed": trial < 9}
                for trial in range(10)
            ),
            {"model": "a", "task_id": "rare", "trial": 0, "passed": False},
        ]
        self.assertAlmostEqual(macro_task_success(records)["a"], 0.45)

    def test_duplicate_trial_is_rejected(self) -> None:
        record = {"model": "a", "task_id": "one", "trial": 0, "passed": True}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            macro_task_success([record, dict(record)])

    def test_empty_records_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            macro_task_success([])

    def test_malformed_fields_are_rejected(self) -> None:
        valid = {"model": "a", "task_id": "one", "trial": 0, "passed": True}
        for key, bad_value in (
            ("model", ""),
            ("task_id", None),
            ("trial", True),
            ("passed", 1),
        ):
            record = dict(valid)
            record[key] = bad_value
            with self.subTest(key=key), self.assertRaises((TypeError, ValueError)):
                macro_task_success([record])


if __name__ == "__main__":
    unittest.main()

