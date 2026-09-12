from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from slidejunction import project
from slidejunction.document import (
    ConfigPointer,
    Diagnostic,
    DiagnosticSeverity,
    SourceSpan,
)
from slidejunction.layout import (
    Configuration,
    LayoutDocument,
    LayoutLoadResult,
    Size,
    Theme,
    ThemeColor,
    ThemePreset,
    Typography,
    dump_layout,
    parse_layout,
)
from slidejunction.markdown import parse_markdown
from slidejunction.project import (
    DeckLoadResult,
    DeckSnapshot,
    LoadedTextFile,
    ProjectFileSnapshot,
    ProjectManifestSnapshot,
    StaleDeckSnapshotError,
    _canonicalize_layout,
)
from slidejunction.references import ReferenceValidationResult, validate_references
from slidejunction.resolver import resolve_presentation


def _theme(*, preset: ThemePreset | None = None) -> Theme:
    return Theme(
        preset=preset or ThemePreset(name="slidejunction-default", version=1),
    )


def _layout(**kwargs) -> LayoutDocument:
    return LayoutDocument(format_version=1, theme=_theme(), **kwargs)


def _files(root: Path, *, source_text: str, layout_text: str) -> ProjectFileSnapshot:
    settings = ProjectManifestSnapshot(
        format_version=1,
        source="slides.md",
        layout="layout.json",
        theme="theme.css",
        assets="assets",
    )
    return ProjectFileSnapshot(
        root=root,
        manifest_settings=settings,
        manifest=LoadedTextFile(
            path=root / "deck.toml",
            target_path=root / "deck.toml",
            text="manifest",
        ),
        source=LoadedTextFile(
            path=root / "slides.md",
            target_path=root / "slides.md",
            text=source_text,
        ),
        layout=LoadedTextFile(
            path=root / "layout.json",
            target_path=root / "layout.json",
            text=layout_text,
        ),
        theme=LoadedTextFile(
            path=root / "theme.css",
            target_path=root / "theme.css",
            text="theme",
        ),
        entrypoint_target_path=root / "deck.py",
        assets_path=root / "assets",
        assets_target_path=root / "assets",
    )


def _snapshot(root: Path) -> tuple[DeckSnapshot, DeckLoadResult]:
    layout = _layout()
    layout_text = dump_layout(layout)
    files = _files(root, source_text="## Slide\n", layout_text=layout_text)
    source = parse_markdown(files.source.text, path=files.source.path)
    layout_result = parse_layout(layout_text, path=files.layout.path)
    assert layout_result.document is not None
    validation = validate_references(
        source,
        layout_result.document,
        layout_path=files.layout.path,
    )
    resolved = resolve_presentation(
        source,
        layout_result.document,
        validation.index,
    )
    snapshot = DeckSnapshot(
        files=files,
        source_document=source,
        layout_result=layout_result,
        reference_validation=validation,
        resolved_presentation=resolved,
    )
    return snapshot, DeckLoadResult(
        files=files,
        source_document=source,
        layout_result=layout_result,
        snapshot=snapshot,
    )


def _diagnostic(
    code: str,
    severity: DiagnosticSeverity,
    *,
    source: bool,
) -> Diagnostic:
    if source:
        span = SourceSpan(
            start_offset=0,
            end_offset=0,
            start_line=0,
            start_column=0,
            end_line=0,
            end_column=0,
        )
        return Diagnostic(
            severity=severity,
            code=code,
            message=code,
            source_span=span,
        )
    return Diagnostic(
        severity=severity,
        code=code,
        message=code,
        config_pointer=ConfigPointer(pointer=""),
    )


def test_project_models_are_module_scoped_frozen_keyword_only_values(
    tmp_path: Path,
) -> None:
    settings = ProjectManifestSnapshot(
        format_version=1,
        source="slides.md",
        layout="layout.json",
        theme="theme.css",
        assets="assets",
    )

    assert project.__all__ == [
        "DeckLoadResult",
        "DeckSnapshot",
        "LoadedTextFile",
        "ProjectFileSnapshot",
        "ProjectManifestSnapshot",
        "StaleDeckSnapshotError",
    ]
    assert issubclass(StaleDeckSnapshotError, RuntimeError)
    assert not hasattr(settings, "__dict__")
    with pytest.raises(FrozenInstanceError):
        settings.source = "other.md"  # type: ignore[misc]
    with pytest.raises(TypeError):
        ProjectManifestSnapshot(  # type: ignore[misc]
            1,
            "slides.md",
            "layout.json",
            "theme.css",
            "assets",
        )


@pytest.mark.parametrize(
    ("factory", "error_type"),
    [
        (
            lambda: ProjectManifestSnapshot(
                format_version=True,
                source="slides.md",
                layout="layout.json",
                theme="theme.css",
                assets="assets",
            ),
            TypeError,
        ),
        (
            lambda: ProjectManifestSnapshot(
                format_version=2,
                source="slides.md",
                layout="layout.json",
                theme="theme.css",
                assets="assets",
            ),
            ValueError,
        ),
        (
            lambda: ProjectManifestSnapshot(
                format_version=1,
                source="",
                layout="layout.json",
                theme="theme.css",
                assets="assets",
            ),
            ValueError,
        ),
        (
            lambda: LoadedTextFile(
                path=Path("relative.md"),
                target_path=Path("/project/relative.md"),
                text="",
            ),
            ValueError,
        ),
        (
            lambda: LoadedTextFile(
                path=Path("/project/slides.md"),
                target_path=Path("/project/slides.md"),
                text=b"bytes",  # type: ignore[arg-type]
            ),
            TypeError,
        ),
    ],
)
def test_leaf_project_models_validate_types_and_values(factory, error_type) -> None:
    with pytest.raises(error_type):
        factory()


def test_file_snapshot_derives_and_validates_logical_paths(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    files = _files(root, source_text="", layout_text="{}")

    assert files.entrypoint_path == root / "deck.py"
    with pytest.raises(ValueError, match="source logical path"):
        replace(
            files,
            source=replace(files.source, path=root / "other.md"),
        )
    with pytest.raises(ValueError, match="remain within"):
        replace(
            files,
            manifest_settings=replace(files.manifest_settings, source="../outside.md"),
        )
    with pytest.raises(ValueError, match="must be distinct"):
        replace(
            files,
            manifest_settings=replace(files.manifest_settings, source="deck.py"),
            source=replace(files.source, path=root / "deck.py"),
        )


def test_deck_snapshot_validates_cross_stage_identity(tmp_path: Path) -> None:
    snapshot, _ = _snapshot(tmp_path.resolve())

    assert snapshot.layout_document is snapshot.layout_result.document
    foreign_source = parse_markdown(
        snapshot.files.source.text,
        path=snapshot.files.source.path,
    )
    foreign_resolved = resolve_presentation(
        foreign_source,
        snapshot.layout_document,
        validate_references(foreign_source, snapshot.layout_document).index,
    )
    with pytest.raises(ValueError, match="Resolved presentation"):
        replace(snapshot, resolved_presentation=foreign_resolved)

    foreign_layout = _layout(configurations={3: Configuration()})
    foreign_validation = validate_references(
        snapshot.source_document,
        foreign_layout,
    )
    with pytest.raises(ValueError, match="does not match"):
        replace(snapshot, reference_validation=foreign_validation)


def test_load_result_requires_fatal_or_nonfatal_snapshot_shape(tmp_path: Path) -> None:
    snapshot, result = _snapshot(tmp_path.resolve())

    assert result.snapshot is snapshot
    with pytest.raises(ValueError, match="requires a DeckSnapshot"):
        replace(result, snapshot=None)
    with pytest.raises(ValueError, match="same file snapshot"):
        DeckLoadResult(
            files=replace(result.files),
            source_document=result.source_document,
            layout_result=result.layout_result,
            snapshot=snapshot,
        )

    fatal = LayoutLoadResult(
        document=None,
        diagnostics=(
            _diagnostic(
                "invalid-layout-json",
                DiagnosticSeverity.ERROR,
                source=False,
            ),
        ),
    )
    fatal_result = DeckLoadResult(
        files=result.files,
        source_document=result.source_document,
        layout_result=fatal,
        snapshot=None,
    )
    assert fatal_result.snapshot is None
    assert fatal_result.has_errors
    with pytest.raises(ValueError, match="fatal layout"):
        replace(fatal_result, snapshot=snapshot)


def test_diagnostics_preserve_subsystem_order_and_error_policy(tmp_path: Path) -> None:
    snapshot, _ = _snapshot(tmp_path.resolve())
    source_diagnostic = _diagnostic(
        "source-warning",
        DiagnosticSeverity.WARNING,
        source=True,
    )
    layout_diagnostic = _diagnostic(
        "layout-error",
        DiagnosticSeverity.ERROR,
        source=False,
    )
    reference_diagnostic = _diagnostic(
        "reference-info",
        DiagnosticSeverity.INFO,
        source=False,
    )
    source = replace(
        snapshot.source_document,
        presentation=replace(
            snapshot.source_document.presentation,
            diagnostics=(source_diagnostic,),
        ),
    )
    validation = ReferenceValidationResult(
        index=validate_references(source, snapshot.layout_document).index,
        diagnostics=(reference_diagnostic,),
    )
    layout_result = LayoutLoadResult(
        document=snapshot.layout_document,
        diagnostics=(layout_diagnostic,),
    )
    resolved = resolve_presentation(source, snapshot.layout_document, validation.index)
    decorated = DeckSnapshot(
        files=replace(
            snapshot.files,
            source=replace(snapshot.files.source, text=source.text),
        ),
        source_document=source,
        layout_result=layout_result,
        reference_validation=validation,
        resolved_presentation=resolved,
    )
    result = DeckLoadResult(
        files=decorated.files,
        source_document=source,
        layout_result=layout_result,
        snapshot=decorated,
    )

    assert decorated.diagnostics == (
        source_diagnostic,
        layout_diagnostic,
        reference_diagnostic,
    )
    assert result.diagnostics == decorated.diagnostics
    assert decorated.has_errors
    assert result.has_errors


def test_canonical_layout_normalizes_sparse_empty_containers() -> None:
    candidate = _layout(configurations={3: Configuration(size=Size())})

    canonical = _canonicalize_layout(candidate, path=Path("/project/layout.json"))

    assert canonical.document == _layout(configurations={3: Configuration()})
    assert canonical.document != candidate
    assert dump_layout(canonical.document) == canonical.text
    assert canonical.load_result.document is canonical.document


def test_canonical_layout_allows_stable_diagnostics_and_rejects_data_loss() -> None:
    future_preset = LayoutDocument(
        format_version=1,
        theme=_theme(preset=ThemePreset(name="slidejunction-default", version=99)),
    )
    canonical = _canonicalize_layout(
        future_preset,
        path=Path("/project/layout.json"),
    )
    assert [item.code for item in canonical.load_result.diagnostics] == [
        "unsupported-theme-preset-version"
    ]

    lossy = _layout(
        configurations={
            3: Configuration(typography=Typography(color=ThemeColor("undefined-token")))
        }
    )
    with pytest.raises(ValueError, match="round-trip stable"):
        _canonicalize_layout(lossy, path=Path("/project/layout.json"))
