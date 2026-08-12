<div align="center">
  <h1>Mendmark</h1>
  <p><strong>Prove your agent evals catch costly business failures.</strong></p>
  <p>Test outcomes, business invariants, tool use, and multi-agent coordination before production does.</p>
  <p>
    <a href="https://github.com/danielgaskins/mendmark/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/danielgaskins/mendmark/actions/workflows/tests.yml/badge.svg"></a>
    <a href="https://github.com/danielgaskins/mendmark/actions/workflows/security.yml"><img alt="Security" src="https://github.com/danielgaskins/mendmark/actions/workflows/security.yml/badge.svg"></a>
    <a href="https://pypi.org/project/mendmark-evals/"><img alt="PyPI" src="https://img.shields.io/pypi/v/mendmark-evals?color=2563eb"></a>
    <img alt="Python 3.10–3.13" src="https://img.shields.io/badge/python-3.10%E2%80%933.13-3776ab">
    <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-0f766e"></a>
  </p>
  <p>
    <a href="#quick-start">Quick start</a> ·
    <a href="#equip-an-agent-harness">Harnesses</a> ·
    <a href="#agent-eval-golden-set">Golden set</a> ·
    <a href="docs/multi-agent.md">Multi-agent</a> ·
    <a href="docs/agent-mutation-audits.md">How it works</a> ·
    <a href="docs/pilot-guide.md">Run a pilot</a>
  </p>
</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/danielgaskins/mendmark/main/docs/assets/mendmark-readme-hero.svg" width="100%" alt="Mendmark changes one part of a passing agent trace, reruns existing evaluators, and identifies killed faults and surviving blind spots.">
</p>

Your agent tests can all pass while an invoice is paid twice, access is granted
without authority, or a required tool action silently disappears. Mendmark tests
the tests themselves: it plants one controlled fault, runs the same evaluators
again, and translates every survivor into a business-readable risk and a precise
engineering finding.

> **Killed** means the eval noticed the planted fault. **Survived** means the
> damaged case still passed. A critical survivor can fail the release gate.

## Quick start

Mendmark requires Python 3.10 or newer.

See the outcome-first value with no service credentials, model calls, or fixture
setup:

```bash
pip install mendmark-evals
mendmark demo
```

The command compares a conventional state-only evaluator with complete outcome
assurance across eight customer, finance, identity, operations, and fulfillment
workflows. It writes a reviewable JSON suite and both privacy-safe reports to
`mendmark-enterprise-demo/`.

Audit a reviewed outcome suite directly—without an evaluator framework or
subprocess:

```bash
mendmark audit-outcomes mendmark-enterprise-demo/suite.json
```

For an existing DeepEval suite:

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
Business assurance: PROTECTED
Configured business risks were detected by the eval suite.
Cases: 1
Mutations: 19  Killed: 19  Survived: 0  Errors: 0
Mutation kill rate: 100.0%
New tools: lookup_order, refund_order
Gate: PASS
```

Run the same command in CI without `--write-baseline`. Mendmark compares the
current tool schemas and mutation results with the last accepted baseline.

For a native parallel multi-agent audit:

```bash
mendmark audit-json examples/multi_agent_suite.json \
  --evaluator-command "python3 examples/multi_agent_evaluator.py"
```

## Equip an agent harness

Mendmark has dependency-light adapters for LangChain/LangGraph, CrewAI, and the
OpenAI Agents SDK. In an existing agent repository:

```bash
python -m pip install 'mendmark-evals==0.7.1'
mendmark equip --framework auto --agent auto
```

The command detects bounded dependency files and creates a reviewed capture
guide, offline evaluator, and inactive CI template under `.mendmark/`. It does
not edit application code, upload a trace, overwrite existing work, enable CI,
or accept a baseline.

Want Codex or Claude Code to perform the integration? Install its native,
repo-scoped skill (use `all` to install both):

```bash
mendmark equip --framework auto --agent codex       # invoke with $mendmark
mendmark equip --framework auto --agent claude-code # invoke with /mendmark
```

For any other repository-capable agent, print a portable self-equip prompt:

```bash
mendmark equip --agent generic --print-agent-prompt
```

See the [agent harness integration guide](docs/harness-integrations.md) for the
direct Python APIs, explicit trace-approval boundary, framework compatibility,
and multi-agent guidance.

## See the blind spot in two minutes

**[▶ Watch the narrated weak-eval demonstration (original v1 fault inventory)](docs/assets/mendmark-weak-eval-demo.mp4)**

A refund-agent test checks only the final sentence. Mendmark finds that 15 of 19
faults escape—including a wrong refund amount and a duplicated refund. A
complete evaluator checks the calls, arguments, results, and response, killing
all 19.

## Outcome-first for business and engineering teams

An outcome contract records the durable business state that must exist, the
invariants that must never be violated, and optional cost and latency limits.
Mendmark then tests whether the evaluator detects missing or corrupted state,
broken safeguards, and exceeded operating limits. Reports lead with plain-language
headlines such as “An invoice can be paid incorrectly,” followed by stable case
and operator identifiers engineers can act on.

Use `--mutation-profile outcome-first` when route variation is harmless and the
business result is the release criterion. Use the default full profile when the
route itself can change authorization, side effects, recovery, cost, or
coordination safety. See [Outcome assurance](docs/outcome-assurance.md) for the
contract model and decision rule.

## Agent Eval Golden Set

The [Enterprise Outcome Golden Set](golden/outcome-v1/) targets the business
surface directly: eight common workflows, 16 system boundaries, 16 reviewed
invariants, and 64 high-importance mutations. It covers support escalation,
invoice approval, onboarding, refunds, offboarding, vendor bank changes,
incident remediation, and shipment exceptions. Its state-only profile detects
32/64; the complete outcome-contract profile detects 64/64. Run it instantly
with `mendmark demo`.

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

Native coordination behavior has its own reviewable
[Multi-Agent Golden Set v2](golden/multi-agent-v2/): **6 workflows, 17 agent
declarations, 41 causal events, 30 operators, and 294/294 mutations killed** by
the complete reference evaluator.

```bash
python benchmarks/benchmark_multi_agent_golden_set_v2.py
```

For contrast, the v2 output-only evaluator detects just **23/294** and leaves
**271 survivors, 181 critical**. Mendmark groups those blind spots by
category and pinpoints the affected agent, event, and tool using privacy-safe
identifiers. See the [multi-agent guide](docs/multi-agent.md) for both commands.

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

## One engine for single-agent and multi-agent systems

Single-agent suites use a simple ordered tool trace. Multi-agent suites add a
causal event graph with agent identities, delegation targets, explicit tool
permissions, returned results, shared-state events, and dependencies. Existing
`1.0` suites remain unchanged; native graphs use the validated `2.0` JSON
contract.

Mendmark mutates both layers. It can break an individual tool call, route work
to the wrong specialist, omit handoff context, drop or misattribute a result,
violate an agent's tool permissions, remove a causal dependency, or insert a
delegation loop. Independent parallel branches are not forced into an arbitrary
wall-clock order.

The included three-agent reference suite has 9 events across parallel billing
and risk branches. Its complete evaluator kills all 64 currently applicable
mutations. The broader v2 golden set covers six topologies and kills 294/294.
See the [multi-agent guide](docs/multi-agent.md) and reviewable
[JSON suite](examples/multi_agent_suite.json).

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

Completed pilots use the machine-validated
[design-partner evidence contract](pilot/) to record time-to-value, mutation
realism, equivalent faults, discovered/remediated blind spots, runtime, cost,
and CI retention without storing customer content. Until that external utility
gate passes, golden-set results are engine evidence—not a claim of universal
agent safety or customer validation.

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

Version 0.7 is a local, open-source engine. It does not yet provide a hosted
dashboard, team accounts, remote trace ingestion, or a secrets service. The
planned control plane is described in [the product design](https://github.com/danielgaskins/mendmark/blob/main/docs/product.md).

Release history is maintained in [CHANGELOG.md](https://github.com/danielgaskins/mendmark/blob/main/CHANGELOG.md).
