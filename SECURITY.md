# Security policy

## Supported versions

Security fixes are provided for the latest minor release. Users should upgrade
to the newest available Mendmark version before reporting an issue.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include customer
traces, prompts, tool payloads, credentials, or evaluator output in a report.
Use GitHub's private vulnerability reporting feature for this repository.

Include the Mendmark version, operating system, affected command, minimal
sanitized reproduction, and expected impact. Receipt should be acknowledged
within three business days. No bounty or fixed remediation timeline is promised.

## Trust boundary

Python suites, custom mutation plugins, and evaluator commands are trusted code
and execute with the permissions of the Mendmark process. Mendmark does not
sandbox them. JSON reports, JUnit, and SARIF exclude case content by design, but
the local suite and evaluator necessarily process that content.

Signature verification proves that Cosign accepted a bundle for an exact key or
OIDC identity. It does not prove that an eval suite, policy, or agent is safe.
