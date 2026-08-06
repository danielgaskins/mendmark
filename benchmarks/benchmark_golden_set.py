"""Run and verify the Mendmark Agent Eval Golden Set."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

from mendmark import __version__
from mendmark.json_adapter import load_json_suite
from mendmark.mutations import AGENT_EVAL_V1_MUTATIONS, generate_mutants


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN_ROOT = PROJECT_ROOT / "golden" / "agent-eval-v1"


class GoldenSetError(RuntimeError):
    """Raised when a measured result differs from the golden contract."""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mutation_digest(mutant_ids: list[str]) -> str:
    value = "\n".join(sorted(mutant_ids)).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _operator_statuses(report: dict[str, object]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for mutation in report["mutations"]:
        counts[mutation["operator"]][mutation["status"]] += 1
    return {
        operator: dict(sorted(statuses.items()))
        for operator, statuses in sorted(counts.items())
    }


def _expect(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise GoldenSetError(f"{label}: expected {expected!r}, got {actual!r}")


def run_golden_set(
    golden_root: Path = DEFAULT_GOLDEN_ROOT, *, repeats: int = 1
) -> dict[str, object]:
    if repeats < 1:
        raise GoldenSetError("repeats must be at least 1")
    manifest_path = golden_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    suite_path = golden_root / manifest["suite"]
    _expect("suite SHA-256", _digest(suite_path), manifest["suite_sha256"])
    asset_paths = {
        "evaluator.py": golden_root / "evaluator.py",
        "README.md": golden_root / "README.md",
        "suite-v1.schema.json": (
            PROJECT_ROOT / "src/mendmark/schemas/suite-v1.schema.json"
        ),
        "report-v1.schema.json": (
            PROJECT_ROOT / "src/mendmark/schemas/report-v1.schema.json"
        ),
    }
    for name, expected_digest in manifest["assets"].items():
        _expect(f"{name} SHA-256", _digest(asset_paths[name]), expected_digest)

    suite = load_json_suite(suite_path)
    mutants = generate_mutants(
        suite.cases, suite.tools, AGENT_EVAL_V1_MUTATIONS
    )
    _expect("case count", len(suite.cases), manifest["contents"]["cases"])
    _expect("tool count", len(suite.tools), manifest["contents"]["tools"])
    _expect("mutation count", len(mutants), manifest["contents"]["mutations"])
    tool_calls = [call for case in suite.cases for call in case.tools_called]
    side_effecting = {tool.name for tool in suite.tools if tool.side_effecting}
    _expect("tool call count", len(tool_calls), manifest["contents"]["tool_calls"])
    _expect(
        "side-effecting call count",
        sum(call.name in side_effecting for call in tool_calls),
        manifest["contents"]["side_effecting_calls"],
    )
    _expect(
        "domains",
        sorted({str(case.metadata["domain"]) for case in suite.cases}),
        manifest["contents"]["domains"],
    )
    _expect(
        "patterns",
        sorted({str(case.metadata["pattern"]) for case in suite.cases}),
        manifest["contents"]["patterns"],
    )
    _expect(
        "mutation ID digest",
        _mutation_digest([mutant.mutant_id for mutant in mutants]),
        manifest["mutation_id_digest"],
    )
    _expect(
        "operator counts",
        dict(sorted(Counter(mutant.operator for mutant in mutants).items())),
        manifest["operator_counts"],
    )

    measured_profiles: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="mendmark-golden-") as directory:
        output_root = Path(directory)
        for profile, expected in manifest["profiles"].items():
            evaluator_command = shlex.join(
                [sys.executable, str(golden_root / "evaluator.py"), "--profile", profile]
            )
            durations: list[float] = []
            report: dict[str, object] = {}
            statuses: dict[str, dict[str, int]] = {}
            for repeat in range(repeats):
                report_path = output_root / f"{profile}-{repeat}.json"
                command = [
                    sys.executable,
                    "-m",
                    "mendmark.cli",
                    "audit-json",
                    str(suite_path),
                    "--evaluator-command",
                    evaluator_command,
                    "--output",
                    str(report_path),
                    "--suite-version",
                    manifest["version"],
                    "--mutation-profile",
                    "agent-eval-v1",
                ]
                started = time.perf_counter()
                completed = subprocess.run(
                    command,
                    cwd=PROJECT_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                durations.append(time.perf_counter() - started)
                _expect(
                    f"{profile} exit code",
                    completed.returncode,
                    expected["expected_exit_code"],
                )
                if not report_path.exists():
                    raise GoldenSetError(
                        f"{profile} produced no report; "
                        f"stderr={completed.stderr.strip()!r}"
                    )
                report = json.loads(report_path.read_text(encoding="utf-8"))
                _expect(
                    f"{profile} summary",
                    report["summary"],
                    expected["expected_summary"],
                )
                _expect(
                    f"{profile} gate",
                    report["gate"]["passed"],
                    expected["expected_gate_passed"],
                )
                statuses = _operator_statuses(report)
                _expect(
                    f"{profile} operator statuses",
                    statuses,
                    expected["operator_statuses"],
                )
            measured_profiles[profile] = {
                "performance": {
                    "runs": repeats,
                    "median_seconds": round(statistics.median(durations), 6),
                    "minimum_seconds": round(min(durations), 6),
                    "maximum_seconds": round(max(durations), 6),
                },
                "summary": report["summary"],
                "gate_passed": report["gate"]["passed"],
                "operator_statuses": statuses,
            }

    checked_in = json.loads(
        (golden_root / "results.json").read_text(encoding="utf-8")
    )
    for profile, measured in measured_profiles.items():
        _expect(
            f"{profile} checked-in summary",
            measured["summary"],
            checked_in["profiles"][profile]["summary"],
        )
        _expect(
            f"{profile} checked-in gate",
            measured["gate_passed"],
            checked_in["profiles"][profile]["gate_passed"],
        )
        _expect(
            f"{profile} checked-in operator statuses",
            measured["operator_statuses"],
            checked_in["profiles"][profile]["operator_statuses"],
        )

    return {
        "dataset": manifest["name"],
        "dataset_version": manifest["version"],
        "mendmark_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cases": len(suite.cases),
        "tools": len(suite.tools),
        "mutations": len(mutants),
        "profiles": measured_profiles,
        "contract_passed": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-root", type=Path, default=DEFAULT_GOLDEN_ROOT)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_golden_set(args.golden_root.resolve(), repeats=args.repeats)
    except (GoldenSetError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"golden set: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
