# Security policy

## Supported versions

Security fixes are provided for the latest minor release. Users should upgrade
to the newest available Mendmark version before reporting an issue.

The supported Python versions and operating systems are listed in
[`docs/compatibility.md`](docs/compatibility.md). Older Mendmark releases may
continue to work, but they do not receive security fixes.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include customer
traces, prompts, tool payloads, credentials, or evaluator output in a report.
Use GitHub's private vulnerability reporting feature for this repository.

Include the Mendmark version, operating system, affected command, minimal
sanitized reproduction, and expected impact. Receipt should be acknowledged
within three business days. An initial severity assessment is targeted within
seven business days, with a status update at least every fourteen business days
until resolution. These are best-effort open-source response targets, not an
SLA. No bounty or fixed remediation timeline is promised.

Please allow a reasonable remediation and release window before public
disclosure. The maintainer will coordinate disclosure timing and credit with
the reporter when practical.

## Trust boundary

Python suites, custom mutation plugins, and evaluator commands are trusted code
and execute with the permissions of the Mendmark process. Mendmark does not
sandbox them. JSON reports, JUnit, and SARIF exclude case content by design, but
the local suite and evaluator necessarily process that content.

Signature verification proves that Cosign accepted a bundle for an exact key or
OIDC identity. It does not prove that an eval suite, policy, or agent is safe.

The complete data flow, abuse cases, controls, and residual risks are documented
in [`docs/threat-model.md`](docs/threat-model.md). In particular, customer code
can print, transmit, or persist any data it can access; Mendmark's privacy-safe
report boundary does not sandbox or redact arbitrary logs produced by trusted
suite, plugin, metric, or evaluator code.

## Supply-chain controls

- Commits on `main` and release tags require the approved SSH signing identity.
- Release tags after the historical 0.4.0 exception are verified before package
  builds, and newly created GitHub releases are immutable.
- PyPI publication uses short-lived OIDC Trusted Publishing and produces PyPI
  provenance attestations for the wheel and source distribution.
- CI builds and validates a CycloneDX SBOM for the package with its optional
  integration dependencies.
- Dependabot, pull-request dependency review, and a scheduled vulnerability
  audit monitor Python and GitHub Actions dependencies.
- GitHub Actions are pinned to full commit hashes.

These controls reduce supply-chain risk; they do not make dependencies or
build infrastructure infallible. Consumers should verify provenance, apply
their own allowlists and vulnerability policy, and run Mendmark with the least
privilege needed by their evaluator.
