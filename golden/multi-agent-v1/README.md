# Mendmark Multi-Agent Golden Set v1

This golden set is the canonical contract for Mendmark's native multi-agent
event graph. Its reviewable corpus is the checked-in
[`multi_agent_suite.json`](../../examples/multi_agent_suite.json), paired with
the deterministic [`multi_agent_evaluator.py`](../../examples/multi_agent_evaluator.py).

## Contents

- One complete parallel workflow with a supervisor and two specialists.
- Three agent contracts and three tool contracts.
- Nine causally linked events across two independent branches.
- Two delegations, three tool calls, two returned results, and one aggregation.
- One side-effecting refund operation.
- 44 pinned mutations from 20 applicable tool, response, and coordination
  operators.

The compact corpus is intentional: every event is required by at least one
operator, making the mutation inventory easy to inspect manually. A separate
100-event assurance test protects deterministic behavior on larger graphs.

## Methodology

The original graph and final outcome must pass. Mendmark then changes exactly
one tool, response, delegation, authorization assignment, result, dependency,
state, aggregation, or loop condition. The complete evaluator compares both the
event graph and final outcome, killing all 44 mutations.

[`manifest.json`](manifest.json) pins the suite bytes, mutation identities,
operator counts, summary, and gate decision. [`results.json`](results.json)
records the reference outcome. Payloads are present in the public corpus for
review but remain absent from generated audit reports.

## Reproduce

From the repository root:

```bash
python benchmarks/benchmark_multi_agent_golden_set.py
```

The command uses only the local CLI and evaluator. It makes no model or network
calls and exits nonzero if the golden contract changes.

The 100% result means the complete reference evaluator detects every generated
fault in this corpus. It is not a general agent-quality or safety score.
