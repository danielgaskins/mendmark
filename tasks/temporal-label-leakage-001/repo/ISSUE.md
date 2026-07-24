# Historical evaluation trains on labels from the future

Each event has both `event_at` and `label_available_at` ISO-8601 timestamps. The
current split puts every event occurring on or before the cutoff into training,
even when its label was not known until afterward.

Repair `split_labeled_events` so that:

- Training contains only events whose event and label were both available on or
  before the cutoff.
- Test contains events strictly after the cutoff.
- Pre-cutoff events with post-cutoff labels are excluded from both partitions.
- Aware ISO-8601 timestamps, including `Z`, are accepted and compared correctly.
- Naive timestamps, malformed values, missing fields, and empty input fail clearly.
- Input order is preserved and inputs are not mutated.

