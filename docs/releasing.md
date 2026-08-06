# Release process

1. Update `CHANGELOG.md` and package versions.
2. Run tests with provider API keys unset, all golden contracts, the enterprise
   benchmark, schema tests, `python -m build`, distribution assurance, dependency
   audit, and `twine check dist/*`.
3. Open a pull request and wait for every required test, golden, compatibility,
   enterprise, distribution, and dependency-review check.
4. Configure `release.yml` as a Trusted Publisher for the `testpypi` environment.
5. Manually dispatch `release.yml`, then install the exact version from TestPyPI
   in a clean environment and run the JSON example.
6. Configure the `pypi` environment with required maintainer approval.
7. Create a signed annotated tag only after TestPyPI verification:

   ```bash
   git tag -s vX.Y.Z -m "Mendmark X.Y.Z"
   git verify-tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   The release workflow rejects unsigned tags and signatures not listed in
   `.github/allowed_signers`. Create the GitHub release only after local
   verification succeeds.
8. Wait for PyPI trusted publishing and its provenance attestation, then verify a
   clean PyPI install.

`release.yml` repeats the product contracts, all golden sets, enterprise
budgets, dependency audit, build, metadata inspection, and isolated distribution
journey before its build artifact can reach either publishing job. Publication
cannot rely only on an earlier workflow result.

Never add a long-lived PyPI token when Trusted Publishing is available. The
release workflow grants `id-token: write` only to publishing jobs.

The historical `v0.4.0` tag predates the signing requirement and remains an
unsigned annotated tag. Do not force-update a published release tag to retrofit
a signature. Its PyPI wheel and source distribution have Trusted Publishing
provenance attestations. All later release tags must pass the signing gate.

GitHub requires signed commits on `main` for administrators as well as other
contributors. Force-pushes, branch deletion, and non-linear history are
disabled. Repository-level immutable releases are enabled; GitHub applies this
protection to future releases rather than retroactively changing 0.4.0.
