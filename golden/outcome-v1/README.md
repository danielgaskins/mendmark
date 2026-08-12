# Mendmark Enterprise Outcome Golden Set

This golden dataset targets durable business results and high-consequence
safeguards rather than requiring one exact execution path. Its three reviewable
cases represent common enterprise workflow shapes:

- customer escalation across CRM and ticketing;
- invoice approval across ERP and payment scheduling; and
- employee onboarding across HRIS and identity provisioning.

Each case declares expected state, two business invariants, a cost ceiling, a
latency ceiling, and report-safe consequence metadata. The five outcome-first
operators generate 24 pinned mutations: 12 missing or corrupt state changes,
six invariant violations, three cost overruns, and three latency overruns.

| Evaluator | Killed | Survived | Result |
| --- | ---: | ---: | --- |
| State only | 12 | 12 | At risk |
| Outcome + invariants + budgets | 24 | 0 | Protected |

The corpus is deterministic, offline, vendor-neutral, and contains no customer
data. Review [suite.json](suite.json), the pinned [manifest](manifest.json), and
[reference results](results.json). Reproduce the comparison with:

```bash
mendmark demo --output-dir outcome-review
python benchmarks/benchmark_outcome_golden_set.py
```

The generated reports add timestamps, but mutation identities and results are
deterministic. Risk estimates illustrate report behavior; they are not claims
about any specific organization and should be replaced with reviewed customer
values in a pilot.
