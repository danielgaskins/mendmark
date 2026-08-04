# Mendmark Agent Eval Golden Set v1

The Mendmark Agent Eval Golden Set is the project's canonical, versioned
benchmark for mutation-testing agent evaluators. Every file needed to inspect or
reproduce it is in this directory.

## Contents

- 24 passing agent cases across ten operating domains.
- 13 read-only and side-effecting tool contracts.
- 39 tool calls, including 21 side effects.
- Zero-, one-, two-, and three-call workflows.
- String, integer, number, boolean, array, and nested-object payloads.
- 263 applicable mutations from all nine Mendmark 0.4 built-in operators.
- Three evaluator profiles with pinned aggregate and per-operator outcomes.

The cases cover search, commerce, payments, CRM, communications, databases,
scheduling, weather, support, and multi-step workflow behavior. The complete
case contents and expected traces are reviewable in [`suite.json`](suite.json).

## Methodology

Every original case must pass its evaluator profile. Mendmark then applies each
eligible built-in operator and reruns the same profile. A mutation is killed only
when a metric passes on the original case and fails on the changed case.

The benchmark compares three deterministic profiles:

| Profile | Checks | Golden result |
| --- | --- | ---: |
| `complete` | Exact ordered tool trace and final outcome | 263/263 killed (100%) |
| `trace-only` | Exact ordered tool trace only | 215/263 killed (81.749%) |
| `response-only` | Exact final outcome only | 87/263 killed (33.080%) |

The contrast is intentional. It measures whether Mendmark distinguishes an
evaluator with complete sensitivity from evaluators that ignore either response
quality or tool behavior.

[`manifest.json`](manifest.json) pins the suite SHA-256, the digest of all sorted
mutation IDs, per-operator mutation counts, expected exit codes, gate decisions,
summaries, and per-operator statuses. A change to corpus bytes, mutation identity,
applicability, or evaluator behavior therefore fails the benchmark until the
golden contract is deliberately reviewed and versioned.

## Reproduce

From the repository root:

```bash
python benchmarks/benchmark_golden_set.py
```

The command runs all profiles through the public `audit-json` CLI and local JSON
evaluator protocol. It makes no model or network calls. A nonzero exit indicates
that the measured result differs from the checked-in golden contract.

Reference measurements for the current release are stored in
[`results.json`](results.json). Runtime is machine-dependent; mutation counts,
statuses, kill rates, and gate decisions are contractual.

## Interpretation

The complete profile's 100% result means it detects every generated fault in
this golden set. It is not an agent-accuracy or general safety score. The set is
public and deterministic so users can audit the methodology, reproduce results,
and identify missing cases or failure classes through ordinary pull requests.
