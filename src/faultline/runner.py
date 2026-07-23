from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .models import TaskSpec


class RunnerError(RuntimeError):
    """Raised when a run cannot be prepared or graded safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _files(root: Path) -> Iterable[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in _files(root):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        contents = path.read_bytes()
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return f"sha256:{digest.hexdigest()}"


def prepare_run(
    task: TaskSpec,
    runs_root: Path,
    *,
    operator: str,
    assistant: str | None,
) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{task.task_id}-{stamp}-{uuid.uuid4().hex[:8]}"
    run_dir = runs_root.resolve() / run_id
    workspace = run_dir / "workspace"
    workspace.parent.mkdir(parents=True, exist_ok=False)
    shutil.copytree(task.public_dir, workspace)

    manifest = {
        "schema_version": "1.0",
        "run_id": run_id,
        "task": {
            "id": task.task_id,
            "schema_version": task.schema_version,
            "failure_class": task.failure_class,
            "difficulty": task.difficulty,
            "public_digest": directory_digest(task.public_dir),
        },
        "framework": {"name": "faultline", "version": __version__},
        "provenance": {
            "operator": operator,
            "assistant": assistant,
            "collaboration_disclosed": bool(assistant),
        },
        "created_at": utc_now(),
        "workspace_initial_digest": directory_digest(workspace),
        "grade_attempts": [],
    }
    _write_json(run_dir / "manifest.json", manifest)
    return run_dir


def _copy_hidden_tests(task: TaskSpec, grading_workspace: Path) -> None:
    target = grading_workspace / "tests" / "_faultline_hidden"
    if target.exists():
        raise RunnerError("workspace contains reserved hidden-test path")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(task.hidden_tests_dir, target)


def _sandbox_command(workspace: Path, command: tuple[str, ...]) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RunnerError(
            "Bubblewrap is required for isolated grading; install bwrap or use "
            "--runtime local for framework development only"
        )

    args = [
        bwrap,
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--ro-bind",
        "/usr",
        "/usr",
    ]
    for system_dir in ("/lib", "/lib64", "/etc"):
        if Path(system_dir).exists():
            args.extend(("--ro-bind", system_dir, system_dir))
    args.extend(
        (
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--bind",
            str(workspace),
            "/workspace",
            "--chdir",
            "/workspace",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp",
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
        )
    )
    args.extend(command)
    return args


def _resource_limits() -> None:
    # Limits apply to both local and Bubblewrap development runs. Stronger hosted
    # isolation should use disposable VMs with cgroup-level controls.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    memory = 1_024 * 1_024 * 1_024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))


def grade_run(
    run_dir: Path,
    task: TaskSpec,
    *,
    runtime: str = "bwrap",
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    workspace = run_dir / "workspace"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RunnerError(f"missing run manifest: {manifest_path}") from error
    if manifest.get("task", {}).get("id") != task.task_id:
        raise RunnerError("run manifest and task specification do not match")
    if not workspace.is_dir():
        raise RunnerError(f"missing run workspace: {workspace}")
    if runtime not in {"bwrap", "local"}:
        raise RunnerError("runtime must be 'bwrap' or 'local'")

    with tempfile.TemporaryDirectory(prefix="faultline-grade-") as temp:
        grading_workspace = Path(temp) / "workspace"
        shutil.copytree(workspace, grading_workspace)
        _copy_hidden_tests(task, grading_workspace)

        if runtime == "bwrap":
            command = _sandbox_command(grading_workspace, task.grader.command)
            cwd = None
        else:
            command = list(task.grader.command)
            cwd = grading_workspace

        started_at = utc_now()
        start = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=task.grader.timeout_seconds,
                check=False,
                preexec_fn=_resource_limits,
            )
            output = completed.stdout
            exit_code = completed.returncode
            timed_out = False
        except subprocess.TimeoutExpired as error:
            captured = error.stdout or ""
            output = captured.decode() if isinstance(captured, bytes) else captured
            output += f"\nTimed out after {task.grader.timeout_seconds} seconds.\n"
            exit_code = None
            timed_out = True

        result = {
            "schema_version": "1.0",
            "run_id": manifest["run_id"],
            "task_id": task.task_id,
            "grader": "deterministic-tests",
            "runtime": runtime,
            "isolation_requested": runtime == "bwrap",
            "isolated": runtime == "bwrap",
            "started_at": started_at,
            "duration_seconds": round(time.monotonic() - start, 6),
            "workspace_digest": directory_digest(workspace),
            "success": exit_code == 0 and not timed_out,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "command": list(task.grader.command),
            "output": output,
        }
        infrastructure_error = (
            runtime == "bwrap"
            and exit_code not in (None, 0)
            and output.lstrip().startswith("bwrap:")
        )
        result["infrastructure_error"] = infrastructure_error
        result["isolated"] = runtime == "bwrap" and not infrastructure_error
        result["valid"] = not infrastructure_error
        if infrastructure_error:
            result["outcome"] = "infrastructure_error"
        elif timed_out:
            result["outcome"] = "timed_out"
        elif result["success"]:
            result["outcome"] = "passed"
        else:
            result["outcome"] = "failed"

    result_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ.json")
    result_path = run_dir / "results" / result_name
    _write_json(result_path, result)
    manifest.setdefault("grade_attempts", []).append(
        {
            "result": str(result_path.relative_to(run_dir)),
            "created_at": utc_now(),
            "success": result["success"],
            "outcome": result["outcome"],
            "valid": result["valid"],
            "isolated": result["isolated"],
            "workspace_digest": result["workspace_digest"],
        }
    )
    _write_json(manifest_path, manifest)
    return result


def load_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir.resolve() / "manifest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RunnerError(f"missing run manifest: {path}") from error
