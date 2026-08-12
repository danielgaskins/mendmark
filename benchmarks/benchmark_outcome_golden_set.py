#!/usr/bin/env python3
"""Verify the Enterprise Outcome Golden Set contract offline."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mendmark.enterprise_demo import run_enterprise_demo  # noqa: E402


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = PROJECT_ROOT / "golden" / "outcome-v1"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    expected = json.loads((root / "results.json").read_text(encoding="utf-8"))["profiles"]
    if _digest(root / "suite.json") != manifest["suite_sha256"]:
        print("outcome golden set: suite digest mismatch", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as directory:
        result = run_enterprise_demo(Path(directory))
    observed = {}
    for source, target in (("state_only", "state-only"), ("protected", "outcome-contract")):
        report = result[source]
        observed[target] = {
            "status": report["business_assurance"]["status"],
            **{key: report["summary"][key] for key in ("cases", "mutants", "killed", "survived", "kill_rate")},
            "affected_workflows": report["business_assurance"]["affected_workflows"],
            "estimated_exposure_usd": report["business_assurance"]["estimated_exposure_usd"],
        }
    if observed != expected:
        print(f"outcome golden set: expected {expected!r}, got {observed!r}", file=sys.stderr)
        return 1
    print("outcome golden set: PASS (state-only 12/24; outcome-contract 24/24)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
