# Mendmark product handoff

Last updated: August 3, 2026

Repository: <https://github.com/danielgaskins/mendmark>

Current stable release: `0.4.0`

0.4 implementation baseline: commit `eb0d5efabb50cb46083b945ef9f96edbab667b26`

## Release status

Version 0.4.0 is published as `mendmark-evals` on PyPI and TestPyPI. The
production release was built from the `v0.4.0` annotated tag through the
protected `pypi` GitHub environment and PyPI Trusted Publishing. PyPI exposes a
provenance attestation for both the wheel and source distribution identifying
`danielgaskins/mendmark`, `release.yml`, and the `pypi` environment.

The repository now uses SSH signatures for commits and tags. GitHub has the
maintainer public key registered as a signing key, `.github/allowed_signers`
defines the repository verification identity, and `release.yml` rejects
unsigned or untrusted future release tags before building. The already-published
`v0.4.0` tag remains an unsigned historical exception because rewriting a public
release tag would invalidate consumers' existing reference; its distributions
retain PyPI provenance attestations.

GitHub branch protection requires signed commits on `main`, including for
administrators, and rejects force-pushes, deletion, and non-linear history.
Repository-level immutable releases are enabled for future releases. GitHub does
not apply that setting retroactively, so the existing 0.4.0 release remains the
documented historical exception.

Release verification completed on August 3, 2026:

- Python 3.10 and 3.13 CI passed on the release commit.
- TestPyPI publication and a clean-install JSON audit passed.
- PyPI publication and a clean-install JSON audit passed.
- The public pilot recruitment issue is
  <https://github.com/danielgaskins/mendmark/issues/1>.

Release links:

- <https://github.com/danielgaskins/mendmark/releases/tag/v0.4.0>
- <https://pypi.org/project/mendmark-evals/0.4.0/>
- <https://test.pypi.org/project/mendmark-evals/0.4.0/>

## Read this first

Mendmark is an open-source Python tool for mutation testing agent eval suites.

The shortest accurate description is:

> You test your agent. Mendmark tests whether those tests catch realistic
> failures.

Mendmark takes passing agent cases, plants one controlled fault at a time, and
runs the team's existing evaluators again. A fault is **killed** when an
evaluator changes from pass to fail. A fault **survives** when the damaged case
still passes. Surviving faults identify specific gaps in the eval suite.

The current product is a local engine and CLI with DeepEval and framework-neutral
JSON adapters. It is not yet a hosted platform. Do not describe the dashboard,
team service, additional framework adapters, or enterprise runner as completed
features.

## Why the product exists

Agent teams can accumulate passing evals without knowing whether those evals
would notice a real failure. This gets worse as an agent gains tools. A suite
may check that the agent chose `refund_order` while ignoring whether it used the
wrong amount, called the tool twice, skipped the required lookup, or claimed
success after the tool failed.

An aggregate score hides those gaps. Mendmark gives the team a concrete answer:

- Which controlled failures did the evals catch?
- Which failures passed unnoticed?
- Which tool lacks meaningful eval coverage?
- Did a new tool or schema change arrive without adequate tests?
- Did an evaluator stop catching a fault that it caught in the accepted
  baseline?

## Target user and first commercial wedge

The first user is an AI engineer, evaluation lead, or platform engineer shipping
a tool-using agent. The team already has traces and at least a small eval suite.

The first wedge is **tool rollout safety**:

> Before enabling a new payment, search, database, or workflow tool, show that
> the current eval suite catches broken calls and unsafe outcomes involving that
> tool.

This wedge is useful because it maps to a release decision. It also lets
Mendmark work beside an existing eval platform. A team does not need to move its
traces or replace DeepEval to try the product.

## What works today

### Mutation engine

The framework-neutral mutation engine operates on `AgentCase`,
`ToolCallRecord`, and `ToolSpec` objects.

Nine built-in mutation operators are included:

| Operator | Controlled fault | Severity |
| --- | --- | --- |
| `tool.removed` | Remove one tool call | Critical |
| `tool.arguments_changed` | Change one argument in one call | Critical |
| `tool.output_corrupted` | Replace a tool result with an error | Critical |
| `tool.side_effect_duplicated` | Repeat one side-effecting call | Critical |
| `tool.order_reversed` | Reverse a multi-tool trace | High |
| `tool.unknown_added` | Add a tool absent from the registry | Critical |
| `recovery.false_success` | Return success after one tool fails | Critical |
| `response.omitted` | Remove the final response | High |
| `response.replaced` | Replace the response with a generic claim | High |

Operators create a separate mutation for every applicable tool call. One case
with two tools therefore produces more than nine mutations.

### Meta-evaluation runner

The runner:

1. Runs every original case through the configured evaluators.
2. Rejects an original case that does not pass its own suite.
3. Generates one-fault mutations.
4. Runs the same evaluator suite against each mutation.
5. Records which metric killed each mutation.
6. Calculates the mutation kill rate and per-tool coverage.
7. Compares current results with the accepted baseline.
8. Applies a release policy and returns a CI-compatible exit code.

An evaluator exception is recorded as an error. It does not count as a killed
mutation.

### Tool rollout checks

Mendmark hashes each declared tool's:

- Name
- Description
- Input schema
- Side-effect flag

The report identifies tools added, removed, or changed since the baseline. It
also reports declared tools that no case exercises.

Basic tool-contract validation currently checks:

- Undeclared tools in actual or expected traces
- Missing required arguments
- Basic JSON Schema types for supplied arguments

Contract reports identify the case, trace, call index, tool, field, and problem.
They do not store the argument value.

### Regression baseline

The baseline stores:

- Tool schema digests
- Mutation IDs and their last accepted statuses
- Provenance from the report that created the accepted baseline

Mendmark detects:

- A previously killed mutation that now survives or errors
- A previously surviving mutation that is now killed
- New and removed mutations
- Added, removed, and changed tools

A failed audit cannot overwrite the baseline.

### Current release policy

The default audit fails when:

- Mutation kill rate is below 80 percent.
- A critical mutation survives.
- A declared tool has no case coverage.
- A tool contract issue exists.
- An original case fails its own eval suite.
- A mutation killed in the accepted baseline now survives or errors.

Suites can configure this through `MENDMARK_POLICY`. CLI flags can relax a rule
for local exploration.

### DeepEval adapter

The current adapter loads a trusted local Python suite. That suite exports:

- `TOOLS`
- `get_cases()`
- `get_metrics()`
- Optional `MENDMARK_POLICY`

`get_metrics()` must return fresh DeepEval metric instances on every call.
Metric names must be unique.

The included example uses deterministic DeepEval custom metrics. It requires no
API key and makes no model calls.

### Framework-neutral JSON adapter

`mendmark audit-json` loads a strictly validated JSON suite and calls any local
evaluator executable through a versioned JSON batch protocol. The evaluator is
started once per audit and receives every original and mutated case through
stdin. This avoids a Python or DeepEval dependency in the customer's application
and avoids per-mutation process startup. Command failures, timeouts, malformed
responses, inconsistent metric names, and plugin failures are infrastructure
errors rather than mutation kills.

The suite, evaluator request, and evaluator response JSON Schemas ship in the
Python package. The complete offline example is `examples/order_agent_suite.json` with
`examples/json_evaluator.py`.

### Custom mutations and CI output

Trusted custom mutation operators can be exported by a DeepEval suite or loaded
from a Python file, module attribute, or installed `mendmark.mutations` entry
point. Mendmark validates operator metadata and stable, unique mutation IDs.

Audits can emit JUnit XML and SARIF 2.1 in addition to the canonical JSON report.
`--changed-tools-only` evaluates only cases associated with added or changed tool
digests while retaining suite-wide tool coverage and contract checks. A scheduled
full audit remains necessary for changes unrelated to tool declarations.

Reports record the Mendmark version, adapter, canonical policy digest, optional
suite/policy versions, and source/CI identity. `--maximum-mutants` stops before
evaluator work when a configured cost ceiling is exceeded. Reports and baselines
can be signed and verified with Sigstore Cosign bundles and exact keys or OIDC
identities; Mendmark does not implement custom cryptography.

### Existing ML integrity pack

Mendmark began as a benchmark for coding agents repairing broken ML pipelines.
That pack remains available through:

- `mendmark prepare`
- `mendmark grade`
- `mendmark show`
- `MendmarkIntegrityMetric`

It contains five failure tasks covering leakage, metric aggregation,
reproducibility, temporal leakage, and train-serve skew. Treat it as a
specialized integrity pack inside the broader Mendmark product. Do not delete it
while developing the general agent-eval system. Release wheels install the pack
under `share/mendmark/tasks`; the CLI falls back there when no local `tasks/`
directory exists.

## Quick verification

Run from the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[deepeval,dev]'
python -m pytest

mendmark audit examples/order_agent_suite.py \
  --baseline examples/order_agent_baseline.json \
  --output /tmp/mendmark-report.json
```

Expected current result:

```text
37 passed

Mendmark agent-eval audit
Cases: 1
Mutations: 13  Killed: 13  Survived: 0  Errors: 0
Mutation kill rate: 100.0%
Gate: PASS
```

Also verify the framework-neutral path:

```bash
mendmark audit-json examples/order_agent_suite.json \
  --evaluator-command "python3 examples/json_evaluator.py" \
  --output /tmp/mendmark-json-report.json \
  --junit /tmp/mendmark.xml \
  --sarif /tmp/mendmark.sarif
```

Also verify the package builds:

```bash
python -m pip wheel . --no-deps --wheel-dir /tmp/mendmark-dist
```

GitHub Actions runs both the test suite and the example mutation audit.

## Important files

| Path | Purpose |
| --- | --- |
| `src/mendmark/agent_cases.py` | Framework-neutral case and tool data model |
| `src/mendmark/mutations.py` | Mutation protocol and built-in operators |
| `src/mendmark/audit.py` | Audit runner, tool checks, report, and policy gate |
| `src/mendmark/deepeval.py` | DeepEval conversion, evaluator, and suite loader |
| `src/mendmark/json_adapter.py` | Validated JSON suite and batch evaluator protocol |
| `src/mendmark/plugins.py` | Trusted custom mutation discovery and loading |
| `src/mendmark/ci_outputs.py` | JUnit and SARIF renderers |
| `src/mendmark/signatures.py` | Sigstore Cosign sign/verify integration |
| `src/mendmark/schemas/` | Versioned public JSON contracts |
| `src/mendmark/cli.py` | Audit commands, baselines, and original ML commands |
| `examples/order_agent_suite.py` | Offline working example |
| `examples/order_agent_baseline.json` | Accepted example baseline |
| `docs/agent-mutation-audits.md` | Technical explanation and interpretation |
| `docs/product.md` | Commercial thesis, product surfaces, pricing hypothesis |
| `docs/evaluation-card.md` | Original ML integrity pack limitations |
| `.github/workflows/tests.yml` | Tests and dogfooded mutation audit |
| `.github/workflows/release.yml` | Trusted TestPyPI/PyPI publishing and verification |

## Report data boundary

The JSON report contains:

- Case IDs
- Mutation IDs, operators, categories, descriptions, and severity
- Mutation status and the metrics that killed it
- Tool names and schema digests
- Contract issue locations without values
- Aggregate counts, kill rates, regressions, and gate failures
- Runner, adapter, policy, source, suite, and CI provenance

The report does not contain:

- Prompts
- Expected or actual answers
- Tool arguments
- Tool outputs
- Customer conversation content

Suite inputs and evaluator processes do contain case content. Python suites,
plugins, and evaluator commands are trusted local code. Run them only inside a
trusted environment; Mendmark is not a sandbox for hostile code.

## Claims that are supportable

These statements are accurate:

- Mendmark is an open-source mutation-testing tool for agent eval suites.
- It plants controlled faults in tool traces and final responses.
- It measures whether existing evaluators catch those faults.
- It reports per-tool mutation coverage and evaluator regressions.
- It detects added, removed, changed, untested, and contract-invalid tools.
- Its current report excludes prompts, tool arguments, and tool outputs.
- It integrates with DeepEval and has a framework-neutral core.
- It accepts framework-neutral JSON traces and any local JSON evaluator command.
- It supports validated custom mutations, JUnit, SARIF, and changed-tool audits.
- It supports mutation cost ceilings and Sigstore-backed artifact signatures.
- Its included offline example catches 13 of 13 generated faults.
- The test suite currently contains 37 passing tests.
- Version 0.4.0 is published to PyPI through a protected Trusted Publishing
  workflow with PyPI-hosted provenance attestations.
- Future releases require a signed tag from the repository's approved SSH
  signing identity before any package build or publication job runs.

## Claims that are not yet supportable

Do not claim any of the following:

- That Mendmark proves an agent is safe or correct.
- That the mutation kill rate is agent accuracy.
- That Mendmark covers every possible agent failure.
- That it already integrates with LangSmith, Phoenix, Braintrust, OpenTelemetry,
  or the OpenAI Agents SDK.
- That a hosted dashboard, team service, VPC runner, SSO, or key-management
  service exists.
- That external companies use it in production.
- That it has paying customers or validated pricing.

A passing audit proves only that the configured evaluators caught the generated
faults that were applicable to the supplied cases.

## Product positioning

Use plain language:

> Agent teams write evals to catch failures. Mendmark checks whether those evals
> work. It changes one tool call or response at a time, reruns the same tests,
> and shows the failures that still pass.

Avoid vague phrases such as:

- Eval infrastructure
- Evaluation design
- Trust layer
- Comprehensive agent safety
- Production-grade evaluation platform

Concrete examples are stronger:

- The refund tool receives the wrong amount.
- A payment call runs twice.
- A required lookup disappears.
- An API returns an error and the agent still claims success.
- A new tool launches without a case that exercises it.

## Resume and interview positioning

Current résumé title:

> Mendmark | Mutation Testing for Agent Evals

Current résumé bullets:

> Built an open-source Python tool that plants controlled failures in passing
> agent traces, reruns a team's existing evaluators through DeepEval or a JSON
> protocol, and fails CI when those evals miss wrong tool arguments, repeated
> side effects, hidden tool errors, or damaged responses.

> Added custom domain mutations, per-tool coverage, tool-schema and contract
> checks, privacy-safe JSON/JUnit/SARIF reports, and regression gates that show
> when an evaluator stops catching a fault it caught before.

The strongest interview demo is:

1. Show the passing refund-agent case.
2. Show the two declared tools and mark `refund_order` as side effecting.
3. Run `mendmark audit`.
4. Explain one mutation in plain language, such as a duplicated refund.
5. Weaken the tool evaluator deliberately.
6. Run again and show the survivor and failed gate.
7. Restore the evaluator and show the regression resolved.

## Recommended next milestone

The prior P0 JSON adapter and plugin API, plus the P1 JUnit/SARIF and changed-tool
mode, are implemented in 0.4. Choose the next integration from real-team usage
rather than adding adapters speculatively.

### P0: Execute design-partner pilots

- Run five to ten real suites through the JSON boundary and measure audit time,
  mutation usefulness, evaluator cost, and report size.
- Use `docs/pilot-guide.md` and the pilot issue form to recruit and onboard teams.
- Use the included benchmark and `--maximum-mutants` to establish cost ceilings.
- Add bounded parallel evaluation only if pilot data shows evaluator execution,
  rather than model calls, is a material bottleneck.

### P1: More framework adapters

Choose the next adapter only after customer interviews. Likely candidates are
OpenTelemetry traces, LangSmith, Phoenix, Braintrust, or the OpenAI Agents SDK.
Do not build all adapters speculatively.

### P2: Hosted control plane

Validate demand before building it. The proposed service would ingest only the
privacy-safe report by default and show:

- History by branch and release
- Critical survivors
- Tool rollout status
- Evaluator regressions
- Owners and accepted exceptions
- Pull-request status

The current pricing in `docs/product.md` is a hypothesis, not validated pricing.

## Product validation plan

The best next evidence is a real team running Mendmark against a real eval
suite. Recruit five to ten teams shipping tool-using agents and ask:

1. What agent failure cost the team the most time or trust?
2. Which tool launches create the most release anxiety?
3. How does the team decide that an evaluator is good enough?
4. Would a surviving critical mutation block deployment?
5. Which trace and eval system already holds the source data?
6. Can report metadata leave the team's environment?
7. Who owns this problem and which budget would pay for it?

The strongest validation event is not praise. It is a team discovering a
survivor, improving an evaluator, and adding Mendmark to CI.

## Development guardrails

- Keep the framework-neutral core separate from adapters.
- Keep the default report free of case content and tool payloads.
- Never count evaluator errors as successful mutation kills.
- Keep mutation IDs stable across runs.
- Require original cases to pass before interpreting mutation results.
- Do not overwrite an accepted baseline after a failed gate.
- Add tests for every new mutation and report field.
- Keep the sample audit deterministic, offline, and free of API keys.
- Preserve backward compatibility for the existing ML integrity commands.
- Update the README, handoff, and case study when a claimed feature actually
  ships.

## Working style for the next agent

1. Inspect the current code and run the verification commands before editing.
2. Create a small plan tied to the recommended milestone.
3. Keep each feature usable from the CLI, covered by tests, and documented.
4. Test in an environment with model-provider API keys unset.
5. Build the wheel before publishing.
6. Push only after local tests and the example audit pass.
7. Wait for GitHub Actions and fix clean-environment failures before handoff.

## Copyable prompt for the next agent

```text
You are taking over development of Mendmark at
/home/danny/Projects/mendmark.

Read HANDOFF.md, README.md, docs/agent-mutation-audits.md, and
docs/product.md completely before making changes. Then inspect the source and
run the verification commands in HANDOFF.md.

Mendmark mutation-tests agent eval suites. It plants controlled faults in
passing tool traces and responses, reruns the team's evaluators, and reports
which faults survive. The current stable release is a local Python engine
published to PyPI with DeepEval and framework-neutral JSON adapters, custom
mutation plugins, JUnit/SARIF output, and changed-tool audits. Do not claim that
hosted or other framework roadmap features already exist.

Your next objective is to implement the highest-priority unfinished milestone
from HANDOFF.md. Preserve the privacy-safe report boundary, stable mutation IDs,
offline example, baseline regression behavior, and original ML integrity pack.
Keep the product language simple and concrete. Add tests and documentation,
build the wheel, run the complete offline audit, and wait for GitHub Actions
before declaring the work complete.
```
