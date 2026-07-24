from __future__ import annotations

from datetime import datetime
from typing import Any


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def split_labeled_events(
    events: list[dict[str, Any]], cutoff: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split on event time, incorrectly ignoring label availability."""
    boundary = _timestamp(cutoff)
    train = [event for event in events if _timestamp(event["event_at"]) <= boundary]
    test = [event for event in events if _timestamp(event["event_at"]) > boundary]
    return train, test

