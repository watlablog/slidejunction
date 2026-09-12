"""Immutable project snapshots and pure project-state validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .document import Diagnostic, DiagnosticSeverity, Presentation, SourceDocument
from .layout import LayoutDocument, LayoutLoadResult, dump_layout, parse_layout
from .references import ReferenceValidationResult, _validate_reference_snapshot
from .resolver import ResolvedPresentation

_SUPPORTED_FORMAT_VERSION = 1
_MANIFEST_NAME = "deck.toml"
_ENTRYPOINT_NAME = "deck.py"


class StaleDeckSnapshotError(RuntimeError):
    """The project on disk no longer matches a previously loaded snapshot."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectManifestSnapshot:
    """Validated project settings captured from ``deck.toml``."""

    format_version: int
    source: str
    layout: str
    theme: str
    assets: str

    def __post_init__(self) -> None:
        if not isinstance(self.format_version, int) or isinstance(
            self.format_version, bool
        ):
            raise TypeError("Project format_version must be an integer")
        if self.format_version != _SUPPORTED_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported project format version: {self.format_version}"
            )
        for name in ("source", "layout", "theme", "assets"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"Project {name} setting must be a string")
            if not value:
                raise ValueError(f"Project {name} setting must be non-empty")


@dataclass(frozen=True, slots=True, kw_only=True)
class LoadedTextFile:
    """An exact UTF-8 text snapshot with logical and actual target paths."""

    path: Path
    target_path: Path
    text: str

    def __post_init__(self) -> None:
        _validate_absolute_normalized_path("Loaded text logical path", self.path)
        _validate_absolute_normalized_path("Loaded text target path", self.target_path)
        if not isinstance(self.text, str):
            raise TypeError("Loaded text must be a string")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectFileSnapshot:
    """Validated paths and exact text captured by one project load."""

    root: Path
    manifest_settings: ProjectManifestSnapshot
    manifest: LoadedTextFile
    source: LoadedTextFile
    layout: LoadedTextFile
    theme: LoadedTextFile
    entrypoint_target_path: Path
    assets_path: Path
    assets_target_path: Path

    def __post_init__(self) -> None:
        _validate_absolute_normalized_path("Project root", self.root)
        if not isinstance(self.manifest_settings, ProjectManifestSnapshot):
            raise TypeError(
                "Project manifest settings must be a ProjectManifestSnapshot"
            )
        for name in ("manifest", "source", "layout", "theme"):
            if not isinstance(getattr(self, name), LoadedTextFile):
                raise TypeError(f"Project {name} must be a LoadedTextFile")
        _validate_absolute_normalized_path(
            "Project entrypoint target path", self.entrypoint_target_path
        )
        _validate_absolute_normalized_path("Project assets path", self.assets_path)
        _validate_absolute_normalized_path(
            "Project assets target path", self.assets_target_path
        )

        expected_paths = {
            "manifest": self.root / _MANIFEST_NAME,
            "source": _project_path(self.root, "source", self.manifest_settings.source),
            "layout": _project_path(self.root, "layout", self.manifest_settings.layout),
            "theme": _project_path(self.root, "theme", self.manifest_settings.theme),
        }
        for name, expected in expected_paths.items():
            if getattr(self, name).path != expected:
                raise ValueError(
                    f"Project {name} logical path does not match its manifest setting"
                )

        expected_assets = _project_path(
            self.root, "assets", self.manifest_settings.assets
        )
        if self.assets_path != expected_assets:
            raise ValueError(
                "Project assets logical path does not match its manifest setting"
            )

        logical_files = (*expected_paths.values(), self.entrypoint_path)
        if len(set(logical_files)) != len(logical_files):
            raise ValueError("Required project file logical paths must be distinct")

    @property
    def entrypoint_path(self) -> Path:
        """Return the fixed logical path of the project's Python entrypoint."""
        return self.root / _ENTRYPOINT_NAME


@dataclass(frozen=True, slots=True, kw_only=True)
class DeckSnapshot:
    """A nonfatal project load tied to one source and layout snapshot."""

    files: ProjectFileSnapshot
    source_document: SourceDocument
    layout_result: LayoutLoadResult
    reference_validation: ReferenceValidationResult
    resolved_presentation: ResolvedPresentation

    def __post_init__(self) -> None:
        if not isinstance(self.files, ProjectFileSnapshot):
            raise TypeError("Deck snapshot files must be a ProjectFileSnapshot")
        _validate_source_snapshot(self.files, self.source_document)
        if not isinstance(self.layout_result, LayoutLoadResult):
            raise TypeError("Deck snapshot layout_result must be a LayoutLoadResult")
        layout_document = self.layout_result.document
        if layout_document is None:
            raise ValueError("Deck snapshot requires a nonfatal layout document")
        if not isinstance(self.reference_validation, ReferenceValidationResult):
            raise TypeError(
                "Deck snapshot reference_validation must be a ReferenceValidationResult"
            )
        if not isinstance(self.resolved_presentation, ResolvedPresentation):
            raise TypeError(
                "Deck snapshot resolved_presentation must be a ResolvedPresentation"
            )
        _validate_reference_snapshot(
            self.source_document,
            layout_document,
            self.reference_validation.index,
        )
        if self.resolved_presentation.source_document is not self.source_document:
            raise ValueError(
                "Resolved presentation must use the deck snapshot source document"
            )

    @property
    def layout_document(self) -> LayoutDocument:
        """Return the nonfatal parsed layout document."""
        document = self.layout_result.document
        if document is None:  # pragma: no cover - protected by construction
            raise ValueError("Deck snapshot has no layout document")
        return document

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return Markdown, Layout, then Reference diagnostics."""
        return _aggregate_diagnostics(
            self.source_document,
            self.layout_result,
            self.reference_validation,
        )

    @property
    def has_errors(self) -> bool:
        """Whether any aggregated diagnostic has error severity."""
        return _has_errors(self.diagnostics)


@dataclass(frozen=True, slots=True, kw_only=True)
class DeckLoadResult:
    """A complete project load result, including fatal layout failures."""

    files: ProjectFileSnapshot
    source_document: SourceDocument
    layout_result: LayoutLoadResult
    snapshot: DeckSnapshot | None

    def __post_init__(self) -> None:
        if not isinstance(self.files, ProjectFileSnapshot):
            raise TypeError("Deck load files must be a ProjectFileSnapshot")
        _validate_source_snapshot(self.files, self.source_document)
        if not isinstance(self.layout_result, LayoutLoadResult):
            raise TypeError("Deck load layout_result must be a LayoutLoadResult")
        if self.snapshot is not None and not isinstance(self.snapshot, DeckSnapshot):
            raise TypeError("Deck load snapshot must be a DeckSnapshot or None")

        if self.layout_result.document is None:
            if self.snapshot is not None:
                raise ValueError("A fatal layout load cannot contain a DeckSnapshot")
            return
        if self.snapshot is None:
            raise ValueError("A nonfatal layout load requires a DeckSnapshot")
        if self.snapshot.files is not self.files:
            raise ValueError("Deck load snapshot must use the same file snapshot")
        if self.snapshot.source_document is not self.source_document:
            raise ValueError("Deck load snapshot must use the same source document")
        if self.snapshot.layout_result is not self.layout_result:
            raise ValueError("Deck load snapshot must use the same layout result")

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return Markdown, Layout, then Reference diagnostics when available."""
        validation = (
            None if self.snapshot is None else self.snapshot.reference_validation
        )
        return _aggregate_diagnostics(
            self.source_document,
            self.layout_result,
            validation,
        )

    @property
    def has_errors(self) -> bool:
        """Whether any aggregated diagnostic has error severity."""
        return _has_errors(self.diagnostics)


@dataclass(frozen=True, slots=True)
class _CanonicalLayout:
    text: str
    document: LayoutDocument
    load_result: LayoutLoadResult


def _canonicalize_layout(
    document: LayoutDocument,
    *,
    path: Path,
) -> _CanonicalLayout:
    """Return a canonical layout only when dump/parse/dump is exactly stable."""
    if not isinstance(document, LayoutDocument):
        raise TypeError("Layout canonicalization requires a LayoutDocument")
    if not isinstance(path, Path):
        raise TypeError("Layout canonicalization path must be a Path")

    text = dump_layout(document)
    load_result = parse_layout(text, path=path)
    canonical_document = load_result.document
    if canonical_document is None:
        raise ValueError("Layout writer output is not structurally loadable")
    if dump_layout(canonical_document) != text:
        raise ValueError("Layout writer output is not round-trip stable")
    return _CanonicalLayout(
        text=text,
        document=canonical_document,
        load_result=load_result,
    )


def _project_path(root: Path, setting: str, value: str) -> Path:
    """Return a lexically contained project path without resolving symlinks."""
    relative_path = Path(value)
    if relative_path.is_absolute():
        raise ValueError(f"deck.{setting} must be relative to the project root")

    candidate = Path(os.path.abspath(root / relative_path))
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(
            f"deck.{setting} must remain within the project root: {value}"
        ) from None
    return candidate


def _validate_absolute_normalized_path(name: str, value: object) -> None:
    if not isinstance(value, Path):
        raise TypeError(f"{name} must be a Path")
    if not value.is_absolute():
        raise ValueError(f"{name} must be absolute")
    if Path(os.path.abspath(value)) != value:
        raise ValueError(f"{name} must be lexically normalized")


def _validate_source_snapshot(
    files: ProjectFileSnapshot,
    source_document: object,
) -> None:
    if not isinstance(source_document, SourceDocument):
        raise TypeError("Deck source_document must be a SourceDocument")
    if not isinstance(source_document.text, str):
        raise TypeError("Deck source text must be a string")
    if not isinstance(source_document.presentation, Presentation):
        raise TypeError("Deck source presentation must be a Presentation")
    if source_document.path is not None and not isinstance(source_document.path, Path):
        raise TypeError("Deck source path must be a Path or None")
    if source_document.text != files.source.text:
        raise ValueError("Deck source text does not match the loaded source file")
    if source_document.path != files.source.path:
        raise ValueError("Deck source path does not match the loaded source file")


def _aggregate_diagnostics(
    source_document: SourceDocument,
    layout_result: LayoutLoadResult,
    reference_validation: ReferenceValidationResult | None,
) -> tuple[Diagnostic, ...]:
    reference_diagnostics = (
        () if reference_validation is None else reference_validation.diagnostics
    )
    return (
        *source_document.presentation.diagnostics,
        *layout_result.diagnostics,
        *reference_diagnostics,
    )


def _has_errors(diagnostics: tuple[Diagnostic, ...]) -> bool:
    return any(
        diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in diagnostics
    )


__all__ = [
    "DeckLoadResult",
    "DeckSnapshot",
    "LoadedTextFile",
    "ProjectFileSnapshot",
    "ProjectManifestSnapshot",
    "StaleDeckSnapshotError",
]
