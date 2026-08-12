# Outcome assurance

Business owners are right to judge an agent by what changed in the business.
Mendmark therefore treats durable outcome state as the primary assurance
surface. A polished final response is not an outcome, and a database row alone
is not enough when duplicate payment, missing authority, cost, or latency can
still make the workflow unacceptable.

## The contract

Each case can declare an `outcome` with:

- `objective`: a short, approved description of the business result;
- `actual_state` and `expected_state`: JSON snapshots from a trusted post-action
  read, where expected state is matched as a recursive subset;
- `invariants`: reviewed safeguards addressed by RFC 6901 JSON Pointer;
- `actual_cost_usd` / `maximum_cost_usd` and duration equivalents; and
- `risk`: a report-safe headline, category, severity, and optional exposure and
  recovery estimates.

Risk headlines and invariant descriptions appear in reports. Keep them free of
customer identifiers, personal data, secrets, and raw payload values.

Supported invariant operators are `equals`, `not_equals`, `exists`,
`not_exists`, `greater_than_or_equal`, `less_than_or_equal`, and `contains`.
`OutcomeContractEvaluator` evaluates these contracts locally without inspecting
the route taken or making network calls.

For a JSON suite, the evaluator is built in:

```bash
mendmark audit-outcomes suite.json --output outcome-report.json
```

## Two assurance modes

`--mutation-profile outcome-first` tests five high-importance fault families:
missing required state, corrupted state, violated invariants, exceeded cost, and
exceeded latency. This is the right stakeholder-facing gate when multiple valid
execution paths lead to the same safe result.

The default profile also tests tool arguments and results, duplicated side
effects, recovery claims, delegation, authorization, shared state, and causal
coordination. Use it when path behavior can change the real outcome or its risk.
The report groups findings into outcome integrity, business invariants, and
execution quality so the same artifact serves both audiences.

## Fast enterprise demonstration

```bash
mendmark demo
mendmark demo invoice-approval --output-dir demo-review
```

The scenarios use vendor-neutral shapes common to CRM/ticketing,
ERP/accounts-payable, and HRIS/identity systems. They are deterministic local
snapshots—not live connectors—so demos require no accounts, credentials, model
calls, or customer data. Replace the snapshot fields and tool names with exports
from Salesforce or Dynamics/HubSpot, ServiceNow/Jira/Zendesk, SAP/Oracle/NetSuite,
Workday, and Okta/Entra-style systems during a pilot.

The command writes `suite.json`, `state-only-report.json`, and
`outcome-assurance-report.json`. The contrast demonstrates precisely which
business safeguards a simple end-state check leaves untested.
