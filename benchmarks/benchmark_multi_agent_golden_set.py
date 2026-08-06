"""Run and verify the Mendmark Multi-Agent Golden Set."""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from mendmark.json_adapter import load_json_suite
from mendmark.mutations import MULTI_AGENT_V1_MUTATIONS, generate_mutants


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_ROOT = PROJECT_ROOT / "golden" / "multi-agent-v1"


class GoldenSetError(RuntimeError):
    """Raised when measured behavior differs from the golden contract."""


def _expect(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise GoldenSetError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> int:
    try:
        manifest = json.loads((GOLDEN_ROOT / "manifest.json").read_text())
        suite_path = (GOLDEN_ROOT / manifest["suite"]).resolve()
        evaluator_path = (GOLDEN_ROOT / manifest["evaluator"]).resolve()
        _expect(
            "suite SHA-256",
            hashlib.sha256(suite_path.read_bytes()).hexdigest(),
            manifest["suite_sha256"],
        )
        asset_paths = {
            "evaluator.py": evaluator_path,
            "README.md": GOLDEN_ROOT / "README.md",
            "suite-v2.schema.json": (
                PROJECT_ROOT / "src/mendmark/schemas/suite-v2.schema.json"
            ),
            "report-v1.schema.json": (
                PROJECT_ROOT / "src/mendmark/schemas/report-v1.schema.json"
            ),
        }
        for name, expected_digest in manifest["assets"].items():
            _expect(
                f"{name} SHA-256",
                hashlib.sha256(asset_paths[name].read_bytes()).hexdigest(),
                expected_digest,
            )
        suite = load_json_suite(suite_path)
        mutants = generate_mutants(
            suite.cases, suite.tools, MULTI_AGENT_V1_MUTATIONS
        )
        mutation_digest = hashlib.sha256(
            "\n".join(sorted(mutant.mutant_id for mutant in mutants)).encode()
        ).hexdigest()
        contents = {
            "cases": len(suite.cases),
            "agents": len({
                agent.agent_id for case in suite.cases for agent in case.agents
            }),
            "tools": len(suite.tools),
            "events": sum(len(case.events) for case in suite.cases),
            "tool_calls": sum(
                len(case.actual_tool_calls()) for case in suite.cases
            ),
            "mutations": len(mutants),
        }
        _expect("contents", contents, manifest["contents"])
        _expect("mutation ID digest", mutation_digest, manifest["mutation_id_digest"])
        _expect(
            "operator counts",
            dict(sorted(Counter(mutant.operator for mutant in mutants).items())),
            manifest["operator_counts"],
        )

        with tempfile.TemporaryDirectory(prefix="mendmark-multi-golden-") as directory:
            report_path = Path(directory) / "report.json"
            command = [
                sys.executable,
                "-m",
                "mendmark.cli",
                "audit-json",
                str(suite_path),
                "--evaluator-command",
                shlex.join([sys.executable, str(evaluator_path)]),
                "--output",
                str(report_path),
                "--suite-version",
                manifest["version"],
                "--mutation-profile",
                "multi-agent-v1",
            ]
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            _expect("exit code", completed.returncode, 0)
            report = json.loads(report_path.read_text())
        _expect("summary", report["summary"], manifest["expected_summary"])
        _expect("gate", report["gate"]["passed"], manifest["expected_gate_passed"])
        result = {
            "dataset": manifest["name"],
            "dataset_version": manifest["version"],
            **contents,
            "summary": report["summary"],
            "gate_passed": report["gate"]["passed"],
            "contract_passed": True,
        }
        _expect(
            "checked-in results",
            result,
            json.loads((GOLDEN_ROOT / "results.json").read_text()),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GoldenSetError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"multi-agent golden set: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
