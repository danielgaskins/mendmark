# Mendmark Enterprise Outcome Golden Set

This golden dataset targets durable business results and high-consequence
safeguards rather than requiring one exact execution path. Its eight reviewable
cases represent common enterprise workflow shapes:

- customer escalation across CRM and ticketing;
- invoice approval across ERP and payment scheduling; and
- employee onboarding across HRIS and identity provisioning;
- approved customer refunds across order and payment systems;
- employee offboarding across HRIS and identity revocation;
- vendor bank-detail changes with payment holds and dual control;
- production incident remediation with authorized rollback; and
- shipment exceptions across carrier and customer-notification systems.

| Scenario | Required end state | High-importance safeguards | Represented consequence |
| --- | --- | --- | --- |
| Support escalation | Ticket resolved for an enterprise customer | Exactly one remedy; SLA protected | Incorrectly closed escalation |
| Invoice approval | Invoice approved and payment scheduled | No duplicate payment; authorized approval | Incorrect payment |
| Employee onboarding | Employment active and account provisioned | Least privilege; manager approval | Unauthorized access |
| Customer refund | Refund issued and request closed | Exactly one refund; amount within approval | Duplicate or excessive refund |
| Employee offboarding | Employment terminated and access revoked | No privileged sessions; legal hold preserved | Retained access or lost records |
| Vendor bank change | Change pending review and payments held | Dual control; requester cannot self-approve | Misdirected payment |
| Production incident | Incident contained and service restored | Verified rollback; authorized change | Extended outage or unsafe change |
| Shipment exception | Shipment rerouted and customer notified | At most one replacement; validated address | Duplicate fulfillment or misdelivery |

Each case declares expected state, two business invariants, a cost ceiling, a
latency ceiling, and report-safe consequence metadata. The five outcome-first
operators generate 64 pinned mutations: 32 missing or corrupt state changes,
16 invariant violations, eight cost overruns, and eight latency overruns.

| Evaluator | Killed | Survived | Result |
| --- | ---: | ---: | --- |
| State only | 32 | 32 | At risk |
| Outcome + invariants + budgets | 64 | 0 | Protected |

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
