from __future__ import annotations

import copy
import unittest

from ml_pipeline.temporal import split_labeled_events


class HiddenTemporalTests(unittest.TestCase):
    def test_delayed_label_is_not_training_data(self) -> None:
        events = [
            {"id": "known", "event_at": "2026-01-01T00:00:00Z", "label_available_at": "2026-01-02T00:00:00Z"},
            {"id": "leaked", "event_at": "2026-01-03T00:00:00Z", "label_available_at": "2026-02-01T00:00:00Z"},
            {"id": "future", "event_at": "2026-01-20T00:00:00Z", "label_available_at": "2026-01-21T00:00:00Z"},
        ]
        train, test = split_labeled_events(events, "2026-01-10T00:00:00Z")
        self.assertEqual([row["id"] for row in train], ["known"])
        self.assertEqual([row["id"] for row in test], ["future"])

    def test_offsets_are_compared_by_instant(self) -> None:
        events = [
            {"id": 1, "event_at": "2026-01-01T09:00:00+09:00", "label_available_at": "2026-01-01T01:00:00+00:00"}
        ]
        train, test = split_labeled_events(events, "2026-01-01T02:00:00Z")
        self.assertEqual([row["id"] for row in train], [1])
        self.assertEqual(test, [])

    def test_input_order_and_values_are_preserved(self) -> None:
        events = [
            {"id": 2, "event_at": "2026-03-02T00:00:00Z", "label_available_at": "2026-03-03T00:00:00Z"},
            {"id": 1, "event_at": "2026-01-01T00:00:00Z", "label_available_at": "2026-01-02T00:00:00Z"},
        ]
        original = copy.deepcopy(events)
        split_labeled_events(events, "2026-02-01T00:00:00Z")
        self.assertEqual(events, original)

    def test_invalid_inputs_fail_clearly(self) -> None:
        with self.assertRaises(ValueError):
            split_labeled_events([], "2026-01-01T00:00:00Z")
        naive = [{"event_at": "2026-01-01T00:00:00", "label_available_at": "2026-01-01T00:00:00"}]
        with self.assertRaisesRegex(ValueError, "timezone"):
            split_labeled_events(naive, "2026-01-02T00:00:00Z")
        with self.assertRaisesRegex((KeyError, ValueError), "label_available_at"):
            split_labeled_events([{"event_at": "2026-01-01T00:00:00Z"}], "2026-01-02T00:00:00Z")


if __name__ == "__main__":
    unittest.main()

