# Mendmark

**Mutation testing for agent evals.**

Your agent tests may all pass and still miss a broken tool call. Mendmark checks
the tests themselves. It makes controlled changes to passing agent traces, runs
your existing evaluators again, and reports which failures they caught.

```text
passing agent case
    -> remove a required tool call
    -> change a tool argument
    -> corrupt a tool result
    -> repeat a side effect
    -> reorder the trace
    -> add an undeclared tool
    -> hide a tool failure behind a success message
    -> damage the final response
    -> run the same evals again
    -> fail CI when a serious fault survives
```

The result is a mutation kill rate. A killed mutation is a planted fault that
your evals detected. A surviving mutation is a specific blind spot you can fix.

## Two-minute demonstration

[Watch the silent weak-eval demonstration](docs/assets/mendmark-weak-eval-demo.mp4).

A refund-agent test passes because it checks only the final sentence. Mendmark
changes the tool trace and finds that 9 of 13 faults escape, including a wrong
refund amount and a duplicated refund. The complete evaluator checks the calls,
arguments, results, and final response. It catches all 13 faults.

The current cut is silent. A voice-over is still to be recorded and added.

## What teams get

- A direct test of whether agent evals catch realistic failures.
- Per-tool mutation coverage for every declared tool.
- A warning when a new or changed tool has no eval coverage.
- Regression detection when an eval stops catching a fault it caught before.
- A JSON report that does not store prompts, tool arguments, or tool outputs.
- CI release gates for kill rate, critical survivors, untested tools, and
  regressions.
- A DeepEval adapter today, with a framework-neutral mutation engine underneath.
- A tested Rubric example through the framework-neutral JSON protocol.
- A validated JSON adapter for any local evaluator command.
- JUnit and SARIF output plus changed-tool-only pull-request audits.
- A stable plugin API for domain-specific mutation operators.
- Source, suite, CI, and policy provenance with packaged report schemas.
- Sigstore Cosign signing and exact-identity verification for audit artifacts.

## Quick start

Mendmark requires Python 3.10 or newer.

```bash
pip install 'mendmark-evals[deepeval]'
```

To run the repository's deterministic example from a source checkout:

```bash
git clone https://github.com/danielgaskins/mendmark.git
cd mendmark

mendmark audit examples/order_agent_suite.py \
  --output mendmark-report.json \
  --write-baseline
```

The included refund-agent example produces 13 controlled faults. Its evals must
catch every one before the gate passes.

```text
Mendmark agent-eval audit
Cases: 1
Mutations: 13  Killed: 13  Survived: 0  Errors: 0
Mutation kill rate: 100.0%
New tools: lookup_order, refund_order
Gate: PASS
```

Run the same command in CI without `--write-baseline`. Mendmark compares the
current tool schemas and mutation results with the last accepted baseline.

## See an eval fail the test

The repository also includes a deliberately weak evaluator. It checks whether
the final sentence is correct and ignores the tool trace.

```bash
mendmark audit examples/order_agent_weak_suite.py \
  --output /tmp/mendmark-weak-report.json
```

The original refund case passes. Mendmark then changes the refund amount,
removes required calls, and duplicates the side effect. Many of those faults
survive because the final sentence never changed. The command exits with a
failed gate and names each blind spot.

Run the complete `order_agent_suite.py` next. Its tool-trace evaluator checks
the ordered calls, arguments, and results, so the same planted faults are
caught. This before-and-after pair is the shortest demonstration of what
Mendmark measures.

## Define a suite

A suite is a trusted local Python file. It exports three things:

```python
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase, ToolCall

TOOLS = [
    {
        "name": "refund_order",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["order_id", "amount"],
        },
        "side_effecting": True,
    }
]

MENDMARK_POLICY = {
    "minimum_kill_rate": 0.9,
    "fail_on_critical_survivor": True,
    "fail_on_untested_tools": True,
    "fail_on_tool_contract_issues": True,
    "fail_on_regression": True,
}


def get_metrics():
    # Return your DeepEval metrics here. The complete example includes a
    # deterministic tool-trace metric that runs without an API key.
    return [MyToolMetric()]


def get_cases():
    refund = ToolCall(
        name="refund_order",
        input_parameters={"order_id": "104", "amount": 29.99},
        output={"status": "accepted"},
    )
    return [
        LLMTestCase(
            name="refund-order",
            input="Refund order 104 in full.",
            actual_output="The refund was accepted.",
            expected_output="The refund was accepted.",
            tools_called=[refund],
            expected_tools=[refund],
        )
    ]
```

`get_metrics()` must return fresh metric instances on every call. Metric names
must be unique. Mendmark reruns those metrics against the original case and each
mutated copy.

See [the complete example](https://github.com/danielgaskins/mendmark/blob/main/examples/order_agent_suite.py)
and the [mutation audit guide](https://github.com/danielgaskins/mendmark/blob/main/docs/agent-mutation-audits.md).

## Use JSON instead of DeepEval

Teams can export cases and traces as JSON and connect any language or eval
framework through a local stdin/stdout command:

```bash
mendmark audit-json examples/order_agent_suite.json \
  --evaluator-command "python3 examples/json_evaluator.py" \
  --junit /tmp/mendmark.xml \
  --sarif /tmp/mendmark.sarif
```

The command runs locally and receives the original and mutated cases in one batch.
Mendmark strictly validates its metric results. See the [JSON adapter and
protocol](https://github.com/danielgaskins/mendmark/blob/main/docs/json-adapter.md).

Custom domain faults can be loaded from a suite, trusted Python file, installed
entry point, or module attribute. See [custom mutation plugins](https://github.com/danielgaskins/mendmark/blob/main/docs/custom-mutations.md).

The repository also includes a tested [Rubric integration](https://github.com/danielgaskins/mendmark/blob/main/docs/rubric.md)
that runs Rubric metrics through the same JSON protocol.

## CI provenance, budgets, and signatures

Reports automatically record the Mendmark version, adapter, canonical policy
digest, and supported GitHub/GitLab CI metadata. Explicit versions can be added
with `--source-commit`, `--source-ref`, `--suite-version`, and
`--policy-version`. Use `--maximum-mutants` to stop before evaluator work when a
suite exceeds its approved cost ceiling.

Mendmark delegates signatures to Sigstore Cosign:

```bash
mendmark sign mendmark-report.json --bundle mendmark-report.sigstore.json
mendmark verify-signature mendmark-report.json \
  --bundle mendmark-report.sigstore.json \
  --certificate-identity "EXPECTED_OIDC_IDENTITY" \
  --certificate-oidc-issuer "EXPECTED_OIDC_ISSUER"
```

See [artifact signing](https://github.com/danielgaskins/mendmark/blob/main/docs/signing.md),
the [compatibility policy](https://github.com/danielgaskins/mendmark/blob/main/docs/compatibility.md),
the [engine benchmark](https://github.com/danielgaskins/mendmark/blob/main/docs/benchmark.md),
the [user assurance contracts](https://github.com/danielgaskins/mendmark/blob/main/docs/assurance.md),
and the packaged report and baseline JSON Schemas.

## Tool rollout checks

Mendmark hashes each declared tool's name, schema, description, and side-effect
flag. The baseline lets it answer four concrete questions in a pull request:

1. Was a tool added?
2. Did its contract change?
3. Does at least one eval exercise it?
4. Do those evals catch faults in its calls and results?

Mendmark also checks required arguments and basic JSON Schema types in the
actual and expected traces. Reports identify the case, tool, field, and problem
without storing the argument value.

This makes a tool launch visible before it reaches production. It does not prove
the tool is safe. It shows whether the team's current evals can recognize the
failures Mendmark introduced.

## Security and privacy

The suite file is executable Python. Only run suites from code you trust.

Mendmark's JSON report stores case IDs, operator names, severities, metric names,
statuses, and tool schema digests. It does not store prompts, expected answers,
tool arguments, or tool outputs. Teams can run the engine inside their own CI
boundary and publish only the report.

See [SECURITY.md](https://github.com/danielgaskins/mendmark/blob/main/SECURITY.md)
for the trusted-code boundary and private
vulnerability reporting guidance.

## Design-partner pilot

Teams with a real tool-using agent can follow the [pilot guide](https://github.com/danielgaskins/mendmark/blob/main/docs/pilot-guide.md)
and [open a privacy-safe Mendmark pilot request](https://github.com/danielgaskins/mendmark/issues/new?template=pilot.yml).
Do not include prompts, traces, payloads, credentials, or customer data in a
public issue.

## Existing ML integrity pack

Mendmark started as a benchmark for coding agents that repair ML pipelines. That
work remains available through `mendmark prepare`, `mendmark grade`, and the
`MendmarkIntegrityMetric` DeepEval adapter. It checks failures such as label
leakage, train-serve skew, invalid metric aggregation, and broken
reproducibility.

The ML pack is now one specialized use of the broader idea. An evaluator should
be tested against known bad outcomes before its score is trusted.

See [the DeepEval guide](https://github.com/danielgaskins/mendmark/blob/main/docs/deepeval.md)
and the [ML evaluation card](https://github.com/danielgaskins/mendmark/blob/main/docs/evaluation-card.md).

## Current boundary

Version 0.4 is a local, open-source engine. It does not yet provide a hosted
dashboard, team accounts, remote trace ingestion, or a secrets service. The
planned control plane is described in [the product design](https://github.com/danielgaskins/mendmark/blob/main/docs/product.md).

Release history is maintained in [CHANGELOG.md](https://github.com/danielgaskins/mendmark/blob/main/CHANGELOG.md).
