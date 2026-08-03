from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mendmark import signatures


def test_sign_blob_uses_cosign_bundle_and_key(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    bundle = tmp_path / "report.sigstore.json"
    commands = []
    monkeypatch.setattr(signatures, "_cosign", lambda: "/usr/bin/cosign")
    monkeypatch.setattr(
        signatures.subprocess,
        "run",
        lambda command, check: commands.append(command) or SimpleNamespace(returncode=0),
    )

    signatures.sign_blob(artifact, bundle, key="kms://release-key")

    assert commands == [[
        "/usr/bin/cosign",
        "sign-blob",
        "--yes",
        "--bundle",
        str(bundle),
        "--key",
        "kms://release-key",
        str(artifact),
    ]]


def test_keyless_verification_requires_exact_identity(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    bundle = tmp_path / "report.sigstore.json"
    artifact.write_text("{}", encoding="utf-8")
    bundle.write_text("{}", encoding="utf-8")

    with pytest.raises(signatures.SignatureError, match="requires"):
        signatures.verify_blob(artifact, bundle)
