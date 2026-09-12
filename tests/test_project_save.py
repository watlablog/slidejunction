import errno
import json
import math
import os
import stat
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

import slidejunction._project_io as project_io
from slidejunction import Deck
from slidejunction.document import Diagnostic, DiagnosticSeverity, Presentation, Slide
from slidejunction.layout import (
    Configuration,
    Crop,
    ImageMedia,
    LayoutDocument,
    MediaFit,
    Size,
    Stacking,
    Theme,
    ThemeColor,
    ThemePreset,
    Typography,
    dump_layout,
)
from slidejunction.project import DeckSnapshot, StaleDeckSnapshotError
from slidejunction.reference_editing import (
    ReferenceEditResult,
    SourceReferenceChange,
    detach_reference,
    edit_consumer_locally,
    edit_shared_definition,
    set_consumer_reference,
)
from slidejunction.references import validate_references
from slidejunction.resolver import resolve_presentation


def test_save_layout_writes_canonical_layout_only_and_reloads(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    source_bytes = base.files.source.path.read_bytes()
    candidate = replace(
        base.layout_document,
        configurations={3: Configuration(stacking=Stacking(z_index=7))},
    )

    result = deck.save_layout(base, candidate)

    assert base.files.source.path.read_bytes() == source_bytes
    assert base.files.layout.path.read_text(encoding="utf-8") == dump_layout(candidate)
    assert result.snapshot is not None
    assert result.snapshot is not base
    assert result.snapshot.layout_document == candidate
    assert result.source_document is not base.source_document


def test_save_layout_preserves_negative_zero_as_distinct_canonical_state(
    tmp_path: Path,
) -> None:
    layout = _layout(
        configurations={
            3: Configuration(media=ImageMedia(crop=Crop(x=0.0))),
        }
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout)
    candidate = replace(
        base.layout_document,
        configurations={
            3: Configuration(media=ImageMedia(crop=Crop(x=-0.0))),
        },
    )

    saved = deck.save_layout(base, candidate)

    assert '"x": -0.0' in saved.files.layout.text
    stored_x = saved.snapshot.layout_document.configurations[3].media.crop.x
    assert stored_x == 0.0
    assert math.copysign(1.0, stored_x) == -1.0


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("save_layout", (None, None)),
        ("save_reference_edit", (None, None)),
    ],
)
def test_save_validates_public_argument_types(
    tmp_path: Path,
    method: str,
    arguments: tuple[object, object],
) -> None:
    deck = Deck.init(tmp_path / "talk")

    with pytest.raises(TypeError):
        getattr(deck, method)(*arguments)


def test_save_rejects_snapshot_from_another_project(tmp_path: Path) -> None:
    first, base = _loaded_project(tmp_path / "first", "Paragraph")
    second = Deck.init(tmp_path / "second" / "talk")

    with pytest.raises(StaleDeckSnapshotError, match="different project root"):
        second.save_layout(base, base.layout_document)
    assert first.root != second.root


def test_save_definition_edit_preserves_source_bytes(tmp_path: Path) -> None:
    layout = _layout(configurations={3: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    consumer = _first_block(base)
    source_bytes = base.files.source.path.read_bytes()
    edit = edit_shared_definition(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        consumer,
        editor=lambda value: replace(value, stacking=Stacking(z_index=-5)),
    )

    result = deck.save_reference_edit(base, edit)

    assert base.files.source.path.read_bytes() == source_bytes
    assert result.snapshot.layout_document.configurations[3].stacking == Stacking(
        z_index=-5
    )


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_save_existing_retarget_changes_source_only(
    tmp_path: Path,
    line_ending: str,
) -> None:
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        f"<!-- sj:ref=3 -->{line_ending}Paragraph{line_ending}",
        layout,
    )
    layout_bytes = base.files.layout.path.read_bytes()
    edit = set_consumer_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        ref_id=8,
    )

    result = deck.save_reference_edit(base, edit)

    assert base.files.source.path.read_bytes() == (
        f"<!-- sj:ref=8 -->{line_ending}Paragraph{line_ending}".encode()
    )
    assert base.files.layout.path.read_bytes() == layout_bytes
    assert _first_block(result.snapshot).config_ref == 8


def test_save_detach_allows_recovered_layout_and_preserves_raw_bytes(
    tmp_path: Path,
) -> None:
    raw_layout = json.dumps(
        {
            "format_version": 1,
            "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
            "configurations": {"3": {"unknown": True}},
        },
        separators=(",", ":"),
    )
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout_text=raw_layout,
    )
    assert base.layout_result.diagnostics
    edit = detach_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
    )

    result = deck.save_reference_edit(base, edit)

    assert base.files.layout.path.read_text(encoding="utf-8") == raw_layout
    assert base.files.source.path.read_text(encoding="utf-8") == "\nParagraph"
    assert _first_block(result.snapshot).config_ref is None


def test_save_new_attach_commits_layout_before_source_and_reloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=4)),
    )
    calls: list[str] = []
    original_stage = project_io._stage_utf8_text
    original_replace = project_io._replace_staged_text

    def recording_stage(target_path: Path, text: str):
        calls.append(f"stage:{target_path.name}")
        return original_stage(target_path, text)

    def recording_replace(staged):
        calls.append(f"replace:{staged.target_path.name}")
        return original_replace(staged)

    monkeypatch.setattr("slidejunction.deck._stage_utf8_text", recording_stage)
    monkeypatch.setattr("slidejunction.deck._replace_staged_text", recording_replace)

    result = deck.save_reference_edit(base, edit)

    assert calls == [
        "stage:layout.json",
        "stage:slides.md",
        "replace:layout.json",
        "replace:slides.md",
    ]
    assert base.files.source.path.read_text(encoding="utf-8") == (
        "<!-- sj:ref=1 -->\nParagraph"
    )
    assert result.snapshot.layout_document.configurations[1].stacking == Stacking(
        z_index=4
    )
    assert _first_block(result.snapshot).config_ref == 1


def test_canonical_empty_nested_change_does_not_rewrite_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_layout = json.dumps(
        {
            "format_version": 1,
            "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
            "configurations": {"3": {}},
        },
        separators=(",", ":"),
    )
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout_text=raw_layout,
    )
    edit = edit_shared_definition(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, size=Size()),
    )

    def forbidden_stage(*args, **kwargs):
        pytest.fail("Canonical-equal layout must not be staged")

    monkeypatch.setattr("slidejunction.deck._stage_utf8_text", forbidden_stage)
    result = deck.save_reference_edit(base, edit)

    assert base.files.layout.path.read_text(encoding="utf-8") == raw_layout
    assert result.snapshot.layout_document == base.layout_document


@pytest.mark.parametrize(
    ("name", "version", "code"),
    [
        ("future-preset", 1, "unknown-theme-preset"),
        ("slidejunction-default", 99, "unsupported-theme-preset-version"),
    ],
)
def test_round_trip_stable_layout_diagnostics_are_persistable(
    tmp_path: Path,
    name: str,
    version: int,
    code: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    candidate = replace(
        base.layout_document,
        theme=Theme(preset=ThemePreset(name=name, version=version)),
    )

    result = deck.save_layout(base, candidate)

    assert result.snapshot is not None
    assert result.snapshot.layout_document.theme.preset == candidate.theme.preset
    assert code in {item.code for item in result.diagnostics}


def test_round_trip_unstable_layout_is_rejected_before_disk_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    baseline = base.files.layout.path.read_bytes()
    candidate = replace(
        base.layout_document,
        configurations={
            3: Configuration(typography=Typography(color=ThemeColor("missing-token")))
        },
    )

    def forbidden(*args, **kwargs):
        pytest.fail("An unstable writer/parser boundary must not touch disk")

    monkeypatch.setattr("slidejunction.deck._require_current_project_files", forbidden)
    with pytest.raises(ValueError, match="round-trip stable"):
        deck.save_layout(base, candidate)
    assert base.files.layout.path.read_bytes() == baseline


def test_recovered_layout_cannot_be_overwritten(tmp_path: Path) -> None:
    raw_layout = json.dumps(
        {
            "format_version": 1,
            "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
            "unexpected": True,
        }
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout_text=raw_layout)
    candidate = replace(
        base.layout_document,
        configurations={9: Configuration()},
    )

    with pytest.raises(ValueError, match="recovered layout"):
        deck.save_layout(base, candidate)

    assert base.files.layout.path.read_text(encoding="utf-8") == raw_layout


@pytest.mark.parametrize("fabrication", ["tree", "diagnostic", "config-ref", "span"])
def test_all_saves_reject_fabricated_source_snapshot(
    tmp_path: Path,
    fabrication: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    source = base.source_document
    slide = source.presentation.items[0]
    assert isinstance(slide, Slide)
    block = slide.blocks[0]
    if fabrication == "tree":
        presentation = Presentation(items=(), diagnostics=())
    elif fabrication == "diagnostic":
        diagnostic = Diagnostic(
            severity=DiagnosticSeverity.WARNING,
            code="fabricated",
            message="not parsed",
            source_span=block.source_binding.syntax_span,
        )
        presentation = replace(source.presentation, diagnostics=(diagnostic,))
    else:
        if fabrication == "config-ref":
            replacement_block = replace(block, config_ref=77)
        else:
            span = block.source_binding.syntax_span
            replacement_span = replace(span, end_column=span.end_column + 1)
            replacement_block = replace(
                block,
                source_binding=replace(
                    block.source_binding,
                    syntax_span=replacement_span,
                ),
            )
        presentation = replace(
            source.presentation,
            items=(replace(slide, blocks=(replacement_block,)),),
        )
    fabricated_source = replace(source, presentation=presentation)
    fabricated = _snapshot_with_source(base, fabricated_source)

    with pytest.raises(ValueError, match="source document"):
        deck.save_layout(fabricated, fabricated.layout_document)


def test_definition_edit_rejects_fabricated_source_snapshot(tmp_path: Path) -> None:
    layout = _layout(configurations={3: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="fabricated",
        message="not parsed",
        source_span=_first_block(base).source_binding.syntax_span,
    )
    source = replace(
        base.source_document,
        presentation=replace(
            base.source_document.presentation,
            diagnostics=(diagnostic,),
        ),
    )
    fabricated = _snapshot_with_source(base, source)
    edit = edit_shared_definition(
        fabricated.source_document,
        fabricated.layout_document,
        fabricated.reference_validation.index,
        _first_block(fabricated),
        editor=lambda value: replace(value, stacking=Stacking(z_index=2)),
    )

    with pytest.raises(ValueError, match="source document"):
        deck.save_reference_edit(fabricated, edit)


def test_save_rejects_fabricated_layout_result_even_for_noop(tmp_path: Path) -> None:
    raw_layout = json.dumps(
        {
            "format_version": 1,
            "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
            "unexpected": True,
        }
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout_text=raw_layout)
    fabricated_result = replace(base.layout_result, diagnostics=())
    fabricated = replace(base, layout_result=fabricated_result)

    with pytest.raises(ValueError, match="layout result"):
        deck.save_layout(fabricated, fabricated.layout_document)


def test_save_rejects_type_coerced_source_span_even_for_noop(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    source = base.source_document
    slide = source.presentation.items[0]
    assert isinstance(slide, Slide)
    block = slide.blocks[0]
    span = block.source_binding.syntax_span
    assert span.start_offset == 0
    forged_block = replace(
        block,
        source_binding=replace(
            block.source_binding,
            syntax_span=replace(span, start_offset=False),
        ),
    )
    forged_source = replace(
        source,
        presentation=replace(
            source.presentation,
            items=(replace(slide, blocks=(forged_block,)),),
        ),
    )
    forged = _snapshot_with_source(base, forged_source)

    with pytest.raises(ValueError, match="source document"):
        deck.save_layout(forged, forged.layout_document)


def test_save_rejects_type_coerced_layout_provenance(tmp_path: Path) -> None:
    layout = _layout(
        configurations={3: Configuration(size=Size(width=1))},
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout)
    forged_document = replace(
        base.layout_document,
        configurations={3: Configuration(size=Size(width=1.0))},
    )
    forged = _snapshot_with_layout(base, forged_document)

    with pytest.raises(ValueError, match="layout result"):
        deck.save_layout(forged, forged.layout_document)


def test_new_reference_cannot_smuggle_type_change_to_existing_definition(
    tmp_path: Path,
) -> None:
    layout = _layout(
        configurations={3: Configuration(size=Size(width=1))},
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout)
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=2)),
    )
    candidate = replace(
        edit.layout_document,
        configurations={
            3: Configuration(size=Size(width=1.0)),
            edit.selected_ref_id: edit.layout_document.configurations[
                edit.selected_ref_id
            ],
        },
    )
    forged_edit = replace(edit, layout_document=candidate)

    with pytest.raises(ValueError, match="exactly one matching definition"):
        deck.save_reference_edit(base, forged_edit)


@pytest.mark.parametrize("changed", ["source", "layout"])
def test_save_rejects_external_source_or_layout_change(
    tmp_path: Path,
    changed: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    path = base.files.source.path if changed == "source" else base.files.layout.path
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


def test_manifest_formatting_and_theme_or_asset_contents_do_not_block_save(
    tmp_path: Path,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    manifest = base.files.manifest.path
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + '\n[metadata]\ntitle = "Talk"\n',
        encoding="utf-8",
    )
    base.files.theme.path.write_text("/* edited externally */\n", encoding="utf-8")
    (base.files.assets_path / "new.txt").write_text("asset", encoding="utf-8")

    result = deck.save_layout(base, base.layout_document)

    assert result.files.theme.text == "/* edited externally */\n"
    assert (result.files.assets_path / "new.txt").read_text(encoding="utf-8") == "asset"


def test_manifest_setting_change_is_stale_even_when_target_content_matches(
    tmp_path: Path,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    duplicate = deck.root / "copy.md"
    duplicate.write_bytes(base.files.source.path.read_bytes())
    manifest = base.files.manifest.path
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'source = "slides.md"', 'source = "copy.md"'
        ),
        encoding="utf-8",
    )

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


def test_manifest_change_to_overlong_required_path_is_stale(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    manifest = base.files.manifest.path
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'source = "slides.md"',
            'source = "' + "x" * 10_000 + '"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


@pytest.mark.parametrize("changed", ["source", "layout"])
def test_symlink_retarget_after_load_is_stale(
    tmp_path: Path,
    changed: str,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = deck.root / ("slides.md" if changed == "source" else "layout.json")
    first_target = tmp_path / f"first-{logical.name}"
    logical.replace(first_target)
    _symlink_or_skip(logical, first_target)
    loaded = deck.load()
    assert loaded.snapshot is not None

    second_target = tmp_path / f"second-{logical.name}"
    second_target.write_bytes(first_target.read_bytes())
    logical.unlink()
    _symlink_or_skip(logical, second_target)

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(loaded.snapshot, loaded.snapshot.layout_document)


@pytest.mark.parametrize("changed", ["entrypoint", "theme", "assets"])
def test_unedited_required_target_change_is_stale(
    tmp_path: Path,
    changed: str,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = {
        "entrypoint": deck.root / "deck.py",
        "theme": deck.root / "theme.css",
        "assets": deck.root / "assets",
    }[changed]
    first_target = tmp_path / f"first-{logical.name}"
    logical.replace(first_target)
    _symlink_or_skip(
        logical,
        first_target,
        target_is_directory=changed == "assets",
    )
    loaded = deck.load()
    assert loaded.snapshot is not None

    second_target = tmp_path / f"second-{logical.name}"
    if changed == "assets":
        second_target.mkdir()
    else:
        second_target.write_bytes(first_target.read_bytes())
    logical.unlink()
    _symlink_or_skip(
        logical,
        second_target,
        target_is_directory=changed == "assets",
    )

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(loaded.snapshot, loaded.snapshot.layout_document)


def test_required_file_alias_introduced_after_load_is_stale(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    theme = base.files.theme.path
    theme.unlink()
    _symlink_or_skip(theme, base.files.source.target_path)

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


@pytest.mark.parametrize("timing", ["preflight", "post-save"])
def test_required_symlink_self_loop_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    timing: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")

    def make_self_loop() -> None:
        source = base.files.source.path
        source.unlink()
        _symlink_or_skip(source, Path(source.name))

    if timing == "preflight":
        make_self_loop()
    else:
        original_load = Deck.load

        def loop_then_load(self: Deck):
            make_self_loop()
            return original_load(self)

        monkeypatch.setattr(Deck, "load", loop_then_load)

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


def test_required_entry_failure_during_post_save_reload_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    original_load = Deck.load

    def remove_source_then_load(self: Deck):
        base.files.source.path.unlink()
        return original_load(self)

    monkeypatch.setattr(Deck, "load", remove_source_then_load)

    with pytest.raises(StaleDeckSnapshotError, match="post-save reload"):
        deck.save_layout(base, base.layout_document)


def test_post_save_intended_text_mismatch_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    original_load = Deck.load

    def change_source_then_load(self: Deck):
        base.files.source.path.write_text("Externally changed", encoding="utf-8")
        return original_load(self)

    monkeypatch.setattr(Deck, "load", change_source_then_load)

    with pytest.raises(StaleDeckSnapshotError, match="intended text"):
        deck.save_layout(base, base.layout_document)


@pytest.mark.parametrize("failure", ["utf8", "toml"])
def test_post_save_utf8_and_toml_decode_errors_propagate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    original_load = Deck.load

    def corrupt_then_load(self: Deck):
        if failure == "utf8":
            base.files.theme.path.write_bytes(b"\xff")
        else:
            base.files.manifest.path.write_text("[deck\n", encoding="utf-8")
        return original_load(self)

    monkeypatch.setattr(Deck, "load", corrupt_then_load)
    expected = UnicodeDecodeError if failure == "utf8" else tomllib.TOMLDecodeError

    with pytest.raises(expected):
        deck.save_layout(base, base.layout_document)


@pytest.mark.parametrize("changed", ["source", "layout"])
def test_only_changed_external_hard_link_target_is_rejected(
    tmp_path: Path,
    changed: str,
) -> None:
    layout = _layout(configurations={3: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    target = base.files.source if changed == "source" else base.files.layout
    link = tmp_path / f"{changed}-hard-link"
    try:
        os.link(target.target_path, link)
    except OSError as error:
        pytest.skip(f"Hard links are unavailable: {error}")

    deck.save_layout(base, base.layout_document)
    with pytest.raises(ValueError, match="multiple hard links"):
        if changed == "source":
            deck.save_reference_edit(
                base,
                detach_reference(
                    base.source_document,
                    base.layout_document,
                    base.reference_validation.index,
                    _first_block(base),
                ),
            )
        else:
            candidate = replace(
                base.layout_document,
                configurations={
                    **base.layout_document.configurations,
                    8: Configuration(),
                },
            )
            deck.save_layout(base, candidate)


def test_semantic_noop_stages_no_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")

    def forbidden(*_args, **_kwargs):
        pytest.fail("A semantic no-op must not stage or replace a file")

    monkeypatch.setattr("slidejunction.deck._stage_utf8_text", forbidden)
    monkeypatch.setattr("slidejunction.deck._replace_staged_text", forbidden)

    saved = deck.save_layout(base, base.layout_document)

    assert saved.snapshot is not None
    assert saved.snapshot is not base
    assert not tuple(deck.root.glob(".*.slidejunction-*.tmp"))


def test_directory_fsync_failure_after_layout_replace_propagates_without_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    candidate = replace(
        base.layout_document,
        configurations={1: Configuration(stacking=Stacking(z_index=1))},
    )
    expected_text = dump_layout(candidate)
    failure = OSError(errno.EIO, "directory fsync failed")

    def fail_fsync(directory: Path) -> None:
        raise failure

    monkeypatch.setattr(project_io, "_fsync_directory", fail_fsync)
    with pytest.raises(OSError) as captured:
        deck.save_layout(base, candidate)

    assert captured.value is failure
    assert base.files.layout.path.read_text(encoding="utf-8") == expected_text
    assert not tuple(base.files.layout.path.parent.glob(".*.slidejunction-*.tmp"))


def test_layout_fsync_failure_in_two_file_save_does_not_write_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=3)),
    )
    source_before = base.files.source.path.read_bytes()
    failure = OSError(errno.EIO, "directory fsync failed")

    def fail_fsync(directory: Path) -> None:
        raise failure

    monkeypatch.setattr(project_io, "_fsync_directory", fail_fsync)
    with pytest.raises(OSError) as captured:
        deck.save_reference_edit(base, edit)

    assert captured.value is failure
    assert base.files.source.path.read_bytes() == source_before
    loaded = deck.load()
    assert loaded.snapshot is not None
    assert 1 in loaded.snapshot.layout_document.configurations
    assert _first_block(loaded.snapshot).config_ref is None


@pytest.mark.parametrize(
    "unsupported_errno",
    sorted(
        {
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
    ),
)
def test_unsupported_directory_fsync_error_is_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsupported_errno: int,
) -> None:
    def unsupported(_descriptor: int) -> None:
        raise OSError(unsupported_errno, "directory fsync unsupported")

    monkeypatch.setattr(project_io.os, "fsync", unsupported)
    project_io._fsync_directory(tmp_path)


def test_cleanup_failure_does_not_hide_primary_commit_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=3)),
    )
    primary = OSError(errno.EIO, "replace failed")
    cleanup = OSError(errno.EACCES, "cleanup failed")
    original_unlink = Path.unlink

    def fail_replace(_staged) -> None:
        raise primary

    def fail_temp_unlink(path: Path, *args, **kwargs) -> None:
        if ".slidejunction-" in path.name:
            raise cleanup
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr("slidejunction.deck._replace_staged_text", fail_replace)
    monkeypatch.setattr(Path, "unlink", fail_temp_unlink)

    with pytest.raises(OSError) as captured:
        deck.save_reference_edit(base, edit)

    assert captured.value is primary
    for temporary in deck.root.glob(".*.slidejunction-*.tmp"):
        original_unlink(temporary)


def test_save_preserves_source_symlink_and_updates_its_external_target(
    tmp_path: Path,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = deck.root / "slides.md"
    target = tmp_path / "external-slides.md"
    logical.replace(target)
    _symlink_or_skip(logical, target)
    layout = _layout(configurations={3: Configuration()})
    target.write_text("<!-- sj:ref=3 -->\nParagraph", encoding="utf-8")
    (deck.root / "layout.json").write_text(dump_layout(layout), encoding="utf-8")
    loaded = deck.load()
    assert loaded.snapshot is not None
    base = loaded.snapshot
    edit = detach_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
    )

    deck.save_reference_edit(base, edit)

    assert logical.is_symlink()
    assert logical.resolve() == target.resolve()
    assert target.read_text(encoding="utf-8") == "\nParagraph"


def test_save_preserves_layout_symlink_target_and_permission_mode(
    tmp_path: Path,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = deck.root / "layout.json"
    target = tmp_path / "external-layout.json"
    logical.replace(target)
    _symlink_or_skip(logical, target)
    target.chmod(0o640)
    loaded = deck.load()
    assert loaded.snapshot is not None
    candidate = replace(
        loaded.snapshot.layout_document,
        configurations={1: Configuration()},
    )

    deck.save_layout(loaded.snapshot, candidate)

    assert logical.is_symlink()
    assert logical.resolve() == target.resolve()
    assert target.read_text(encoding="utf-8") == dump_layout(candidate)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_stale_change_after_staging_cleans_temp_and_preserves_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    layout_before = base.files.layout.path.read_bytes()
    candidate = replace(
        base.layout_document,
        configurations={1: Configuration()},
    )
    original_stage = project_io._stage_utf8_text

    def stage_then_change_source(target_path: Path, text: str):
        staged = original_stage(target_path, text)
        base.files.source.path.write_text("Externally changed", encoding="utf-8")
        return staged

    monkeypatch.setattr("slidejunction.deck._stage_utf8_text", stage_then_change_source)

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, candidate)

    assert base.files.layout.path.read_bytes() == layout_before
    assert not tuple(deck.root.glob(".*.slidejunction-*.tmp"))


def test_source_replace_failure_after_layout_commit_leaves_unused_definition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=5)),
    )
    source_before = base.files.source.path.read_bytes()
    original_replace = project_io._replace_staged_text
    failure = OSError(errno.EIO, "source replace failed")

    def fail_source(staged):
        if staged.target_path == base.files.source.target_path:
            raise failure
        return original_replace(staged)

    monkeypatch.setattr("slidejunction.deck._replace_staged_text", fail_source)
    with pytest.raises(OSError) as captured:
        deck.save_reference_edit(base, edit)

    assert captured.value is failure
    assert base.files.source.path.read_bytes() == source_before
    reloaded = deck.load()
    assert reloaded.snapshot is not None
    assert 1 in reloaded.snapshot.layout_document.configurations
    assert _first_block(reloaded.snapshot).config_ref is None
    assert not tuple(deck.root.glob(".*.slidejunction-*.tmp"))


def test_intermediate_stale_change_after_layout_commit_stops_source_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=5)),
    )
    original_replace = project_io._replace_staged_text

    def replace_then_change_source(staged) -> None:
        original_replace(staged)
        if staged.target_path == base.files.layout.target_path:
            base.files.source.path.write_text("Externally changed", encoding="utf-8")

    monkeypatch.setattr(
        "slidejunction.deck._replace_staged_text",
        replace_then_change_source,
    )

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_reference_edit(base, edit)

    assert base.files.source.path.read_text(encoding="utf-8") == "Externally changed"
    reloaded = deck.load()
    assert reloaded.snapshot is not None
    assert 1 in reloaded.snapshot.layout_document.configurations
    assert _first_block(reloaded.snapshot).config_ref is None


def test_persistent_writer_values_survive_save_and_reload(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    candidate = replace(
        base.layout_document,
        configurations={
            1: Configuration(
                media=ImageMedia(
                    aspect_ratio_locked=False,
                    fit=MediaFit.STRETCH,
                ),
                stacking=Stacking(z_index=0),
            ),
            2: Configuration(),
        },
    )

    saved = deck.save_layout(base, candidate)

    assert saved.snapshot is not None
    stored = saved.snapshot.layout_document.configurations
    assert stored[1].media.aspect_ratio_locked is False
    assert stored[1].media.fit is MediaFit.STRETCH
    assert stored[1].stacking.z_index == 0
    assert stored[2] == Configuration()


@pytest.mark.parametrize("mutation", ["theme", "unrelated", "delete"])
def test_reference_edit_rejects_raw_changes_outside_selected_definition(
    tmp_path: Path,
    mutation: str,
) -> None:
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    if mutation == "theme":
        candidate = replace(
            base.layout_document,
            theme=Theme(preset=ThemePreset(name="future", version=1)),
        )
    elif mutation == "unrelated":
        candidate = replace(
            base.layout_document,
            configurations={
                **base.layout_document.configurations,
                8: Configuration(stacking=Stacking(z_index=1)),
            },
        )
    else:
        candidate = replace(
            base.layout_document,
            configurations={3: base.layout_document.configurations[3]},
        )
    edit = ReferenceEditResult(
        source_document=base.source_document,
        layout_document=candidate,
        selected_consumer=_first_block(base),
        source_changes=(),
        selected_ref_id=3,
    )

    with pytest.raises(ValueError, match="outside the selected definition"):
        deck.save_reference_edit(base, edit)


def test_detach_result_cannot_smuggle_layout_change(tmp_path: Path) -> None:
    layout = _layout(configurations={3: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    consumer = _first_block(base)
    candidate = replace(
        base.layout_document,
        configurations={3: Configuration(stacking=Stacking(z_index=9))},
    )
    edit = ReferenceEditResult(
        source_document=base.source_document,
        layout_document=candidate,
        selected_consumer=consumer,
        source_changes=(SourceReferenceChange(consumer=consumer, new_ref_id=None),),
        selected_ref_id=None,
    )

    with pytest.raises(ValueError, match="source-only"):
        deck.save_reference_edit(base, edit)


def _loaded_project(
    tmp_path: Path,
    source: str,
    layout: LayoutDocument | None = None,
    *,
    layout_text: str | None = None,
) -> tuple[Deck, DeckSnapshot]:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / "slides.md").write_bytes(source.encode("utf-8"))
    if layout_text is not None:
        (deck.root / "layout.json").write_bytes(layout_text.encode("utf-8"))
    elif layout is not None:
        (deck.root / "layout.json").write_text(
            dump_layout(layout),
            encoding="utf-8",
        )
    result = deck.load()
    assert result.snapshot is not None
    return deck, result.snapshot


def _layout(
    *,
    configurations: dict[int, Configuration] | None = None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
    )


def _first_block(snapshot: DeckSnapshot):
    item = snapshot.source_document.presentation.items[0]
    assert isinstance(item, Slide)
    return item.blocks[0]


def _snapshot_with_source(
    base: DeckSnapshot,
    source,
) -> DeckSnapshot:
    validation = validate_references(
        source,
        base.layout_document,
        layout_path=base.files.layout.path,
    )
    resolved = resolve_presentation(source, base.layout_document, validation.index)
    return replace(
        base,
        source_document=source,
        reference_validation=validation,
        resolved_presentation=resolved,
    )


def _snapshot_with_layout(
    base: DeckSnapshot,
    layout: LayoutDocument,
) -> DeckSnapshot:
    layout_result = replace(base.layout_result, document=layout)
    validation = validate_references(
        base.source_document,
        layout,
        layout_path=base.files.layout.path,
    )
    resolved = resolve_presentation(
        base.source_document,
        layout,
        validation.index,
    )
    return replace(
        base,
        layout_result=layout_result,
        reference_validation=validation,
        resolved_presentation=resolved,
    )


def _symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
