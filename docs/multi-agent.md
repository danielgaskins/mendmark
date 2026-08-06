# Multi-agent mutation audits

Mendmark represents a multi-agent run as a directed acyclic event graph. The
same audit engine handles ordinary single-agent tool traces and multi-agent
executions; teams do not need separate policies, baselines, or CI commands.

## Why an event graph

A flat transcript cannot reliably express parallel work. Wall-clock order is
also a poor correctness rule because two independent specialists may complete
in either order. Each event therefore has a stable ID and names only the events
that must precede it through `depends_on`.

This distinguishes a real causality failure from harmless scheduler variation.
Mendmark never requires unrelated parallel branches to have a fixed order.

## Execution model

A `2.0` case declares:

- `agents`: stable IDs, roles, and explicit tool allow-lists.
- `root_agent_id`: the agent responsible for the final outcome.
- `events`: the observed execution graph.
- `expected_events`: the graph accepted by the evaluator.
- The same input, expected output, tags, and metadata used by single-agent cases.

Supported event kinds are:

| Kind | Purpose |
| --- | --- |
| `delegation` | Assign work to another agent |
| `message` | Communicate or aggregate without invoking a tool |
| `tool_call` | Record a tool invocation owned by one agent |
| `agent_result` | Return specialist work to another agent |
| `state_update` | Record a shared-state transition |

Tool calls remain governed by the global tool registry. Each agent then narrows
that registry with `allowed_tools`. An empty allow-list means the agent cannot
invoke tools; it does not mean unrestricted access.

## Run the complete offline example

```bash
mendmark audit-json examples/multi_agent_suite.json \
  --evaluator-command "python3 examples/multi_agent_evaluator.py" \
  --output /tmp/mendmark-multi-agent-report.json
```

The example runs a supervisor, billing specialist, and risk specialist across
two parallel branches. It includes three tool calls, one side effect, two
delegations, two returned results, one shared-state update, and a causally
dependent aggregation. The complete evaluator kills all 44 applicable tool and
coordination mutations.

## Built-in coordination faults

| Operator | Fault | Severity |
| --- | --- | --- |
| `delegation.removed` | Removes a required delegation | Critical |
| `delegation.recipient_changed` | Routes work to another agent | Critical |
| `delegation.context_omitted` | Removes handoff context | High |
| `delegation.context_corrupted` | Changes one handoff value | Critical |
| `agent.authorization_violated` | Attributes a tool call to an unauthorized agent | Critical |
| `coordination.result_dropped` | Removes a specialist result | Critical |
| `coordination.result_misattributed` | Delivers a result to the wrong agent | High |
| `coordination.dependency_removed` | Removes one causal dependency | High |
| `coordination.state_update_dropped` | Removes a shared-state update | Critical |
| `coordination.state_update_corrupted` | Changes a shared-state value | Critical |
| `coordination.aggregation_dropped` | Removes a multi-branch aggregation | Critical |
| `coordination.loop_inserted` | Inserts a reverse delegation loop | Critical |

All applicable tool and response operators also run against multi-agent cases.
Tool mutations preserve the owning agent and event identity. Removing an event
rewires its downstream dependencies to the removed event's prerequisites, so a
tool-removal mutation does not accidentally introduce an unrelated dangling
reference.

## Evaluation design

A useful multi-agent evaluator normally separates these concerns into metrics:

1. Final outcome correctness.
2. Delegation and recipient correctness.
3. Per-agent tool authorization.
4. Handoff context and returned-result completeness.
5. Causal dependencies and side-effect uniqueness.
6. Aggregation, termination, and loop behavior.

Mendmark compares each metric with its result on the original passing case. A
mutation is killed only when a metric changes from pass to fail. Evaluator
errors remain infrastructure failures and never count as detections.

The report adds privacy-safe per-agent coverage, event counts, and contract
issues. It does not include event payloads, messages, prompts, tool arguments,
tool outputs, or final answers.

Accepted baselines also pin a digest of each agent's role, description, and
tool allow-list. A changed agent contract is visible in the next full report;
inconsistent declarations for the same agent ID fail the release gate.

## Validation and scale

Before evaluation, Mendmark rejects unknown agents, unknown dependencies,
duplicate IDs, self-delegation, invalid event/tool combinations, and dependency
cycles. The release gate also detects agents with no event coverage, tools
outside an agent's allow-list, and allow-lists that reference undeclared tools.

The evaluator command still receives the complete original and mutated batch in
one local process by default. Use `--evaluator-batch-size` to bound process and
request size for large suites, and `--maximum-mutants` to enforce an evaluation
budget before the evaluator starts. Use changed-tool-only audits for pull requests and retain
a scheduled full audit for routing, prompts, agent policy, and coordination
changes that do not alter tool schemas.

Mutation IDs are derived from case, operator, event, agent, and tool identities,
not event payloads or runtime timestamps. They remain deterministic across
runs, including large parallel graphs.

## Python and framework adapters

Python suites may return `AgentCase` objects containing `AgentSpec` and
`AgentEvent` values. The DeepEval adapter flattens event-owned tool calls into
DeepEval's tool list and places the complete graph in
`metadata["mendmark_multi_agent"]`, allowing custom metrics to evaluate both
representations.

The JSON `2.0` protocol is preferred when a framework already exposes native
multi-agent traces. It preserves the graph without requiring a Python import or
a framework-specific Mendmark dependency.

The core types are available directly from the package:

```python
from mendmark import AgentCase, AgentEvent, AgentSpec, ToolCallRecord, ToolSpec
```
