# Changelog

All notable changes to Mendmark are documented here. The project follows
Semantic Versioning for its Python and JSON contracts.

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
