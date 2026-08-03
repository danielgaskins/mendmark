"""Setuptools shim and package data for the ML integrity task pack."""

from pathlib import Path
from setuptools import setup


task_files: dict[str, list[str]] = {}
for task_file in Path("tasks").rglob("*"):
    if (
        task_file.is_file()
        and "__pycache__" not in task_file.parts
        and task_file.suffix != ".pyc"
    ):
        relative_parent = task_file.parent.relative_to("tasks")
        destination = str(Path("share/mendmark/tasks") / relative_parent)
        task_files.setdefault(destination, []).append(str(task_file))


setup(data_files=sorted(task_files.items()))
