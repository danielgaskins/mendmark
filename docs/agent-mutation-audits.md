# Agent mutation audits

## The problem

An eval score only matters if the eval notices the failures a team cares about.
A tool-calling agent can pass a polished test suite while that suite ignores a
wrong argument, repeated payment, missing lookup, stale tool schema, or success
claim after an API error.

Mendmark checks for those blind spots by planting one controlled fault at a time.
This is the same basic idea as mutation testing in ordinary software. A mutation
is killed when at least one evaluator changes from pass to fail. It survives when
the eval suite still approves the damaged case.

## Audit flow

```text
load passing cases and declared tools
  -> run the original eval suite
  -> generate one-fault mutants
  -> run the same evals on each mutant
  -> attribute each kill to a metric
  -> calculate tool coverage and kill rate
  -> compare with the accepted baseline
  -> apply the release policy
```

The original case must pass. If it does not, Mendmark reports a baseline issue
and fails the gate. An evaluator error does not count as a successful detection.

## Built-in faults

| Operator | Fault | Default severity |
| --- | --- | --- |
| `tool.removed` | Removes one tool call | Critical |
| `tool.arguments_changed` | Changes one argument | Critical |
| `tool.argument_omitted` | Omits one observed argument | Critical |
| `tool.argument_unexpected` | Adds an unexpected argument | High |
| `tool.argument_type_changed` | Changes an argument to an incompatible type | Critical |
| `tool.identifier_swapped` | Uses an identifier from another call | Critical |
| `tool.output_corrupted` | Replaces a tool result with an error | Critical |
| `tool.side_effect_duplicated` | Repeats a side-effecting call | Critical |
| `tool.order_reversed` | Reverses a multi-tool trace | High |
| `tool.unknown_added` | Adds a tool absent from the registry | Critical |
| `recovery.false_success` | Reports success after one tool fails | Critical |
| `response.omitted` | Removes the final response | High |
| `response.replaced` | Replaces the response with a generic claim | High |
| `delegation.removed` | Removes a required delegation | Critical |
| `delegation.recipient_changed` | Routes work to another agent | Critical |
| `delegation.context_omitted` | Removes handoff context | High |
| `delegation.context_corrupted` | Changes one handoff value | Critical |
| `agent.authorization_violated` | Moves a tool call to an unauthorized agent | Critical |
| `coordination.result_dropped` | Removes a specialist result | Critical |
| `coordination.result_misattributed` | Sends a result to the wrong agent | High |
| `coordination.dependency_removed` | Removes a causal dependency | High |
| `coordination.state_update_dropped` | Removes a shared-state update | Critical |
| `coordination.state_update_corrupted` | Changes a shared-state value | Critical |
| `coordination.aggregation_dropped` | Removes a multi-branch aggregation | Critical |
| `coordination.loop_inserted` | Inserts a delegation loop | Critical |
| `coordination.delegation_duplicated` | Issues a delegation twice | High |
| `coordination.result_duplicated` | Delivers a result twice | High |
| `coordination.aggregation_premature` | Aggregates before prerequisites | Critical |
| `coordination.state_revision_stale` | Applies a stale revision | Critical |
| `coordination.branch_abandoned` | Abandons a delegated branch | Critical |
| `coordination.result_request_changed` | Correlates a result to the wrong request | Critical |

Each applicable operator creates a separate mutant for each tool call. That
makes the report useful for a rollout. A team can see that its evals catch a bad
argument to `lookup_order` but miss the same fault in `refund_order`.

## Gate policy

The default policy fails when:

- Mutation kill rate is below 80 percent.
- Any critical mutation survives.
- A declared tool or agent has no case coverage.
- A case uses an undeclared tool or violates a basic tool input contract.
- An original case fails its own eval suite.
- A mutation that the accepted baseline killed now survives or errors.

Suites can set stricter values with `MENDMARK_POLICY`. Command-line flags can
relax a rule for an exploratory local run. A failed audit cannot overwrite the
baseline.

Audits can also emit JUnit and SARIF metadata for pull-request systems. A
changed-tool-only run evaluates cases associated with added or changed tool
digests; a scheduled full run remains the authoritative suite-wide audit.

## Baselines and tool changes

The baseline contains only tool schema digests and mutation statuses. It lets
Mendmark identify:

- New, removed, and changed tools.
- New and removed mutations.
- Regressions from killed to survived or errored.
- Improvements from survived to killed.

A tool is counted as tested when it appears in either the actual or expected
tool trace of at least one case. Mutation coverage then shows how many planted
faults for that tool were killed, survived, or errored.

## Reading the kill rate

A 90 percent kill rate means the suite detected 90 percent of evaluated faults
that Mendmark inserted. It does not mean the agent is 90 percent correct. It also
does not cover faults Mendmark did not generate.

Use the rate as a quality signal for the eval suite. Use critical survivors as
concrete work items. Add domain-specific mutation operators when a product has
important failures that the built-ins do not represent.

Custom operators are loaded as trusted local code and validated for stable,
unique names and mutation IDs. See [custom mutation plugins](custom-mutations.md).

Native multi-agent cases use a causal event graph so independent parallel work
does not need an arbitrary total order. See [multi-agent mutation audits](multi-agent.md).

## Data boundary

The local suite contains prompts and traces, so it should remain inside the
team's trusted environment. The generated report excludes case content, tool
arguments, and tool outputs. A future hosted control plane can receive that
report without receiving production conversations.
