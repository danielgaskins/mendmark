from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import SpecError, TaskSpec
from .runner import RunnerError, grade_run, load_manifest, prepare_run


def _tasks_root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _task(tasks_root: Path, task_id: str) -> TaskSpec:
    return TaskSpec.load(tasks_root / task_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mendmark",
        description="Evaluate agents repairing broken machine-learning systems.",
    )
    parser.add_argument("--tasks-root", default="tasks", help="task directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("tasks", help="list and validate available tasks")

    prepare = subparsers.add_parser("prepare", help="create a public agent workspace")
    prepare.add_argument("task_id")
    prepare.add_argument("--runs-root", default="runs")
    prepare.add_argument("--operator", required=True)
    prepare.add_argument("--assistant", default=None)

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
    return parser


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
                assistant=args.assistant,
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
    except (FileNotFoundError, KeyError, OSError, SpecError, RunnerError) as error:
        print(f"mendmark: {error}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
