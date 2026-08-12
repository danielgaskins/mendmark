# Benchmarks

## Enterprise Outcome Golden Set

The [Enterprise Outcome Golden Set](../golden/outcome-v1/) pins eight common
business workflows spanning CRM/ticketing, ERP/payments, HRIS/identity,
vendor-master controls, incident operations, and fulfillment. It contains 16
reviewed invariants and 64 outcome-first mutations. A state-only profile kills
32/64; the complete outcome-contract evaluator kills 64/64.

```bash
mendmark demo --output-dir outcome-review
```

The generated suite and reports are deterministic apart from report timestamps.
They require no model, network, service credentials, or customer data.

## Agent Eval Golden Set

The [Mendmark Agent Eval Golden Set](../golden/agent-eval-v1/) is the canonical
behavioral benchmark. It pins 24 cases, 13 tools, 263 mutations, and the expected
per-operator results for complete, trace-only, and response-only evaluator
profiles.

On the August 4, 2026 reference workstation, ten full CLI runs per profile had
the following median wall times:

| Profile | Median | Result |
| --- | ---: | ---: |
| Complete | 0.151 s | 263/263 killed |
| Trace only | 0.139 s | 215/263 killed |
| Response only | 0.141 s | 87/263 killed |

These timings include CLI startup, mutation generation, one JSON evaluator
process, policy evaluation, and report writing. They exclude installation and
make no model or network calls. Runtime is machine-dependent; the corpus digest,
mutation identities, outcome counts, kill rates, and gate decisions are the
golden contract.

Reproduce and verify it with:

```bash
python benchmarks/benchmark_golden_set.py --repeats 10
```

## Multi-Agent Golden Sets

The [Mendmark Multi-Agent Golden Set](../golden/multi-agent-v1/) pins a complete
parallel supervisor workflow with 3 agents, 3 tools, 9 causal events, and 44
applicable mutations across 20 operators. The reference graph-and-outcome
evaluator kills all 44 mutations.

```bash
python benchmarks/benchmark_multi_agent_golden_set.py
```

The corpus, evaluator, suite digest, mutation-ID digest, per-operator counts,
summary, and gate result are checked in and reproducible without a model or
network connection.

[Version 2](../golden/multi-agent-v2/) is the broader current benchmark: six
workflows, 17 agent declarations, 41 events, 30 applicable operators, and 294
mutations. The strong and reversed-scheduler profiles kill 294/294; the
output-only profile kills 23/294 and misses 181 critical failures.

```bash
python benchmarks/benchmark_multi_agent_golden_set_v2.py
```

## Engine scaling benchmark

This benchmark measures Mendmark's in-process mutation and report overhead. It
does not measure an external evaluator, model latency, or provider cost.

Run on August 3, 2026 with CPython 3.10 on the development Linux workstation:

| Cases | Mutations | Evaluation items | Time | Peak memory | Report size |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 19 | 20 | 0.004 s | 102 KiB | 9.0 KiB |
| 10 | 190 | 200 | 0.025 s | 398 KiB | 68 KiB |
| 100 | 1,900 | 2,000 | 0.235 s | 3.8 MiB | 662 KiB |
| 1,000 | 19,000 | 20,000 | 2.032 s | 39.0 MiB | 6.5 MiB |

These are single samples, not service-level objectives. Real audit cost is
usually dominated by evaluator work. Use the benchmark for regression direction,
then measure the customer's actual suite and evaluator.

Reproduce it with:

```bash
python benchmarks/benchmark_audit.py --cases 1 10 100 1000
```

The enforced enterprise benchmark adds complete multi-agent evaluation, JUnit,
SARIF, report sizing, and selected-case incremental audits. Default budgets are
30 seconds, 512 MiB peak memory, and a 64 MiB JSON report for each scenario.
The August 6, 2026 reference run completed 1,000 single-agent cases/19,000
mutations in 2.11 seconds and 250 multi-agent cases/13,500 mutations in 1.85
seconds, each under 40 MiB peak memory.

```bash
python benchmarks/benchmark_enterprise.py
```

The JSON adapter invokes its evaluator command once per audit with all evaluation
items. `--maximum-mutants` can enforce a pre-evaluation ceiling. Bounded
concurrency should be added only if pilot measurements show that evaluator
latency warrants the operational complexity.
