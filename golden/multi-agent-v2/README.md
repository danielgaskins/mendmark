# Mendmark Multi-Agent Golden Set v2

This is the broad, fully pinned multi-agent benchmark for Mendmark. Version 1
remains unchanged as a compact historical regression contract.

## Contents

- Six passing workflows, 17 agent declarations, five tools, and 41 events.
- Parallel fan-out/fan-in, nested delegation, retry after timeout, parallel
  shared state, identical tools under different agent authorities, and ordered
  side effects.
- 294 applicable mutations from 30 operators, including omitted, unexpected,
  wrong-type, and swapped tool arguments; duplicated delegation and results;
  premature aggregation; stale state; abandoned branches; and incorrect result
  correlation.
- Strong, output-only, and scheduler-permuted strong profiles.

The strong profile detects 294/294 faults. The output-only contrast detects
23/294 and leaves 181 critical failures undetected. Reversing every event array
still yields 294/294 because causal dependencies, not scheduler order, define
the graph.

## Integrity and methodology

[`manifest.json`](manifest.json) pins every evaluator input, the public report
schema, all mutation identities and applicability counts, outcome summaries,
and canonical digests of per-operator and per-category coverage. The benchmark
also verifies that [`results.json`](results.json) exactly matches the measured
contract.

The strong evaluator uses the pristine, hashed [`suite.json`](suite.json) as its
oracle. It normalizes absent/null optional fields, dependency ordering, and
event-array ordering while preserving event content. It makes no model or
network calls.

## Reproduce

```bash
python benchmarks/benchmark_multi_agent_golden_set_v2.py
```

The 100% strong-profile score means Mendmark detects every generated fault in
this public corpus. It is not a general agent-quality score; real design-partner
evidence is tracked separately and may promote independently reviewed,
anonymized failure patterns into a future golden-set version.
