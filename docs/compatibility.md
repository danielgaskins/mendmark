# Compatibility policy

Mendmark 0.x is evolving, but automation still needs predictable contracts.

- Python 3.10 through 3.13 on Linux are supported. CI tests every supported
  version. macOS and Windows are not yet claimed as supported platforms; their
  evaluator command parsing must be validated before making that claim.
- Patch releases preserve CLI flags, report fields, JSON protocol fields, and
  mutation IDs except where a security defect makes that unsafe.
- Minor releases may add optional object fields. Consumers must ignore unknown
  fields and select behavior using `schema_version`, not the package version.
- JSON suite and evaluator protocol `1.0` remain the stable flat-trace contract.
  Native event graphs use `2.0`; Mendmark chooses the evaluator protocol from
  the case type and never sends `2.0` fields to a `1.0` single-agent audit.
- Removing or changing a field, status, mutation ID, or plugin requirement needs
  a new schema or protocol version and migration notes.
- Built-in mutation IDs remain `<case_id>:<operator_name>:<stable_suffix>`.
- Historical benchmarks select immutable `agent-eval-v1` or `multi-agent-v1`
  mutation profiles. Ordinary audits use `current`; adding a new operator never
  rewrites an older golden-set contract.
- A custom operator name is globally unique within an audit and is part of the
  customer's accepted baseline contract.
- `audit`, `audit-json`, `prepare`, `grade`, and `show` exit with 0 for success,
  1 for a failed product gate, and 2 for invalid input or infrastructure failure.

The JSON Schemas under `mendmark/schemas` are the machine-readable contract.
Python suites and plugins are trusted-code APIs and receive deprecation notes at
least one minor release before removal when security permits.
