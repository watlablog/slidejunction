import json
from pathlib import Path

import pytest

from slidejunction import Deck
from slidejunction.project import DeckLoadResult, DeckSnapshot, ProjectFileSnapshot


def test_load_returns_exact_project_snapshot_and_derived_state(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")

    result = deck.load()

    assert isinstance(result, DeckLoadResult)
    assert isinstance(result.files, ProjectFileSnapshot)
    assert isinstance(result.snapshot, DeckSnapshot)
    assert result.files.root == deck.root
    assert result.files.manifest.path == deck.root / "deck.toml"
    assert result.files.source.path == deck.root / "slides.md"
    assert result.files.layout.path == deck.root / "layout.json"
    assert result.files.theme.path == deck.root / "theme.css"
    assert result.files.entrypoint_path == deck.root / "deck.py"
    assert result.files.assets_path == deck.root / "assets"
    assert result.files.source.text == "# Untitled Presentation\n"
    assert result.source_document.text == result.files.source.text
    assert result.snapshot.files is result.files
    assert result.snapshot.source_document is result.source_document
    assert result.snapshot.layout_result is result.layout_result
    assert result.snapshot.layout_document is result.layout_result.document
    assert (
        result.snapshot.resolved_presentation.source_document is result.source_document
    )
    assert result.diagnostics == ()
    assert result.has_errors is False


@pytest.mark.parametrize(
    "text",
    [
        "# LF\nBody\n",
        "# CRLF\r\nBody\r\n",
        "# CR\rBody\r",
        "# 終端なし",
        "# Unicode 🚀\n本文 e\u0301\n",
    ],
)
def test_load_preserves_source_text_exactly(tmp_path: Path, text: str) -> None:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / "slides.md").write_bytes(text.encode("utf-8"))

    result = deck.load()

    assert result.files.source.text == text
    assert result.source_document.text == text


def test_load_returns_fatal_layout_without_building_snapshot(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")
    source_text = "# Still parsed\r\n"
    (deck.root / "slides.md").write_bytes(source_text.encode())
    (deck.root / "layout.json").write_bytes(b"{")

    result = deck.load()

    assert result.files.layout.text == "{"
    assert result.source_document.text == source_text
    assert result.layout_result.document is None
    assert result.snapshot is None
    assert [item.code for item in result.diagnostics] == ["invalid-layout-json"]
    assert result.has_errors is True


def test_load_keeps_recoverable_layout_and_reference_diagnostics(
    tmp_path: Path,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    source = "Text </sj-format>\n\n<!-- sj:ref=8 -->\nReferenced"
    layout = {
        "format_version": 1,
        "theme": {"preset": {"name": "future-preset", "version": 7}},
        "configurations": {},
        "inline_formats": {},
    }
    (deck.root / "slides.md").write_text(source, encoding="utf-8")
    (deck.root / "layout.json").write_text(json.dumps(layout), encoding="utf-8")

    result = deck.load()

    assert result.snapshot is not None
    assert [item.code for item in result.diagnostics] == [
        "unexpected-inline-format-close",
        "unknown-theme-preset",
        "missing-configuration-ref",
    ]
    assert result.snapshot.diagnostics == result.diagnostics
    assert result.has_errors is True
    assert result.snapshot.has_errors is True


def test_load_uses_logical_paths_for_diagnostic_provenance(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / "layout.json").write_text("{", encoding="utf-8")

    result = deck.load()

    pointer = result.layout_result.diagnostics[0].config_pointer
    assert pointer is not None
    assert pointer.path == deck.root / "layout.json"
    assert result.source_document.path == deck.root / "slides.md"


def test_repeated_loads_are_fresh_and_observe_external_edits(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")
    first = deck.load()
    (deck.root / "slides.md").write_text("# Changed\n", encoding="utf-8")

    second = deck.load()

    assert second is not first
    assert second.files is not first.files
    assert second.source_document is not first.source_document
    assert second.snapshot is not first.snapshot
    assert first.source_document.text == "# Untitled Presentation\n"
    assert second.source_document.text == "# Changed\n"
    assert not hasattr(deck, "source_document")
    assert not hasattr(deck, "layout_document")
    assert not hasattr(deck, "resolved_presentation")


@pytest.mark.parametrize(
    "entry", ["deck.toml", "slides.md", "layout.json", "theme.css"]
)
def test_load_rejects_invalid_utf8_text_inputs(tmp_path: Path, entry: str) -> None:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / entry).write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        deck.load()


def test_load_records_external_symlink_targets(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = deck.root / "slides.md"
    target = tmp_path / "external.md"
    logical.replace(target)
    _symlink_or_skip(logical, target)

    result = deck.load()

    assert result.files.source.path == logical
    assert result.files.source.target_path == target.resolve()
    assert result.files.source.text == "# Untitled Presentation\n"


def test_layout_suffix_is_not_restricted_and_legacy_css_is_not_migrated(
    tmp_path: Path,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    layout = deck.root / "layout.json"
    alternate = deck.root / "state.data"
    layout.replace(alternate)
    _replace_manifest_layout(deck.root, "state.data")

    assert Deck.open(deck.root).load().snapshot is not None

    alternate.replace(deck.root / "layout.css")
    (deck.root / "layout.css").write_text("/* legacy layout CSS */\n", encoding="utf-8")
    _replace_manifest_layout(deck.root, "layout.css")

    legacy = Deck.open(deck.root).load()
    assert legacy.snapshot is None
    assert (deck.root / "layout.css").read_text(encoding="utf-8") == (
        "/* legacy layout CSS */\n"
    )
    assert not (deck.root / "layout.json").exists()


def _replace_manifest_layout(root: Path, value: str) -> None:
    manifest = (root / "deck.toml").read_text(encoding="utf-8")
    manifest = manifest.replace('layout = "layout.json"', f'layout = "{value}"')
    manifest = manifest.replace('layout = "state.data"', f'layout = "{value}"')
    (root / "deck.toml").write_text(manifest, encoding="utf-8")


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
