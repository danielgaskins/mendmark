# Release process

1. Update `CHANGELOG.md`, package versions, and the handoff.
2. Run tests with provider API keys unset, both offline audits, schema tests,
   `python -m build`, and `twine check dist/*`.
3. Push the reviewed commit and wait for the `tests` workflow.
4. Configure `release.yml` as a Trusted Publisher for the `testpypi` environment.
5. Manually dispatch `release.yml`, then install the exact version from TestPyPI
   in a clean environment and run the JSON example.
6. Configure the `pypi` environment with required maintainer approval.
7. Create a signed `vX.Y.Z` GitHub release only after TestPyPI verification.
8. Wait for PyPI trusted publishing and its provenance attestation, then verify a
   clean PyPI install.

Never add a long-lived PyPI token when Trusted Publishing is available. The
release workflow grants `id-token: write` only to publishing jobs.
