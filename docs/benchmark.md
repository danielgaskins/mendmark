# Benchmarks

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

## Engine scaling benchmark

This benchmark measures Mendmark's in-process mutation and report overhead. It
does not measure an external evaluator, model latency, or provider cost.

Run on August 3, 2026 with CPython 3.10 on the development Linux workstation:

| Cases | Mutations | Evaluation items | Time | Peak memory | Report size |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 13 | 14 | 0.001 s | 59 KiB | 5.4 KiB |
| 10 | 130 | 140 | 0.007 s | 256 KiB | 45 KiB |
| 100 | 1,300 | 1,400 | 0.071 s | 2.4 MiB | 446 KiB |
| 1,000 | 13,000 | 14,000 | 0.785 s | 24.1 MiB | 4.4 MiB |

These are single samples, not service-level objectives. Real audit cost is
usually dominated by evaluator work. Use the benchmark for regression direction,
then measure the customer's actual suite and evaluator.

Reproduce it with:

```bash
python benchmarks/benchmark_audit.py --cases 1 10 100 1000
```

The JSON adapter invokes its evaluator command once per audit with all evaluation
items. `--maximum-mutants` can enforce a pre-evaluation ceiling. Bounded
concurrency should be added only if pilot measurements show that evaluator
latency warrants the operational complexity.
