"""Discovery for trusted custom mutation operators."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from .mutations import MutationOperator, MutationPluginError, validate_operators


def _operators(value: Any, source: str) -> tuple[MutationOperator, ...]:
    if callable(value) and not callable(getattr(value, "mutate", None)):
        try:
            value = value()
        except Exception as error:
            raise MutationPluginError(
                f"mutation plugin {source!r} failed during initialization: {error}"
            ) from error
    if callable(getattr(value, "mutate", None)):
        values = (value,)
    else:
        try:
            values = tuple(value)
        except (TypeError, ValueError) as error:
            raise MutationPluginError(
                f"mutation plugin {source!r} must provide operators"
            ) from error
    return validate_operators(values)


def operators_from_module(module: ModuleType) -> tuple[MutationOperator, ...]:
    """Read optional custom operators from an already loaded suite module."""
    if hasattr(module, "get_mutation_operators"):
        return _operators(module.get_mutation_operators, module.__name__)
    if hasattr(module, "MUTATION_OPERATORS"):
        return _operators(module.MUTATION_OPERATORS, module.__name__)
    return ()


def _load_path(path: Path) -> ModuleType:
    resolved = path.expanduser().resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(
        f"mendmark_mutation_plugin_{digest}", resolved
    )
    if spec is None or spec.loader is None:
        raise MutationPluginError(f"cannot load mutation plugin: {resolved}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise MutationPluginError(
            f"mutation plugin {resolved} failed during import: {error}"
        ) from error
    return module


def load_mutation_plugin(specification: str) -> tuple[MutationOperator, ...]:
    """Load operators from a file, module attribute, or installed entry point."""
    path = Path(specification)
    if path.is_file() or specification.endswith(".py"):
        module = _load_path(path)
        operators = operators_from_module(module)
        if not operators:
            raise MutationPluginError(
                f"mutation plugin {specification!r} defines no operators"
            )
        return operators

    entry_points = importlib.metadata.entry_points()
    matches = entry_points.select(group="mendmark.mutations", name=specification)
    for entry_point in matches:
        try:
            return _operators(entry_point.load(), specification)
        except Exception as error:
            if isinstance(error, MutationPluginError):
                raise
            raise MutationPluginError(
                f"mutation entry point {specification!r} could not be loaded: {error}"
            ) from error

    if ":" in specification:
        module_name, attribute = specification.split(":", 1)
        try:
            module = importlib.import_module(module_name)
            value = getattr(module, attribute)
        except (ImportError, AttributeError) as error:
            raise MutationPluginError(
                f"cannot load mutation plugin {specification!r}: {error}"
            ) from error
        return _operators(value, specification)

    raise MutationPluginError(
        f"no mutation plugin named {specification!r}; use a Python file, "
        "module:attribute, or mendmark.mutations entry point"
    )


def load_mutation_plugins(
    specifications: list[str] | tuple[str, ...],
) -> tuple[MutationOperator, ...]:
    loaded: list[MutationOperator] = []
    for specification in specifications:
        loaded.extend(load_mutation_plugin(specification))
    return validate_operators(tuple(loaded))
