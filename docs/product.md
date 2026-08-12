# Mendmark product design

## One-line promise

Mendmark tells an agent team whether its evals would catch a broken tool call or
coordination failure before that failure reaches users.

## Buyer and pain

The first buyer is an engineering or AI lead shipping a tool-using agent. The
team already has traces and a few evals. Every new tool, model, prompt, and
workflow creates a release question that is hard to answer:

> Did we improve the agent, or did our tests simply fail to notice what broke?

The cost appears as slow launches, manual trace review, production regressions,
and arguments about whether an aggregate score can be trusted.

## Product surfaces

### Open-source engine

- Runs inside a customer's CI or VPC.
- Adapts cases from DeepEval and, later, other eval frameworks.
- Applies built-in and custom mutations.
- Produces privacy-safe JSON.
- Enforces release policy without a hosted dependency.

### Hosted control plane

- Stores report metadata, not raw prompts by default.
- Shows kill rate and critical survivors by service, branch, and release.
- Tracks tool schemas and marks new or changed tools.
- Assigns surviving mutations to an owner.
- Compares model, prompt, and evaluator versions.
- Posts a concise pull-request check.
- Maintains an audit trail for accepted exceptions.

### Enterprise runner

- Runs fully inside the customer's cloud account.
- Supports private package registries and secrets managers.
- Signs reports and records build provenance.
- Adds role-based access, SSO, retention policy, and export controls.

## Core workflow

1. Import passing agent cases from the existing eval suite.
2. Register the tools the agent may call.
3. Run a local audit and inspect every surviving fault.
4. Strengthen weak evaluators or accept a documented exception.
5. Save the first passing baseline.
6. Add the audit to pull requests and release CI.
7. Review new tool contracts and mutation regressions before deployment.

## Commercial wedge

Most eval platforms help teams write and run evaluators. Mendmark tests whether
those evaluators are sensitive to realistic failures. It can work beside the
customer's current platform, so adoption does not require a trace migration.

The first narrow wedge is tool rollout safety. A team adding a payment, search,
database, or workflow tool gets an immediate answer about missing coverage and
the exact faults its current evals miss.

## Pricing hypothesis

The engine should remain open source.

| Plan | Price hypothesis | Customer |
| --- | ---: | --- |
| Local | Free | Individual developer or open-source project |
| Team | $299 per month | One agent team, hosted history, PR checks, alerts |
| Growth | $999 per month | Several agents, SSO, policy templates, longer history |
| Enterprise | Annual contract | VPC runner, audit controls, support, custom retention |

Pricing should be tested through customer interviews. A useful value metric may
be active agent services rather than seats or trace volume because local audits
do not require raw trace ingestion.

## Security model

- Run mutations where the cases already live.
- Keep prompts and tool payloads local by default.
- Send only IDs, hashes, aggregate counts, statuses, and policy results to the
  hosted control plane.
- Treat suite files and custom operators as trusted code.
- Sign reports in CI and attach source commit, suite version, and runner version.
- Never claim a mutation gate proves an agent is safe. It proves only that the
  configured eval suite detected the faults that were tested.

## Roadmap

### Current open-source release

- Framework-neutral case and tool model.
- Native single-agent traces and multi-agent causal event graphs.
- DeepEval suite adapter.
- Framework-neutral JSON suite and local batch evaluator protocol.
- Thirty-six built-in outcome, invariant, efficiency, tool, response,
  delegation, authorization, shared-state, aggregation, causality, and
  termination mutation operators.
- Validated domain-specific mutation plugins.
- Per-tool coverage and tool schema tracking.
- Baseline regression gates.
- Privacy-safe JSON output.
- JUnit, SARIF, and changed-tool-only CI audits.
- Source/CI provenance, mutation cost ceilings, and public report schemas.
- Sigstore Cosign signing and verification for reports and baselines.
- Existing deterministic ML integrity pack.
- Versioned Agent Eval Golden Set with 24 cases, 263 mutations, three evaluator
  profiles, and pinned per-operator outcomes.
- Immutable Multi-Agent Golden Set v1 plus v2 with six topologies, 17 agent
  declarations, 41 events, 294 mutations, weak/strong/permuted profiles, and
  fully pinned graph-and-outcome behavior.
- Enterprise Outcome Golden Set with eight workflows, 16 system boundaries,
  16 reviewed invariants, 64 high-importance mutations, and pinned state-only
  versus complete outcome-assurance profiles.
- Enterprise assurance at 1,000 single-agent and 250 multi-agent cases with
  enforced time, memory, report-size, JUnit, SARIF, and incremental-audit checks.
- A machine-validated, privacy-safe design-partner evidence rubric and utility
  gate that cannot be satisfied by planned or unreviewed pilots.

### Next

- Pilot the JSON adapter with real agent teams and select the next framework
  adapter from observed demand.
- Measure real-suite runtime, evaluator cost, and report size using explicit
  mutation budgets and the pilot scorecard.
- Consider OpenTelemetry, OpenAI Agents SDK, LangSmith, Phoenix, or Braintrust
  only after the pilot identifies a clear adoption bottleneck.

### Hosted validation release

- Read-only report ingestion.
- Project dashboard and pull-request summaries.
- Critical survivor triage.
- Tool rollout history.
- Team policy and exception workflow.

## Validation questions

Customer calls should test these claims:

1. Which agent failure was most expensive or embarrassing?
2. How did the team learn its evaluator had missed it?
3. What must pass before a new tool is enabled?
4. Who owns eval quality and release approval?
5. Can privacy-safe metadata leave the customer's cloud?
6. Would a surviving fault block a release?
7. Is the budget attached to observability, testing, security, or AI platform?

The strongest early signal is not general interest. It is a team willing to run
Mendmark against a real eval suite and fix a survivor before shipping.
