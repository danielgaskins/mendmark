from __future__ import annotations

import unittest

from ml_pipeline.temporal import split_labeled_events


class PublicTemporalTests(unittest.TestCase):
    def test_splits_events_around_cutoff(self) -> None:
        events = [
            {"id": 1, "event_at": "2026-01-01T00:00:00Z", "label_available_at": "2026-01-02T00:00:00Z"},
            {"id": 2, "event_at": "2026-02-01T00:00:00Z", "label_available_at": "2026-02-02T00:00:00Z"},
        ]
        train, test = split_labeled_events(events, "2026-01-15T00:00:00Z")
        self.assertEqual([row["id"] for row in train], [1])
        self.assertEqual([row["id"] for row in test], [2])


if __name__ == "__main__":
    unittest.main()

