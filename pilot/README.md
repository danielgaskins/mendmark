# Design-partner evidence

This directory defines the privacy-safe evidence needed to distinguish engine
assurance from demonstrated customer utility. `template.json` is a planning
record, not a completed-pilot claim.

For each pilot, copy the template into `pilot/evidence/<anonymous-id>.json` and
record only aggregate counts and coarse organization bands. Never store company
names, prompts, outputs, payloads, arguments, account identifiers, trace
content, or unstructured interview notes in this repository.

Validate and summarize evidence with:

```bash
python scripts/summarize_pilots.py
python scripts/summarize_pilots.py --require-completed 3
```

The utility gate for a credible ICP claim is at least three completed pilots,
including one multi-agent deployment, with:

- Median time to first audit no greater than ten minutes.
- At least 80% of reviewed mutations judged realistic.
- Equivalent-mutation rate below 10%.
- At least one new evaluator blind spot found in two or more pilots.
- At least half of discovered blind spots remediated during the pilot.
- At least two partners retaining Mendmark in CI.

## Promotion into a golden set

Only the abstract failure pattern may be promoted. Recreate it with new neutral
identifiers and minimal data, obtain two independent reviews, demonstrate that
the original evaluator weakness survives in the recreated case, and create a
new immutable golden-set version. Never copy or lightly redact a customer trace.
