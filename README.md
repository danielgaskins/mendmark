<div align="center">
  <h1>Mendmark</h1>
  <p><strong>Mutation testing for agent evals.</strong></p>
  <p>Find the broken tool calls your passing tests still accept.</p>
  <p>
    <a href="https://github.com/danielgaskins/mendmark/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/danielgaskins/mendmark/actions/workflows/tests.yml/badge.svg"></a>
    <a href="https://github.com/danielgaskins/mendmark/actions/workflows/security.yml"><img alt="Security" src="https://github.com/danielgaskins/mendmark/actions/workflows/security.yml/badge.svg"></a>
    <a href="https://pypi.org/project/mendmark-evals/"><img alt="PyPI" src="https://img.shields.io/pypi/v/mendmark-evals?color=2563eb"></a>
    <img alt="Python 3.10–3.13" src="https://img.shields.io/badge/python-3.10%E2%80%933.13-3776ab">
    <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-0f766e"></a>
  </p>
  <p>
    <a href="#quick-start">Quick start</a> ·
    <a href="#agent-eval-golden-set">Golden set</a> ·
    <a href="docs/agent-mutation-audits.md">How it works</a> ·
    <a href="docs/pilot-guide.md">Run a pilot</a>
  </p>
</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/danielgaskins/mendmark/main/docs/assets/mendmark-readme-hero.svg" width="100%" alt="Mendmark changes one part of a passing agent trace, reruns existing evaluators, and identifies killed faults and surviving blind spots.">
</p>

Your agent tests can all pass and still miss a broken tool call. Mendmark tests
the tests themselves: it plants one controlled fault, runs the same evaluators
again, and turns every survivor into a concrete blind spot to fix.

> **Killed** means the eval noticed the planted fault. **Survived** means the
> damaged case still passed. A critical survivor can fail the release gate.

## Quick start

Mendmark requires Python 3.10 or newer.

```bash
pip install 'mendmark-evals[deepeval]'

git clone https://github.com/danielgaskins/mendmark.git
cd mendmark

mendmark audit examples/order_agent_suite.py \
  --output mendmark-report.json \
  --write-baseline
```

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

## See the blind spot in two minutes

**[▶ Watch the narrated weak-eval demonstration](docs/assets/mendmark-weak-eval-demo.mp4)**

A refund-agent test checks only the final sentence. Mendmark finds that 9 of 13
faults escape—including a wrong refund amount and a duplicated refund. A
complete evaluator checks the calls, arguments, results, and response, killing
all 13.

## Agent Eval Golden Set

The [Mendmark Agent Eval Golden Set](golden/agent-eval-v1/) is the canonical,
versioned benchmark for the mutation engine.

<table>
  <tr>
    <td align="center"><strong>24</strong><br>reviewable cases</td>
    <td align="center"><strong>13</strong><br>tool contracts</td>
    <td align="center"><strong>39</strong><br>tool calls</td>
    <td align="center"><strong>263</strong><br>pinned mutations</td>
    <td align="center"><strong>10</strong><br>domains</td>
  </tr>
</table>

| Evaluator profile | Killed | Survived | Kill rate |
| --- | ---: | ---: | ---: |
| **Complete trace and outcome** | **263** | **0** | **100.000%** |
| Trace only | 215 | 48 | 81.749% |
| Response only | 87 | 176 | 33.080% |

The response-only profile leaves **162 critical tool-behavior mutations**
undetected. The complete profile catches every mutation in the golden set.

```bash
python benchmarks/benchmark_golden_set.py
```

Review the [manifest](golden/agent-eval-v1/manifest.json),
[case suite](golden/agent-eval-v1/suite.json), evaluator profiles,
[methodology](golden/agent-eval-v1/README.md), and
[reference performance](golden/agent-eval-v1/results.json) directly. The
benchmark is deterministic, offline, and makes no model calls.

## Built for real CI

<table>
  <tr>
    <td width="50%"><strong>🔎 Expose evaluator blind spots</strong><br>Wrong arguments, corrupted results, reordered calls, duplicate side effects, false recovery, and damaged responses.</td>
    <td width="50%"><strong>🧰 Fit the existing stack</strong><br>DeepEval, Rubric, or any local evaluator through a validated JSON subprocess protocol.</td>
  </tr>
  <tr>
    <td width="50%"><strong>🚦 Gate tool rollouts</strong><br>Per-tool coverage, schema-change detection, accepted baselines, mutation budgets, JUnit, and SARIF.</td>
    <td width="50%"><strong>🔐 Keep case content local</strong><br>Reports omit prompts, answers, tool arguments, and tool outputs; artifacts can be signed with Cosign.</td>
  </tr>
</table>

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
for private vulnerability reporting, the
[threat model and deployment checklist](https://github.com/danielgaskins/mendmark/blob/main/docs/threat-model.md)
for the complete trusted-code boundary, and
[SUPPORT.md](https://github.com/danielgaskins/mendmark/blob/main/SUPPORT.md)
for version and support expectations.

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
