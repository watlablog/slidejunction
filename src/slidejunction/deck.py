"""SlideJunction presentation project loading and safe persistence."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Self

from ._project_io import (
    _cleanup_staged_text_files,
    _discover_manifest,
    _discovery_start,
    _entry_exists,
    _is_stale_topology_os_error,
    _load_project_files,
    _replace_staged_text,
    _require_changed_target_not_hard_link,
    _require_current_project_files,
    _stage_utf8_text,
    _StagedTextFile,
    _validate_project_for_open,
)
from .document import Block, InlineFormat, SourceDocument
from .layout import (
    LayoutDocument,
    Theme,
    ThemePreset,
    dump_layout,
    parse_layout,
)
from .markdown import parse_markdown
from .project import (
    DeckLoadResult,
    DeckSnapshot,
    ProjectFileSnapshot,
    StaleDeckSnapshotError,
    _canonicalize_layout,
)
from .reference_editing import ReferenceEditResult
from .references import ReferenceKind, validate_references
from .resolver import resolve_presentation
from .source_editing import apply_reference_edit_to_source

_MANIFEST_NAME = "deck.toml"
_ASSETS_DIRECTORY = "assets"
_PROJECT_ENTRY_NAMES = (
    _MANIFEST_NAME,
    "deck.py",
    "slides.md",
    "layout.json",
    "theme.css",
    _ASSETS_DIRECTORY,
)
_MANIFEST_TEXT = (
    "[deck]\n"
    "format_version = 1\n"
    'source = "slides.md"\n'
    'layout = "layout.json"\n'
    'theme = "theme.css"\n'
    'assets = "assets"\n'
)
_ENTRYPOINT_TEXT = (
    '"""Python control entry point for this SlideJunction presentation."""\n'
    "\n"
    "from slidejunction import Deck\n"
    "\n"
    "deck = Deck.open(__file__)\n"
)
_SOURCE_TEXT = "# Untitled Presentation\n"
_THEME_TEXT = "/* SlideJunction presentation theme */\n"


class Deck:
    """A project handle whose semantic state is loaded fresh from disk."""

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        raise TypeError(
            "Deck cannot be constructed directly; use Deck.init() or Deck.open()."
        )

    @classmethod
    def _from_root(cls, root: str | Path) -> Self:
        instance = object.__new__(cls)
        instance._root = Path(root).expanduser().resolve()
        return instance

    @property
    def root(self) -> Path:
        """Return the canonical absolute path to the project root."""
        return self._root

    @classmethod
    def open(cls, path: str | Path = ".") -> Self:
        """Open the nearest SlideJunction project at or above *path*."""
        manifest = _discover_manifest(_discovery_start(path))
        root = manifest.parent
        _validate_project_for_open(root)
        return cls._from_root(root)

    @classmethod
    def init(cls, path: str | Path) -> Self:
        """Create a minimal M7 SlideJunction project at *path*.

        ``layout.json`` is the structured configuration source of truth.
        ``layout.css`` is neither a project input nor generated in M7; any future
        renderer/build derivative belongs to Milestone 8 or later.
        """
        requested_root = Path(path).expanduser()
        if requested_root.is_symlink() and not requested_root.exists():
            raise FileExistsError(
                f"Cannot initialize a project at broken symlink: {requested_root}"
            )

        root = requested_root.resolve()
        if root.exists() and not root.is_dir():
            raise FileExistsError(f"Project path is not a directory: {root}")

        root.mkdir(parents=True, exist_ok=True)
        collisions = [
            root / name for name in _PROJECT_ENTRY_NAMES if _entry_exists(root / name)
        ]
        if collisions:
            names = ", ".join(collision.name for collision in collisions)
            raise FileExistsError(
                f"Cannot initialize project; entries already exist: {names}"
            )

        contents = {
            _MANIFEST_NAME: _MANIFEST_TEXT,
            "deck.py": _ENTRYPOINT_TEXT,
            "slides.md": _SOURCE_TEXT,
            "layout.json": _initial_layout_text(),
            "theme.css": _THEME_TEXT,
        }
        for name, content in contents.items():
            with (root / name).open(
                "x", encoding="utf-8", newline="\n"
            ) as project_file:
                project_file.write(content)

        (root / _ASSETS_DIRECTORY).mkdir()
        return cls._from_root(root)

    def load(self) -> DeckLoadResult:
        """Read and derive a fresh immutable project snapshot from disk."""
        files = _load_project_files(self.root)
        source_document = parse_markdown(files.source.text, path=files.source.path)
        layout_result = parse_layout(files.layout.text, path=files.layout.path)
        layout_document = layout_result.document
        if layout_document is None:
            return DeckLoadResult(
                files=files,
                source_document=source_document,
                layout_result=layout_result,
                snapshot=None,
            )

        reference_validation = validate_references(
            source_document,
            layout_document,
            layout_path=files.layout.path,
        )
        resolved_presentation = resolve_presentation(
            source_document,
            layout_document,
            reference_validation.index,
        )
        snapshot = DeckSnapshot(
            files=files,
            source_document=source_document,
            layout_result=layout_result,
            reference_validation=reference_validation,
            resolved_presentation=resolved_presentation,
        )
        return DeckLoadResult(
            files=files,
            source_document=source_document,
            layout_result=layout_result,
            snapshot=snapshot,
        )

    def save_reference_edit(
        self,
        base_snapshot: DeckSnapshot,
        edit_result: ReferenceEditResult,
    ) -> DeckLoadResult:
        """Safely persist one M6 reference edit and return a fresh load.

        Baseline source/layout provenance is re-established before any write.
        A source-plus-layout edit commits the additive layout definition first.
        If a replace succeeds and its directory fsync then fails, the error is
        propagated even though that target may already contain the new text; no
        rollback is attempted and callers should load again to inspect disk state.
        """
        if not isinstance(base_snapshot, DeckSnapshot):
            raise TypeError("base_snapshot must be a DeckSnapshot")
        if not isinstance(edit_result, ReferenceEditResult):
            raise TypeError("edit_result must be a ReferenceEditResult")
        _require_snapshot_owner(self.root, base_snapshot)
        if edit_result.source_document is not base_snapshot.source_document:
            raise StaleDeckSnapshotError(
                "Reference edit source does not belong to the base snapshot"
            )
        _require_baseline_provenance(base_snapshot)

        candidate_layout = edit_result.layout_document
        _validate_reference_edit_layout_delta(base_snapshot, edit_result)
        candidate_source = apply_reference_edit_to_source(edit_result)
        return self._save_candidate(
            base_snapshot,
            candidate_source=candidate_source,
            candidate_layout=candidate_layout,
            edit_result=edit_result,
        )

    def save_layout(
        self,
        base_snapshot: DeckSnapshot,
        layout_document: LayoutDocument,
    ) -> DeckLoadResult:
        """Safely persist an explicit layout update and return a fresh load.

        If a replace succeeds and its directory fsync then fails, the error is
        propagated even though the layout may already contain the new text. No
        rollback is attempted; callers should load again to inspect disk state.
        """
        if not isinstance(base_snapshot, DeckSnapshot):
            raise TypeError("base_snapshot must be a DeckSnapshot")
        if not isinstance(layout_document, LayoutDocument):
            raise TypeError("layout_document must be a LayoutDocument")
        _require_snapshot_owner(self.root, base_snapshot)
        _require_baseline_provenance(base_snapshot)
        return self._save_candidate(
            base_snapshot,
            candidate_source=base_snapshot.source_document,
            candidate_layout=layout_document,
            edit_result=None,
        )

    def _save_candidate(
        self,
        base_snapshot: DeckSnapshot,
        *,
        candidate_source: SourceDocument,
        candidate_layout: LayoutDocument,
        edit_result: ReferenceEditResult | None,
    ) -> DeckLoadResult:
        canonical_base = _canonicalize_layout(
            base_snapshot.layout_document,
            path=base_snapshot.files.layout.path,
        )
        canonical_candidate = _canonicalize_layout(
            candidate_layout,
            path=base_snapshot.files.layout.path,
        )
        layout_changed = not _model_equal_exact(
            canonical_candidate.document,
            canonical_base.document,
        )
        source_changed = candidate_source.text != base_snapshot.source_document.text

        if edit_result is not None:
            _validate_persisted_reference_delta(
                canonical_base.document,
                canonical_candidate.document,
                edit_result,
                source_changed=source_changed,
                layout_changed=layout_changed,
            )

        persisted_layout = (
            canonical_candidate.document
            if layout_changed
            else base_snapshot.layout_document
        )
        reference_validation = validate_references(
            candidate_source,
            persisted_layout,
            layout_path=base_snapshot.files.layout.path,
        )
        resolve_presentation(
            candidate_source,
            persisted_layout,
            reference_validation.index,
        )

        if layout_changed and base_snapshot.layout_result.diagnostics:
            raise ValueError(
                "Cannot overwrite a recovered layout with loader diagnostics"
            )

        expected_layout_text = (
            canonical_candidate.text
            if layout_changed
            else base_snapshot.files.layout.text
        )
        _commit_project_text(
            base_snapshot.files,
            source_text=candidate_source.text,
            layout_text=expected_layout_text,
            source_changed=source_changed,
            layout_changed=layout_changed,
        )

        reloaded = _reload_after_save(self)
        _validate_reloaded_state(
            reloaded,
            baseline=base_snapshot.files,
            expected_source=candidate_source,
            expected_source_text=candidate_source.text,
            expected_layout=(
                canonical_candidate.document
                if layout_changed
                else base_snapshot.layout_document
            ),
            expected_layout_text=expected_layout_text,
        )
        return reloaded


def _initial_layout_text() -> str:
    return dump_layout(
        LayoutDocument(
            format_version=1,
            theme=Theme(
                preset=ThemePreset(
                    name="slidejunction-default",
                    version=1,
                )
            ),
        )
    )


def _reload_after_save(deck: Deck) -> DeckLoadResult:
    try:
        return deck.load()
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise
    except (
        FileNotFoundError,
        IsADirectoryError,
        NotADirectoryError,
        ValueError,
    ) as error:
        raise StaleDeckSnapshotError(
            "Project state changed before post-save reload completed"
        ) from error
    except OSError as error:
        if not _is_stale_topology_os_error(error):
            raise
        raise StaleDeckSnapshotError(
            "Project state changed before post-save reload completed"
        ) from error


def _require_snapshot_owner(root: Path, snapshot: DeckSnapshot) -> None:
    if snapshot.files.root != root:
        raise StaleDeckSnapshotError(
            "Deck snapshot belongs to a different project root"
        )


def _require_baseline_provenance(snapshot: DeckSnapshot) -> None:
    expected_source = parse_markdown(
        snapshot.files.source.text,
        path=snapshot.files.source.path,
    )
    if not _model_equal_exact(expected_source, snapshot.source_document):
        raise ValueError(
            "DeckSnapshot source document does not match its loaded source text"
        )
    expected_layout = parse_layout(
        snapshot.files.layout.text,
        path=snapshot.files.layout.path,
    )
    if not _model_equal_exact(expected_layout, snapshot.layout_result):
        raise ValueError(
            "DeckSnapshot layout result does not match its loaded layout text"
        )


def _validate_reference_edit_layout_delta(
    base_snapshot: DeckSnapshot,
    edit_result: ReferenceEditResult,
) -> None:
    base = base_snapshot.layout_document
    candidate = edit_result.layout_document
    changes = edit_result.source_changes
    if not isinstance(changes, tuple) or len(changes) > 1:
        raise ValueError("Reference edit must contain at most one source change")

    if not changes:
        if _model_equal_exact(candidate, base):
            return
        consumer = edit_result.selected_consumer
        ref_id = consumer.config_ref
        if ref_id is None:
            raise ValueError("A consumer without a ref cannot change a definition")
        kind = _consumer_kind(consumer)
        if not _is_single_definition_update(base, candidate, kind, ref_id):
            raise ValueError(
                "Reference edit contains changes outside the selected definition"
            )
        return

    change = changes[0]
    new_ref_id = change.new_ref_id
    if new_ref_id is None or _has_global_definition(base, new_ref_id):
        if not _model_equal_exact(candidate, base):
            raise ValueError(
                "A source-only reference edit cannot change the layout document"
            )
        return
    if not _is_exact_definition_addition(base, candidate, change.kind, new_ref_id):
        raise ValueError(
            "A new reference edit must add exactly one matching definition"
        )


def _validate_persisted_reference_delta(
    base: LayoutDocument,
    candidate: LayoutDocument,
    edit_result: ReferenceEditResult,
    *,
    source_changed: bool,
    layout_changed: bool,
) -> None:
    if not edit_result.source_changes:
        return
    change = edit_result.source_changes[0]
    new_ref_id = change.new_ref_id
    if new_ref_id is None or _has_global_definition(base, new_ref_id):
        if layout_changed:
            raise ValueError("A source-only edit changed canonical layout state")
        return
    if not source_changed:
        raise ValueError("A planned source reference change did not change source text")
    if not layout_changed or not _is_exact_definition_addition(
        base, candidate, change.kind, new_ref_id
    ):
        raise ValueError(
            "Source-plus-layout save must persist exactly one new definition"
        )


def _consumer_kind(consumer: object) -> ReferenceKind:
    if isinstance(consumer, InlineFormat):
        return ReferenceKind.INLINE_FORMAT
    if isinstance(consumer, Block):
        return ReferenceKind.CONFIGURATION
    raise TypeError("Selected consumer is not reference-capable")


def _has_global_definition(document: LayoutDocument, ref_id: int) -> bool:
    return ref_id in document.configurations or ref_id in document.inline_formats


def _is_single_definition_update(
    base: LayoutDocument,
    candidate: LayoutDocument,
    kind: ReferenceKind,
    ref_id: int,
) -> bool:
    if not _model_equal_exact(base.format_version, candidate.format_version) or not (
        _model_equal_exact(base.theme, candidate.theme)
    ):
        return False
    if kind is ReferenceKind.CONFIGURATION:
        if not _model_equal_exact(base.inline_formats, candidate.inline_formats):
            return False
        return _mapping_changed_only_at(
            base.configurations,
            candidate.configurations,
            ref_id,
        )
    if not _model_equal_exact(base.configurations, candidate.configurations):
        return False
    return _mapping_changed_only_at(
        base.inline_formats,
        candidate.inline_formats,
        ref_id,
    )


def _mapping_changed_only_at(
    base: Mapping[int, object],
    candidate: Mapping[int, object],
    ref_id: int,
) -> bool:
    if base.keys() != candidate.keys() or ref_id not in base:
        return False
    return all(
        _model_equal_exact(base[key], candidate[key]) for key in base if key != ref_id
    )


def _is_exact_definition_addition(
    base: LayoutDocument,
    candidate: LayoutDocument,
    kind: ReferenceKind,
    ref_id: int,
) -> bool:
    if not _model_equal_exact(base.format_version, candidate.format_version) or not (
        _model_equal_exact(base.theme, candidate.theme)
    ):
        return False
    if _has_global_definition(base, ref_id):
        return False
    if kind is ReferenceKind.CONFIGURATION:
        return (
            _model_equal_exact(base.inline_formats, candidate.inline_formats)
            and set(candidate.configurations) == {*base.configurations, ref_id}
            and all(
                _model_equal_exact(candidate.configurations[key], value)
                for key, value in base.configurations.items()
            )
        )
    return (
        _model_equal_exact(base.configurations, candidate.configurations)
        and set(candidate.inline_formats) == {*base.inline_formats, ref_id}
        and all(
            _model_equal_exact(candidate.inline_formats[key], value)
            for key, value in base.inline_formats.items()
        )
    )


def _commit_project_text(
    baseline: ProjectFileSnapshot,
    *,
    source_text: str,
    layout_text: str,
    source_changed: bool,
    layout_changed: bool,
) -> None:
    current = _require_current_project_files(baseline)
    _require_changed_targets(
        current,
        source_changed=source_changed,
        layout_changed=layout_changed,
    )

    staged: list[_StagedTextFile] = []
    source_stage: _StagedTextFile | None = None
    layout_stage: _StagedTextFile | None = None
    try:
        if layout_changed:
            layout_stage = _stage_utf8_text(current.layout.target_path, layout_text)
            staged.append(layout_stage)
        if source_changed:
            source_stage = _stage_utf8_text(current.source.target_path, source_text)
            staged.append(source_stage)

        current = _require_current_project_files(baseline)
        _require_changed_targets(
            current,
            source_changed=source_changed,
            layout_changed=layout_changed,
        )

        if layout_stage is not None:
            _replace_staged_text(layout_stage)
        if layout_stage is not None and source_stage is not None:
            current = _require_current_project_files(
                baseline,
                layout_text=layout_text,
            )
            _require_changed_target_not_hard_link(
                current.source.target_path,
                name="source",
            )
        if source_stage is not None:
            _replace_staged_text(source_stage)
    except BaseException:
        _cleanup_staged_text_files(tuple(staged), suppress_errors=True)
        raise
    _cleanup_staged_text_files(tuple(staged), suppress_errors=False)


def _require_changed_targets(
    files: ProjectFileSnapshot,
    *,
    source_changed: bool,
    layout_changed: bool,
) -> None:
    if source_changed:
        _require_changed_target_not_hard_link(
            files.source.target_path,
            name="source",
        )
    if layout_changed:
        _require_changed_target_not_hard_link(
            files.layout.target_path,
            name="layout",
        )


def _validate_reloaded_state(
    reloaded: DeckLoadResult,
    *,
    baseline: ProjectFileSnapshot,
    expected_source: SourceDocument,
    expected_source_text: str,
    expected_layout: LayoutDocument,
    expected_layout_text: str,
) -> None:
    if reloaded.snapshot is None:
        raise StaleDeckSnapshotError(
            "Saved project did not reload with a structural layout document"
        )
    if reloaded.files.manifest_settings != baseline.manifest_settings:
        raise StaleDeckSnapshotError("Project manifest changed during save")
    if _target_paths(reloaded.files) != _target_paths(baseline):
        raise StaleDeckSnapshotError("Project targets changed during save")
    if reloaded.files.source.text != expected_source_text:
        raise StaleDeckSnapshotError("Saved source does not match intended text")
    if not _model_equal_exact(reloaded.source_document, expected_source):
        raise StaleDeckSnapshotError(
            "Saved source model does not match intended source"
        )
    if reloaded.files.layout.text != expected_layout_text:
        raise StaleDeckSnapshotError("Saved layout does not match intended text")
    if not _model_equal_exact(reloaded.snapshot.layout_document, expected_layout):
        raise StaleDeckSnapshotError(
            "Saved layout model does not match intended layout"
        )


def _target_paths(files: ProjectFileSnapshot) -> tuple[Path, ...]:
    return (
        files.manifest.target_path,
        files.entrypoint_target_path,
        files.source.target_path,
        files.layout.target_path,
        files.theme.target_path,
        files.assets_target_path,
    )


def _model_equal_exact(left: object, right: object) -> bool:
    """Compare immutable models recursively without numeric type coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float):
        return left.hex() == right.hex()
    if is_dataclass(left) and not isinstance(left, type):
        return all(
            _model_equal_exact(
                getattr(left, field.name),
                getattr(right, field.name),
            )
            for field in fields(left)
        )
    if isinstance(left, Mapping):
        if len(left) != len(right):
            return False
        unmatched = list(right.items())
        for left_key, left_value in left.items():
            for index, (right_key, right_value) in enumerate(unmatched):
                if _model_equal_exact(left_key, right_key):
                    if not _model_equal_exact(left_value, right_value):
                        return False
                    unmatched.pop(index)
                    break
            else:
                return False
        return not unmatched
    if isinstance(left, tuple | list):
        return len(left) == len(right) and all(
            _model_equal_exact(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right


__all__ = ["Deck"]
