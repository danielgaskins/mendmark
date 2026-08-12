# Changelog

All notable changes to Mendmark are documented here. The project follows
Semantic Versioning for its Python and JSON contracts.

## 0.7.1 - 2026-08-12

### Added

- Five generalized real-world outcome scenarios covering customer refunds,
  employee offboarding, vendor bank-detail changes, production incident
  remediation, and shipment exceptions.
- Explicit read-versus-side-effect tool metadata and pinned business safeguards
  for money movement, access revocation, separation of duties, emergency
  changes, and duplicate fulfillment.

### Changed

- The Enterprise Outcome Golden Set now contains eight workflows, 16 system
  boundaries, 16 invariants, and 64 mutations; state-only assurance detects
  32/64 while complete outcome assurance detects 64/64.

## 0.7.0 - 2026-08-12

### Added

- Outcome contracts for durable business state, reviewed invariants, cost and
  latency budgets, consequence metadata, and a dependency-free evaluator.
- Five outcome-first mutations and an `outcome-first` JSON audit profile that
  tolerates harmless route variation while testing business consequences.
- Business-readable assurance summaries, risk headlines, represented exposure,
  and coverage grouped by outcome integrity, invariants, and execution quality.
- A one-command enterprise demo and golden benchmark spanning common
  CRM/ticketing, ERP/payments, and HRIS/identity workflow shapes.

## 0.6.1 - 2026-08-10

### Added

- Repo-scoped Mendmark skills for Codex and Claude Code, with explicit
  `$mendmark` and `/mendmark` invocation paths and non-destructive auto/all
  targeting through `mendmark equip --agent`.
- An always-generated, agent-neutral `SELF-EQUIP.md` protocol for unsupported
  coding agents, covering harness discovery, JSON fallback, causal trace
  fidelity, reviewed golden behavior, privacy, side effects, baselines, CI,
  and final evidence reporting.

### Changed

- Self-equip metadata now records coding-agent targets, and distribution
  assurance verifies both native skills without modifying existing
  `AGENTS.md`, `CLAUDE.md`, or repository policy.

## 0.6.0 - 2026-08-10

### Added

- Dependency-light, public-object adapters for LangChain/LangGraph messages,
  CrewAI events, and OpenAI Agents SDK run items, including tool-schema and
  side-effect metadata conversion.
- `mendmark equip` for bounded harness detection, non-destructive local
  scaffolding, an offline evaluator, an inactive pinned CI template, and a
  copyable coding-agent self-equip prompt.
- Live compatibility assurance against current releases of all three harness
  paths, plus explicit human approval before observed traces can become
  expected behavior.
- A fluent causal-case builder for reviewed multi-agent delegation, parallel
  dependencies, tool authority, state changes, results, and aggregation without
  hand-authoring schema 2.0 JSON.

## 0.5.0 - 2026-08-06

### Added

- Multi-Agent Golden Set v2 with six diverse topologies, 41 causal events, 294
  mutations across 30 applicable operators, pinned evaluator/schema assets,
  strong/output-only/scheduler-permuted profiles, and checked-in results.
- Ten fault operators for omitted, unexpected, wrong-type, and swapped tool
  arguments; duplicate delegations/results; premature aggregation; stale
  revisions; abandoned branches; and incorrect result correlation.
- Property-style generated-DAG tests, adversarial JSON limits, complete Python
  3.10-3.13 and integration compatibility matrices, and an enforced
  enterprise-scale benchmark.
- Privacy-safe design-partner evidence schema, validator, aggregate utility
  gate, and customer-pattern promotion methodology.
- Release publication now depends on tests, all golden sets, dependency audit,
  enterprise budgets, distribution assurance, and package metadata checks.

- Native multi-agent event graphs with explicit agent contracts, delegation,
  causal dependencies, agent-owned tool calls, results, messages, and shared
  state updates through JSON suite and evaluator protocol `2.0`.
- Twelve coordination mutation operators covering routing, handoff context,
  authorization, dropped and misattributed results, missing dependencies, and
  delegation loops. Existing tool and response operators also mutate event
  graphs.
- Privacy-safe per-agent coverage, agent contract digests in accepted baselines,
  deterministic large-graph assurance, a complete parallel example, and the
  Mendmark Multi-Agent Golden Set.

- A deliberately weak refund-agent suite that demonstrates how an evaluator can
  accept the correct final response while missing broken tool behavior.
- A regression test proving that the weak example exposes surviving critical
  mutations before the complete example kills them.
- A tested Rubric evaluator example that connects Rubric metrics through the
  framework-neutral JSON protocol.
- The Mendmark Agent Eval Golden Set: 24 deterministic cases, 13 tool contracts,
  263 built-in mutations, complete/trace-only/response-only evaluator profiles,
  pinned per-operator outcomes, and reproducible reference performance.

### Fixed

- Python suites can import helper modules stored beside the suite file, matching
  normal script behavior when an audit is launched from another directory.

### Security

- Added an explicit threat model, privacy data flow, enterprise deployment
  checklist, and public support lifecycle.
- Added Dependabot, pull-request dependency review, a scheduled vulnerability
  audit of the resolved integration environment, and a reproducible CycloneDX
  SBOM artifact.

## 0.4.2 - 2026-08-03

### Fixed

- Fetch the annotated release-tag object explicitly in GitHub Actions before
  signature verification. GitHub's release checkout otherwise exposes the tag
  name as a commit ref, which correctly caused the 0.4.1 production guard to
  stop before publication.

## 0.4.1 - 2026-08-03

### Added

- A clean-wheel assurance journey that exercises CLI help, version reporting,
  packaged schemas, installed tasks, and a complete JSON audit outside the
  source checkout.
- Privacy canaries across console, JSON, JUnit, and SARIF output.
- Determinism, actionable-error, and failed-baseline-preservation contracts.
- A dedicated distribution-assurance GitHub Actions job.
- Bounded registry-propagation retries for TestPyPI and PyPI verification.
- SSH-signed commits and release tags, signed-tag verification before release
  builds, protected `main`, and immutable future GitHub releases.
- `mendmark --version` for quick installation diagnosis.

### Compatibility

- The report, baseline, suite, and evaluator protocol schema versions remain
  `1.0`; no existing CLI command or Python API was removed.

## 0.4.0 - 2026-08-03

### Added

- Framework-neutral JSON suites and a single-process batch evaluator protocol.
- Packaged JSON Schemas for suites, evaluator requests and responses, reports,
  and accepted baselines.
- Custom mutation operators from suites, files, module attributes, and the
  `mendmark.mutations` entry-point group.
- JUnit and SARIF CI output.
- Changed-tool-only audits and an optional mutation budget.
- Source, CI, suite, and policy provenance with a canonical policy digest.
- Sigstore Cosign commands for signing and verifying reports and baselines.
- Offline examples, scale benchmark, pilot materials, and Python 3.10/3.13 CI.
- The existing ML integrity task pack in installed wheels, not only source checkouts.

### Security

- Evaluator failures, inconsistent metric sets, malformed plugin output, and
  duplicate mutation IDs are infrastructure errors rather than successful kills.
- Baseline digests and mutation statuses are strictly validated.
- Reports and CI formats continue to exclude prompts and tool payloads.

### Compatibility

- Existing `audit`, `prepare`, `grade`, and `show` commands remain available.
- Report and baseline schema version remains `1.0`; fields were added compatibly.
