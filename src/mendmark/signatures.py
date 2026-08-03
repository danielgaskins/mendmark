"""Cosign-backed signatures for reports, baselines, and other artifacts."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class SignatureError(ValueError):
    """Raised when Cosign cannot sign or verify an artifact."""


def _cosign() -> str:
    executable = shutil.which("cosign")
    if executable is None:
        raise SignatureError(
            "cosign is required for signatures; install it from "
            "https://docs.sigstore.dev/cosign/system_config/installation/"
        )
    return executable


def sign_blob(
    artifact: str | Path,
    bundle: str | Path,
    *,
    key: str | None = None,
) -> None:
    """Sign an artifact using keyless identity or a Cosign-supported key URI."""
    source = Path(artifact).expanduser().resolve()
    if not source.is_file():
        raise SignatureError(f"artifact does not exist: {source}")
    destination = Path(bundle).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [_cosign(), "sign-blob", "--yes", "--bundle", str(destination)]
    if key:
        command.extend(("--key", key))
    command.append(str(source))
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SignatureError(
            f"cosign sign-blob exited with status {completed.returncode}"
        )


def verify_blob(
    artifact: str | Path,
    bundle: str | Path,
    *,
    key: str | None = None,
    certificate_identity: str | None = None,
    certificate_oidc_issuer: str | None = None,
) -> None:
    """Verify a Cosign bundle against a key or an exact signer identity."""
    source = Path(artifact).expanduser().resolve()
    signature = Path(bundle).expanduser().resolve()
    if not source.is_file():
        raise SignatureError(f"artifact does not exist: {source}")
    if not signature.is_file():
        raise SignatureError(f"signature bundle does not exist: {signature}")
    if key:
        if certificate_identity or certificate_oidc_issuer:
            raise SignatureError(
                "use either --key or certificate identity options, not both"
            )
    elif not certificate_identity or not certificate_oidc_issuer:
        raise SignatureError(
            "keyless verification requires --certificate-identity and "
            "--certificate-oidc-issuer"
        )
    command = [_cosign(), "verify-blob", str(source), "--bundle", str(signature)]
    if key:
        command.extend(("--key", key))
    else:
        command.extend(
            (
                "--certificate-identity",
                str(certificate_identity),
                "--certificate-oidc-issuer",
                str(certificate_oidc_issuer),
            )
        )
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SignatureError(
            f"cosign verify-blob exited with status {completed.returncode}"
        )
