import json
import tomllib
from pathlib import Path

import pytest

from slidejunction import Deck

_DEFAULT_SETTINGS = {
    "format_version": "1",
    "source": '"slides.md"',
    "theme": '"theme.css"',
    "layout": '"layout.css"',
    "assets": '"assets"',
}
_REQUIRED_ENTRIES = (
    ("deck.py", None, False),
    ("slides.md", "source", False),
    ("theme.css", "theme", False),
    ("layout.css", "layout", False),
    ("assets", "assets", True),
)


def test_open_round_trips_project_created_by_init(tmp_path: Path) -> None:
    initialized = Deck.init(tmp_path / "my-talk")

    opened = Deck.open(initialized.root)

    assert isinstance(opened, Deck)
    assert opened.root == initialized.root


@pytest.mark.parametrize("start_kind", ["root", "nested", "file", "manifest"])
def test_open_discovers_project_from_supported_positions(
    tmp_path: Path,
    start_kind: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    nested = project / "assets" / "images"
    nested.mkdir()
    starts = {
        "root": project,
        "nested": nested,
        "file": project / "slides.md",
        "manifest": project / "deck.toml",
    }

    deck = Deck.open(starts[start_kind])

    assert deck.root == project


def test_open_without_argument_discovers_from_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    nested = project / "assets" / "images"
    nested.mkdir()
    monkeypatch.chdir(nested)

    deck = Deck.open()

    assert deck.root == project


def test_open_chooses_nearest_nested_project(tmp_path: Path) -> None:
    parent = Deck.init(tmp_path / "talks").root
    child = Deck.init(parent / "demo").root

    deck = Deck.open(child / "assets")

    assert deck.root == child


def test_open_canonicalizes_relative_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    monkeypatch.chdir(tmp_path)

    deck = Deck.open(Path("my-talk/assets"))

    assert deck.root == project
    assert deck.root.is_absolute()


def test_open_resolves_directory_symlink_to_canonical_project_root(
    tmp_path: Path,
) -> None:
    project = Deck.init(tmp_path / "real-project").root
    linked_project = tmp_path / "linked-project"
    _create_symlink_or_skip(linked_project, project, target_is_directory=True)

    deck = Deck.open(linked_project / "assets")

    assert deck.root == project


def test_open_accepts_manifest_symlink_and_uses_marker_directory_as_root(
    tmp_path: Path,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    manifest = project / "deck.toml"
    external_manifest = tmp_path / "shared-deck.toml"
    manifest.replace(external_manifest)
    _create_symlink_or_skip(manifest, external_manifest)

    deck = Deck.open(manifest)

    assert deck.root == project


def test_open_allows_unknown_deck_keys_and_tables(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(
        project,
        extra_deck='title = "PyCon"\nlanguage = "ja"',
        extra_document='[metadata]\nauthor = "SlideJunction"',
    )

    deck = Deck.open(project)

    assert deck.root == project


def test_open_accepts_configured_entries_in_subdirectories(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    content = project / "content"
    styles = project / "styles"
    resources = project / "resources"
    content.mkdir()
    styles.mkdir()
    resources.mkdir()
    (project / "slides.md").replace(content / "slides.md")
    (project / "theme.css").replace(styles / "theme.css")
    (project / "layout.css").replace(styles / "layout.css")
    (project / "assets").replace(resources / "assets")
    _write_manifest(
        project,
        values={
            "source": _toml_string("content/slides.md"),
            "theme": _toml_string("styles/theme.css"),
            "layout": _toml_string("styles/layout.css"),
            "assets": _toml_string("resources/assets"),
        },
    )

    deck = Deck.open(project)

    assert deck.root == project


def test_open_accepts_lexically_normalized_path_within_root(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(
        project,
        values={"source": _toml_string("content/../slides.md")},
    )

    deck = Deck.open(project)

    assert deck.root == project


@pytest.mark.parametrize(
    ("entry_name", "setting", "is_directory"),
    _REQUIRED_ENTRIES,
)
def test_open_accepts_required_entry_symlink_to_external_target(
    tmp_path: Path,
    entry_name: str,
    setting: str | None,
    is_directory: bool,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    entry = project / entry_name
    external_target = tmp_path / f"external-{entry_name}"
    entry.replace(external_target)
    _create_symlink_or_skip(
        entry,
        external_target,
        target_is_directory=is_directory,
    )

    deck = Deck.open(project)

    assert deck.root == project


@pytest.mark.parametrize("input_kind", ["missing", "broken-symlink"])
def test_open_rejects_missing_input_path(tmp_path: Path, input_kind: str) -> None:
    requested_path = tmp_path / "missing"
    if input_kind == "broken-symlink":
        broken_link = tmp_path / "broken"
        _create_symlink_or_skip(broken_link, requested_path)
        requested_path = broken_link

    with pytest.raises(FileNotFoundError):
        Deck.open(requested_path)


def test_open_rejects_path_without_project_marker(tmp_path: Path) -> None:
    start = tmp_path / "not-a-project" / "nested"
    start.mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        Deck.open(start)


def test_open_does_not_fall_back_from_invalid_nearest_marker(tmp_path: Path) -> None:
    parent = Deck.init(tmp_path / "talks").root
    broken_project = parent / "broken-talk"
    broken_project.mkdir()
    (broken_project / "deck.toml").write_text("[deck\n", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        Deck.open(broken_project)


@pytest.mark.parametrize(
    ("marker_kind", "expected_exception"),
    [
        ("directory", IsADirectoryError),
        ("directory-symlink", IsADirectoryError),
        ("broken-symlink", FileNotFoundError),
    ],
)
def test_open_rejects_non_file_project_marker_without_parent_fallback(
    tmp_path: Path,
    marker_kind: str,
    expected_exception: type[Exception],
) -> None:
    parent = Deck.init(tmp_path / "talks").root
    project = parent / "invalid-project"
    project.mkdir()
    marker = project / "deck.toml"
    if marker_kind == "directory":
        marker.mkdir()
    elif marker_kind == "directory-symlink":
        target = tmp_path / "marker-directory"
        target.mkdir()
        _create_symlink_or_skip(marker, target, target_is_directory=True)
    else:
        _create_symlink_or_skip(marker, tmp_path / "missing-marker")

    with pytest.raises(expected_exception):
        Deck.open(project)


def test_open_rejects_malformed_toml(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    (project / "deck.toml").write_text("[deck\n", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        Deck.open(project)


@pytest.mark.parametrize(
    "manifest_content",
    [
        'title = "Not a deck"\n',
        "deck = 1\n",
    ],
)
def test_open_requires_deck_table(
    tmp_path: Path,
    manifest_content: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    (project / "deck.toml").write_text(manifest_content, encoding="utf-8")

    with pytest.raises(ValueError):
        Deck.open(project)


@pytest.mark.parametrize("missing_key", list(_DEFAULT_SETTINGS))
def test_open_requires_all_deck_settings(tmp_path: Path, missing_key: str) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, omit={missing_key})

    with pytest.raises(ValueError):
        Deck.open(project)


@pytest.mark.parametrize(
    ("setting", "invalid_value"),
    [
        ("format_version", "true"),
        ("source", "1"),
        ("theme", "false"),
        ("layout", "[]"),
        ("assets", "{}"),
    ],
)
def test_open_rejects_wrong_setting_types(
    tmp_path: Path,
    setting: str,
    invalid_value: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, values={setting: invalid_value})

    with pytest.raises(ValueError):
        Deck.open(project)


def test_open_rejects_unsupported_format_version(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, values={"format_version": "2"})

    with pytest.raises(ValueError):
        Deck.open(project)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "",
        "/outside/slides.md",
        "../outside/slides.md",
    ],
)
def test_open_rejects_invalid_configured_path(
    tmp_path: Path,
    invalid_path: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, values={"source": _toml_string(invalid_path)})

    with pytest.raises(ValueError):
        Deck.open(project)


@pytest.mark.parametrize(
    ("entry_name", "setting", "is_directory"),
    _REQUIRED_ENTRIES,
)
@pytest.mark.parametrize("missing_kind", ["missing", "broken-symlink"])
def test_open_rejects_missing_required_entry(
    tmp_path: Path,
    entry_name: str,
    setting: str | None,
    is_directory: bool,
    missing_kind: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    entry = project / entry_name
    if is_directory:
        entry.rmdir()
    else:
        entry.unlink()
    if missing_kind == "broken-symlink":
        _create_symlink_or_skip(
            entry,
            tmp_path / f"missing-{entry_name}",
            target_is_directory=is_directory,
        )

    with pytest.raises(FileNotFoundError):
        Deck.open(project)


@pytest.mark.parametrize(
    ("entry_name", "setting", "is_directory"),
    _REQUIRED_ENTRIES,
)
@pytest.mark.parametrize("entry_kind", ["direct", "symlink"])
def test_open_rejects_required_entry_with_wrong_filesystem_type(
    tmp_path: Path,
    entry_name: str,
    setting: str | None,
    is_directory: bool,
    entry_kind: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    entry = project / entry_name
    if is_directory:
        entry.rmdir()
        wrong_target = tmp_path / f"wrong-{entry_name}"
        wrong_target.write_text("Not a directory.\n", encoding="utf-8")
        expected_exception = NotADirectoryError
    else:
        entry.unlink()
        wrong_target = tmp_path / f"wrong-{entry_name}"
        wrong_target.mkdir()
        expected_exception = IsADirectoryError

    if entry_kind == "direct":
        wrong_target.replace(entry)
    else:
        _create_symlink_or_skip(
            entry,
            wrong_target,
            target_is_directory=not is_directory,
        )

    with pytest.raises(expected_exception):
        Deck.open(project)


def _write_manifest(
    root: Path,
    *,
    values: dict[str, str] | None = None,
    omit: set[str] | None = None,
    extra_deck: str = "",
    extra_document: str = "",
) -> None:
    settings = _DEFAULT_SETTINGS | (values or {})
    omitted = omit or set()
    lines = ["[deck]"]
    lines.extend(
        f"{key} = {value}" for key, value in settings.items() if key not in omitted
    )
    if extra_deck:
        lines.append(extra_deck)
    if extra_document:
        lines.append(extra_document)
    (root / "deck.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _create_symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
