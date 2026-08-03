from __future__ import annotations

from pathlib import Path

from mendmark.cli import _tasks_root


def test_default_tasks_root_falls_back_to_installed_data(
    monkeypatch, tmp_path: Path
) -> None:
    working = tmp_path / "working"
    installed = tmp_path / "prefix" / "share" / "mendmark" / "tasks"
    working.mkdir()
    installed.mkdir(parents=True)
    monkeypatch.chdir(working)
    monkeypatch.setattr("mendmark.cli.sysconfig.get_path", lambda name: str(tmp_path / "prefix"))

    assert _tasks_root("tasks") == installed.resolve()
