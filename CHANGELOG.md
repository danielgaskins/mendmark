# Changelog

All notable changes to Mendmark are documented here. The project follows
Semantic Versioning for its Python and JSON contracts.

## Unreleased

### Added

- A deliberately weak refund-agent suite that demonstrates how an evaluator can
  accept the correct final response while missing broken tool behavior.
- A regression test proving that the weak example exposes surviving critical
  mutations before the complete example kills them.

### Fixed

- Python suites can import helper modules stored beside the suite file, matching
  normal script behavior when an audit is launched from another directory.

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
