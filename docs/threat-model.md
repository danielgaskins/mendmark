# Threat model and data flow

This document describes Mendmark 0.4 as a local CLI and Python package. It does
not describe a hosted control plane, because none exists in the current product.

## Security objectives

Mendmark aims to:

- Keep prompts, answers, tool arguments, and tool outputs out of its reports.
- Make evaluator failures visible rather than counting them as successful kills.
- Prevent a failed audit from replacing an accepted baseline.
- Make released packages traceable to a verified repository release workflow.
- Give operators explicit limits for evaluator time and mutation cost.

Mendmark does not aim to sandbox untrusted code, prove an agent safe, prevent a
trusted evaluator from leaking data, or replace an organization's endpoint,
network, identity, and secrets controls.

## Data flow

```text
Customer trust boundary

suite / JSON cases ----> Mendmark mutation engine ----> trusted evaluator
  prompts and traces         in-memory copies             case content
        |                          |                           |
        |                          +---- statuses only <-------+
        |                                      |
        +------------------------------> privacy-safe report
                                               |
                                  optional CI artifacts or
                                  customer-controlled storage
```

Mendmark processes case content locally. Its report serializers retain IDs,
operator and metric names, tool names and schema digests, statuses, aggregate
counts, policy results, and source/CI provenance. They omit prompts, expected and
actual answers, tool arguments, and tool outputs.

Identifiers, tool names, metric names, mutation descriptions, source metadata,
and custom operator metadata are not secret fields. Customers must avoid placing
sensitive values in them. Hashes are integrity and change-detection values, not
encryption or anonymization.

## Trust zones

| Component | Treatment | Important consequence |
| --- | --- | --- |
| Mendmark package and built-in operators | Product code | Install from a verified distribution and keep it updated. |
| Python suites and DeepEval metrics | Trusted customer code | They run in the Mendmark process with its full permissions. |
| Custom mutation plugins | Trusted customer code | They can read inputs, environment variables, files, and network resources available to the process. |
| JSON evaluator command | Trusted customer executable | It receives case content and inherits the configured process environment and operating-system permissions. |
| Reports, JUnit, SARIF, and baselines | Privacy-reduced metadata | They exclude designated case-content fields but may still reveal business identifiers and tool names. |
| CI logs and third-party actions | Separate operational boundary | Customer code can write sensitive content to logs even when Mendmark's own report does not. |

## Threats, controls, and residual risk

| Threat | Existing controls | Residual risk and operator action |
| --- | --- | --- |
| A malicious suite, plugin, or evaluator executes arbitrary code | Executable integrations are explicitly documented as trusted code. | Mendmark is not a sandbox. Review code and run it in an isolated, least-privilege job without unnecessary secrets or network access. |
| Case content leaks through Mendmark output | Report, JUnit, SARIF, error, and console privacy-canary tests; schemas exclude case-content fields. | Trusted integrations may log or transmit content themselves. Sanitize identifiers and inspect logs before exporting them. |
| A report or baseline is altered | Strict schema validation; optional Cosign signing and exact-identity verification; failed gates cannot overwrite accepted baselines. | Unsigned artifacts have no cryptographic origin guarantee. Require signature verification in the consuming workflow. |
| Dependency or release compromise | Zero mandatory runtime dependencies; signed commits and tags; immutable releases; Trusted Publishing provenance; pinned Actions; dependency review, vulnerability audit, and SBOM automation. | Optional adapters have transitive dependencies and upstream risk. Apply organizational allowlists and scan the exact deployed environment. |
| Excessive evaluator cost or runtime | `--maximum-mutants`, evaluator timeout controls, and changed-tool-only audits. | A permitted evaluator can still consume resources or call paid services. Enforce process, network, and provider-side budgets outside Mendmark. |
| Crafted input exhausts memory or produces an oversized report | Strict JSON validation and an explicit pre-evaluation mutation ceiling. | No hard input-byte or report-size limit is currently claimed. Bound source artifact size and job resources at the CI/container layer. |
| Tool schema digests reveal sensitive data | Reports store digests rather than schemas or argument values. | Low-entropy or known schemas may be guessable; a digest is not a secrecy mechanism. Do not place secrets in schemas or descriptions. |
| Results are interpreted as proof of agent safety | Documentation and CLI language distinguish mutation detection from agent correctness. | Users may still overgeneralize. Review applicable operators, survivors, evaluator errors, and untested failure classes before release decisions. |

## Recommended enterprise deployment

1. Pin an exact Mendmark version and verify the PyPI provenance attestation.
2. Run the audit in an ephemeral CI job or container with a read-only source
   checkout where practical.
3. Provide only the secrets and outbound network access required by the trusted
   evaluator. Do not expose deployment or production credentials.
4. Set evaluator timeout, mutation budget, process memory/CPU limits, and
   provider-side spend limits.
5. Store raw suites and traces under the customer's existing data controls.
6. Export only reviewed Mendmark reports; sanitize case IDs, tool names, metric
   names, custom metadata, and source metadata when necessary.
7. Sign accepted baselines and reports, verify the expected key or OIDC identity
   before comparison, and restrict who can update baselines.
8. Retain audit artifacts and CI logs according to the customer's policy.
9. Schedule full audits in addition to changed-tool pull-request audits.

## Validation and review

The privacy boundary is exercised by `tests/test_user_assurance.py`. Distribution
CI builds the wheel, installs it outside the repository, validates the packaged
schemas and tasks, and runs the complete offline JSON audit. Security automation
audits the resolved optional integration environment and emits a validated,
reproducible CycloneDX SBOM.

Review this threat model when a new adapter, data field, external service,
credential flow, persistence layer, or execution mode is introduced.
