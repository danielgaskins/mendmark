# Signing reports and baselines

Mendmark delegates cryptography and identity verification to Sigstore Cosign.
It does not define a custom signature format.

Sign with an interactive or ambient OIDC identity:

```bash
mendmark sign mendmark-report.json \
  --bundle mendmark-report.sigstore.json
```

In CI, install Cosign and provide `id-token: write`. Verify against the exact
workflow identity and issuer:

```bash
mendmark verify-signature mendmark-report.json \
  --bundle mendmark-report.sigstore.json \
  --certificate-identity \
    "https://github.com/ORG/REPO/.github/workflows/evals.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

Customer-managed keys and KMS URIs supported by Cosign can be passed with
`--key`. Keep the artifact and `.sigstore.json` bundle together. Verification
must pin an exact expected key or identity; wildcard identities are not exposed
by Mendmark's CLI.

Signing proves artifact integrity and signer identity. It does not prove that
the configured evaluator, policy, or agent is correct or safe.
