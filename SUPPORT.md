# Support policy

Mendmark is currently a community-supported open-source project. Public support
is provided on a best-effort basis and does not include an uptime, response, or
remediation SLA.

## Where to ask

- Use a GitHub issue for reproducible bugs, compatibility questions, and focused
  feature requests.
- Use the pilot request form when evaluating Mendmark against a real agent suite.
- Use GitHub private vulnerability reporting for suspected security issues, as
  described in [`SECURITY.md`](SECURITY.md).

Search existing issues before opening a new one. Include the Mendmark version,
Python version, operating system, command, exit code, and a minimal sanitized
reproduction. Never include credentials, prompts, traces, expected or actual
answers, tool arguments, tool outputs, or customer data.

## Response targets

Ordinary issues are targeted for initial triage within five business days.
Security reports follow the targets in `SECURITY.md`. Targets are not guarantees
and may change with maintainer availability.

## Supported surface

- The latest Mendmark minor release receives bug and security fixes.
- Python and platform support follows [`docs/compatibility.md`](docs/compatibility.md).
- The documented CLI, versioned JSON Schemas, JSON evaluator protocol, and
  built-in mutation IDs follow the compatibility policy.
- Python suites, plugins, and evaluator commands are trusted customer code.
  Debugging that code is outside the default support boundary unless the problem
  reproduces against a documented Mendmark interface.

Feature requests are prioritized from repeated real-suite evidence. A requested
framework adapter, hosted feature, or enterprise control should not be treated
as committed until it appears in a published release.

## Enterprise status

Mendmark does not currently offer a paid support contract, hosted service, or
enterprise SLA. Teams may run the open-source engine inside their own CI or VPC.
The security model and deployment checklist are documented in
[`docs/threat-model.md`](docs/threat-model.md).
