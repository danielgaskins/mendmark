from __future__ import annotations

from datetime import datetime
from typing import Any


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def split_labeled_events(
    events: list[dict[str, Any]], cutoff: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not events:
        raise ValueError("events must not be empty")
    boundary = _timestamp(cutoff, "cutoff")
    train: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    for event in events:
        if "event_at" not in event:
            raise ValueError("event is missing event_at")
        if "label_available_at" not in event:
            raise ValueError("event is missing label_available_at")
        event_at = _timestamp(event["event_at"], "event_at")
        label_at = _timestamp(event["label_available_at"], "label_available_at")
        if event_at <= boundary and label_at <= boundary:
            train.append(event)
        elif event_at > boundary:
            test.append(event)
    return train, test

