#!/usr/bin/env python3
"""Exercise a built Mendmark wheel as a new user outside the source tree."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    project_root = args.project_root.resolve()
    if not wheel.is_file():
        parser.error(f"wheel does not exist: {wheel}")

    with tempfile.TemporaryDirectory(prefix="mendmark-wheel-assurance-") as raw_temp:
        root = Path(raw_temp)
        environment = root / "venv"
        workspace = root / "workspace"
        workspace.mkdir()
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        mendmark = bin_dir / ("mendmark.exe" if os.name == "nt" else "mendmark")
        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        for name in tuple(clean_env):
            if name.endswith("_API_KEY"):
                clean_env.pop(name)

        run(
            [str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
            cwd=workspace,
            env=clean_env,
        )
        version = run([str(mendmark), "--version"], cwd=workspace, env=clean_env).strip()
        package_version = run(
            [
                str(python),
                "-c",
                "from importlib.metadata import version; print(version('mendmark-evals'))",
            ],
            cwd=workspace,
            env=clean_env,
        ).strip()
        if version != f"mendmark {package_version}":
            raise RuntimeError(f"unexpected version output: {version!r}")

        source_distribution = wheel.parent / f"mendmark_evals-{package_version}.tar.gz"
        if source_distribution.is_file():
            with tarfile.open(source_distribution, "r:gz") as archive:
                members = {
                    Path(name).parts[1:]
                    for name in archive.getnames()
                    if len(Path(name).parts) > 1
                }
            required = {
                ("scripts", "assure_distribution.py"),
                (".github", "allowed_signers"),
                ("docs", "assurance.md"),
                ("golden", "agent-eval-v1", "manifest.json"),
                ("golden", "agent-eval-v1", "suite.json"),
                ("golden", "agent-eval-v1", "results.json"),
            }
            missing = sorted(required - members)
            if missing:
                raise RuntimeError(
                    "source distribution is missing assurance assets: "
                    + ", ".join("/".join(path) for path in missing)
                )
        help_text = run([str(mendmark), "--help"], cwd=workspace, env=clean_env)
        if "mutation-test" not in help_text.lower() or "audit-json" not in help_text:
            raise RuntimeError("installed CLI help is missing the primary product journey")
        tasks = run([str(mendmark), "tasks"], cwd=workspace, env=clean_env)
        if len([line for line in tasks.splitlines() if line.strip()]) != 5:
            raise RuntimeError("installed wheel did not expose all five ML integrity tasks")

        schema_count = run(
            [
                str(python),
                "-c",
                (
                    "from importlib import resources; "
                    "root=resources.files('mendmark').joinpath('schemas'); "
                    "print(len(list(root.iterdir())))"
                ),
            ],
            cwd=workspace,
            env=clean_env,
        ).strip()
        if schema_count != "5":
            raise RuntimeError(f"installed wheel exposed {schema_count} schemas, expected 5")

        for name in (
            "order_agent_suite.json",
            "json_evaluator.py",
            "order_agent_baseline.json",
        ):
            shutil.copyfile(project_root / "examples" / name, workspace / name)
        report_path = workspace / "report.json"
        output = run(
            [
                str(mendmark),
                "audit-json",
                "order_agent_suite.json",
                "--evaluator-command",
                f"{python} json_evaluator.py",
                "--baseline",
                "order_agent_baseline.json",
                "--output",
                str(report_path),
            ],
            cwd=workspace,
            env=clean_env,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["gate"]["passed"] is not True or report["summary"]["mutants"] != 13:
            raise RuntimeError("clean-wheel audit did not produce the expected passing report")
        if "Gate: PASS" not in output:
            raise RuntimeError("clean-wheel audit did not present a clear passing result")

    print(f"Distribution assurance passed for {wheel.name} ({version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
