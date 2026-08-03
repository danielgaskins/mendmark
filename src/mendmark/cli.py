from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .audit import AuditPolicy, run_audit
from .models import SpecError, TaskSpec
from .runner import RunnerError, _write_json, grade_run, load_manifest, prepare_run


def _tasks_root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _task(tasks_root: Path, task_id: str) -> TaskSpec:
    return TaskSpec.load(tasks_root / task_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mendmark",
        description="Mutation-test agent evals and grade ML repair tasks.",
    )
    parser.add_argument("--tasks-root", default="tasks", help="task directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("tasks", help="list and validate available tasks")

    prepare = subparsers.add_parser("prepare", help="create a public agent workspace")
    prepare.add_argument("task_id")
    prepare.add_argument("--runs-root", default="runs")
    prepare.add_argument("--operator", required=True)

    grade = subparsers.add_parser("grade", help="grade an existing run")
    grade.add_argument("run_dir")
    grade.add_argument(
        "--runtime",
        choices=("bwrap", "local"),
        default="bwrap",
        help="use local only for framework development",
    )

    show = subparsers.add_parser("show", help="show a run manifest")
    show.add_argument("run_dir")

    audit = subparsers.add_parser(
        "audit", help="mutation-test a DeepEval suite"
    )
    audit.add_argument("suite", help="trusted Python suite file")
    audit.add_argument("--output", default="mendmark-report.json")
    audit.add_argument("--baseline", default=".mendmark-baseline.json")
    audit.add_argument("--write-baseline", action="store_true")
    audit.add_argument("--minimum-kill-rate", type=float, default=None)
    audit.add_argument(
        "--allow-critical-survivors", action="store_true"
    )
    audit.add_argument("--allow-untested-tools", action="store_true")
    audit.add_argument("--allow-tool-contract-issues", action="store_true")
    audit.add_argument("--allow-regressions", action="store_true")
    return parser


def _load_baseline(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {"tools": {}, "mutations": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    loaded: dict[str, dict[str, str]] = {}
    for field in ("tools", "mutations"):
        values = data.get(field, {})
        if not isinstance(values, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in values.items()
        ):
            raise RunnerError(f"invalid Mendmark {field} baseline")
        loaded[field] = values
    return loaded


def _print_audit(report: dict[str, object], output: Path) -> None:
    summary = report["summary"]
    gate = report["gate"]
    tools = report["tools"]
    print("Mendmark agent-eval audit")
    print(f"Cases: {summary['cases']}")
    print(
        f"Mutations: {summary['mutants']}  "
        f"Killed: {summary['killed']}  "
        f"Survived: {summary['survived']}  "
        f"Errors: {summary['errors']}"
    )
    print(f"Mutation kill rate: {summary['kill_rate']:.1%}")
    if tools["untested"]:
        print("Untested tools: " + ", ".join(tools["untested"]))
    if tools["added_since_baseline"]:
        print("New tools: " + ", ".join(tools["added_since_baseline"]))
    if tools["contract_issues"]:
        print(f"Tool contract issues: {len(tools['contract_issues'])}")
    regressed = report["regressions"]["regressed"]
    if regressed:
        print("Regressed mutations:")
        for mutant_id in regressed:
            print(f"  {mutant_id}")
    survived = [
        mutation
        for mutation in report["mutations"]
        if mutation["status"] == "survived"
    ]
    if survived:
        print("Surviving mutations:")
        for mutation in survived:
            print(
                f"  {mutation['severity']}: {mutation['operator']} "
                f"[{mutation['source_case_id']}]"
            )
    print("Gate: " + ("PASS" if gate["passed"] else "FAIL"))
    for failure in gate["failures"]:
        print(f"  {failure}")
    print(f"Report: {output}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    tasks_root = _tasks_root(args.tasks_root)
    try:
        if args.command == "tasks":
            for task_dir in sorted(path for path in tasks_root.iterdir() if path.is_dir()):
                task = TaskSpec.load(task_dir)
                print(
                    f"{task.task_id}\t{task.failure_class}\t"
                    f"{task.difficulty}\t{task.title}"
                )
            return 0

        if args.command == "prepare":
            task = _task(tasks_root, args.task_id)
            run_dir = prepare_run(
                task,
                Path(args.runs_root),
                operator=args.operator,
            )
            print(run_dir)
            return 0

        if args.command == "grade":
            run_dir = Path(args.run_dir)
            manifest = load_manifest(run_dir)
            task = _task(tasks_root, manifest["task"]["id"])
            result = grade_run(run_dir, task, runtime=args.runtime)
            print(json.dumps(result, indent=2, sort_keys=True))
            if result["infrastructure_error"]:
                return 2
            return 0 if result["success"] else 1

        if args.command == "show":
            print(json.dumps(load_manifest(Path(args.run_dir)), indent=2, sort_keys=True))
            return 0

        if args.command == "audit":
            from .deepeval import load_deepeval_suite

            suite = load_deepeval_suite(args.suite)
            baseline_path = Path(args.baseline).expanduser().resolve()
            baseline = _load_baseline(baseline_path)
            base_policy = suite.policy
            policy = AuditPolicy(
                minimum_kill_rate=(
                    args.minimum_kill_rate
                    if args.minimum_kill_rate is not None
                    else base_policy.minimum_kill_rate
                ),
                fail_on_critical_survivor=(
                    False
                    if args.allow_critical_survivors
                    else base_policy.fail_on_critical_survivor
                ),
                fail_on_untested_tools=(
                    False
                    if args.allow_untested_tools
                    else base_policy.fail_on_untested_tools
                ),
                fail_on_tool_contract_issues=(
                    False
                    if args.allow_tool_contract_issues
                    else base_policy.fail_on_tool_contract_issues
                ),
                fail_on_regression=(
                    False
                    if args.allow_regressions
                    else base_policy.fail_on_regression
                ),
            )
            report = run_audit(
                cases=suite.cases,
                tools=suite.tools,
                evaluator=suite.evaluator,
                policy=policy,
                previous_tools=baseline["tools"],
                previous_mutations=baseline["mutations"],
            )
            report["generated_at"] = datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
            output = Path(args.output).expanduser().resolve()
            _write_json(output, report)
            if args.write_baseline and report["gate"]["passed"]:
                _write_json(
                    baseline_path,
                    {
                        "schema_version": "1.0",
                        "tools": report["tools"]["schema_digests"],
                        "mutations": {
                            item["mutant_id"]: item["status"]
                            for item in report["mutations"]
                        },
                    },
                )
            elif args.write_baseline:
                print(
                    "Baseline was not updated because the audit gate failed.",
                    file=sys.stderr,
                )
            _print_audit(report, output)
            return 0 if report["gate"]["passed"] else 1
    except (
        FileNotFoundError,
        ImportError,
        KeyError,
        OSError,
        SpecError,
        RunnerError,
        ValueError,
    ) as error:
        print(f"mendmark: {error}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
