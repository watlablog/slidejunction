"""Strict JSON parsing for SlideJunction layout configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..document import ConfigPointer, Diagnostic, DiagnosticSeverity
from .model import LayoutLoadResult
from .validation import validate_layout


@dataclass(frozen=True, slots=True)
class _JSONObject:
    pairs: tuple[tuple[str, object], ...]


class _NonJsonConstant(ValueError):
    pass


def parse_layout(
    text: str,
    *,
    path: str | Path | None = None,
) -> LayoutLoadResult:
    """Parse strict JSON without reading from or writing to the filesystem."""
    provenance = None if path is None else Path(path)
    try:
        raw = json.loads(
            text,
            object_pairs_hook=lambda pairs: _JSONObject(tuple(pairs)),
            parse_constant=_reject_non_json_constant,
        )
    except (json.JSONDecodeError, _NonJsonConstant) as error:
        return LayoutLoadResult(
            document=None,
            diagnostics=(
                _diagnostic(
                    provenance,
                    "",
                    "invalid-layout-json",
                    f"Layout configuration is not strict JSON: {error}",
                ),
            ),
        )

    if not isinstance(raw, _JSONObject):
        return validate_layout(_materialize(raw), path=provenance)

    duplicates: list[Diagnostic] = []
    _collect_duplicates(raw, "", provenance, duplicates)
    if duplicates:
        return LayoutLoadResult(
            document=None,
            diagnostics=tuple(sorted(duplicates, key=_diagnostic_sort_key)),
        )
    return validate_layout(_materialize(raw), path=provenance)


def _reject_non_json_constant(value: str) -> object:
    raise _NonJsonConstant(value)


def _collect_duplicates(
    value: object,
    pointer: str,
    path: Path | None,
    diagnostics: list[Diagnostic],
) -> None:
    if isinstance(value, _JSONObject):
        seen: set[str] = set()
        for key, child in value.pairs:
            child_pointer = _join_pointer(pointer, key)
            if key in seen:
                diagnostics.append(
                    _diagnostic(
                        path,
                        child_pointer,
                        "duplicate-layout-json-key",
                        f"Duplicate JSON object key: {key!r}",
                    )
                )
            else:
                seen.add(key)
            _collect_duplicates(child, child_pointer, path, diagnostics)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            child_pointer = _join_pointer(pointer, str(index))
            _collect_duplicates(child, child_pointer, path, diagnostics)


def _materialize(value: object) -> Any:
    if isinstance(value, _JSONObject):
        return {key: _materialize(child) for key, child in value.pairs}
    if isinstance(value, list):
        return [_materialize(child) for child in value]
    return value


def _join_pointer(parent: str, component: str) -> str:
    escaped = component.replace("~", "~0").replace("/", "~1")
    return f"{parent}/{escaped}"


def _diagnostic(
    path: Path | None,
    pointer: str,
    code: str,
    message: str,
) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=code,
        message=message,
        config_pointer=ConfigPointer(path=path, pointer=pointer),
    )


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str, int]:
    location = diagnostic.config_pointer
    if location is None:
        raise ValueError("Layout diagnostic has no config pointer")
    return (location.pointer, diagnostic.code, diagnostic.ref_id or 0)


__all__ = ["parse_layout"]
