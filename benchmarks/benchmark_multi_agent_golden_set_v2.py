"""Run and verify the Mendmark Multi-Agent Golden Set v2."""

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
from mendmark.mutations import generate_mutants


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_ROOT = PROJECT_ROOT / "golden" / "multi-agent-v2"


class GoldenSetError(RuntimeError):
    """Raised when measured behavior differs from the golden contract."""


def _expect(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise GoldenSetError(f"{label}: expected {expected!r}, got {actual!r}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _operator_statuses(report: dict[str, object]) -> dict[str, dict[str, int]]:
    return {
        operator: {
            field: coverage[field]
            for field in ("killed", "survived", "errors")
            if coverage[field]
        }
        for operator, coverage in report["coverage"]["by_operator"].items()
    }


def main() -> int:
    try:
        manifest = json.loads(
            (GOLDEN_ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        asset_paths = {
            "suite.json": GOLDEN_ROOT / "suite.json",
            "evaluator.py": GOLDEN_ROOT / "evaluator.py",
            "weak_evaluator.py": GOLDEN_ROOT / "weak_evaluator.py",
            "README.md": GOLDEN_ROOT / "README.md",
            "suite-v2.schema.json": (
                PROJECT_ROOT / "src/mendmark/schemas/suite-v2.schema.json"
            ),
            "report-v1.schema.json": (
                PROJECT_ROOT / "src/mendmark/schemas/report-v1.schema.json"
            ),
        }
        for name, expected_digest in manifest["assets"].items():
            _expect(f"{name} SHA-256", _sha256(asset_paths[name]), expected_digest)

        suite = load_json_suite(GOLDEN_ROOT / "suite.json")
        mutants = generate_mutants(suite.cases, suite.tools)
        side_effecting = {tool.name for tool in suite.tools if tool.side_effecting}
        contents = {
            "cases": len(suite.cases),
            "agents": len({
                agent.agent_id for case in suite.cases for agent in case.agents
            }),
            "agent_declarations": sum(len(case.agents) for case in suite.cases),
            "tools": len(suite.tools),
            "events": sum(len(case.events) for case in suite.cases),
            "tool_calls": sum(len(case.actual_tool_calls()) for case in suite.cases),
            "side_effecting_calls": sum(
                call.name in side_effecting
                for case in suite.cases
                for call in case.actual_tool_calls()
            ),
            "mutations": len(mutants),
        }
        _expect("contents", contents, manifest["contents"])
        _expect(
            "operator counts",
            dict(sorted(Counter(mutant.operator for mutant in mutants).items())),
            manifest["operator_counts"],
        )
        mutation_digest = hashlib.sha256(
            "\n".join(sorted(mutant.mutant_id for mutant in mutants)).encode()
        ).hexdigest()
        _expect("mutation ID digest", mutation_digest, manifest["mutation_id_digest"])

        measured_profiles = {}
        with tempfile.TemporaryDirectory(prefix="mendmark-multi-v2-") as raw_temp:
            temp = Path(raw_temp)
            original_document = json.loads(
                (GOLDEN_ROOT / "suite.json").read_text(encoding="utf-8")
            )
            for profile_name, expected in manifest["profiles"].items():
                suite_path = GOLDEN_ROOT / "suite.json"
                if expected["reverse_events"]:
                    document = json.loads(json.dumps(original_document))
                    for case in document["cases"]:
                        case["events"].reverse()
                    suite_path = temp / f"{profile_name}-suite.json"
                    suite_path.write_text(json.dumps(document), encoding="utf-8")
                report_path = temp / f"{profile_name}-report.json"
                evaluator_path = GOLDEN_ROOT / expected["evaluator"]
                completed = subprocess.run(
                    [
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
                    ],
                    cwd=PROJECT_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                _expect(
                    f"{profile_name} exit code",
                    completed.returncode,
                    expected["expected_exit_code"],
                )
                report = json.loads(report_path.read_text(encoding="utf-8"))
                _expect(
                    f"{profile_name} summary",
                    report["summary"],
                    expected["expected_summary"],
                )
                _expect(
                    f"{profile_name} gate",
                    report["gate"]["passed"],
                    expected["expected_gate_passed"],
                )
                _expect(
                    f"{profile_name} operator status digest",
                    _json_digest(_operator_statuses(report)),
                    expected["operator_status_digest"],
                )
                _expect(
                    f"{profile_name} category coverage digest",
                    _json_digest(report["coverage"]["by_category"]),
                    expected["category_coverage_digest"],
                )
                measured_profiles[profile_name] = {
                    "gate_passed": report["gate"]["passed"],
                    "summary": report["summary"],
                }

        result = {
            "dataset": manifest["name"],
            "dataset_version": manifest["version"],
            "contents": contents,
            "profiles": dict(sorted(measured_profiles.items())),
            "contract_passed": True,
        }
        checked_in = json.loads(
            (GOLDEN_ROOT / "results.json").read_text(encoding="utf-8")
        )
        _expect("checked-in results", result, checked_in)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GoldenSetError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"multi-agent golden set v2: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
