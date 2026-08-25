import runpy
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from slidejunction import Deck

_PROJECT_ENTRY_NAMES = {
    "deck.toml",
    "deck.py",
    "slides.md",
    "theme.css",
    "layout.css",
    "assets",
}


def test_direct_construction_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(
        TypeError,
        match=(
            r"^Deck cannot be constructed directly; "
            r"use Deck\.init\(\) or Deck\.open\(\)\.$"
        ),
    ):
        Deck(tmp_path)


def test_init_canonicalizes_relative_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    deck = Deck.init(Path("relative/project"))

    assert deck.root == (tmp_path / "relative/project").resolve()
    assert deck.root.is_absolute()


def test_init_expands_user_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    deck = Deck.init(Path("~/project"))

    assert deck.root == (tmp_path / "project").resolve()


def test_init_creates_minimal_project_in_nested_path(tmp_path: Path) -> None:
    project_path = tmp_path / "talks" / "my-talk"

    deck = Deck.init(project_path)

    assert isinstance(deck, Deck)
    assert deck.root == project_path.resolve()
    assert {entry.name for entry in project_path.iterdir()} == _PROJECT_ENTRY_NAMES
    assert (project_path / "assets").is_dir()
    assert not any((project_path / "assets").iterdir())

    with (project_path / "deck.toml").open("rb") as deck_config:
        config = tomllib.load(deck_config)
    assert config["deck"] == {
        "format_version": 1,
        "source": "slides.md",
        "theme": "theme.css",
        "layout": "layout.css",
        "assets": "assets",
    }

    expected_contents = {
        "deck.py": (
            '"""Python control entry point for this SlideJunction presentation."""\n'
            "\n"
            "from slidejunction import Deck\n"
            "\n"
            "deck = Deck.open(__file__)\n"
        ),
        "slides.md": "# Untitled Presentation\n",
        "theme.css": "/* SlideJunction presentation theme */\n",
        "layout.css": "/* Slide-specific layout overrides */\n",
    }
    for name, expected_content in expected_contents.items():
        assert (project_path / name).read_text(encoding="utf-8") == expected_content

    for name in ("deck.toml", *expected_contents):
        assert (project_path / name).read_bytes().endswith(b"\n")


def test_generated_deck_exposes_opened_deck_object(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root

    namespace = runpy.run_path(str(project / "deck.py"))

    deck = namespace["deck"]
    assert isinstance(deck, Deck)
    assert deck.root == project


def test_generated_deck_executes_outside_project_directory(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    working_directory = tmp_path / "outside-project"
    working_directory.mkdir()

    completed = subprocess.run(
        [sys.executable, str(project / "deck.py")],
        cwd=working_directory,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0


def test_init_accepts_existing_empty_directory(tmp_path: Path) -> None:
    project_path = tmp_path / "my-talk"
    project_path.mkdir()

    deck = Deck.init(project_path)

    assert deck.root == project_path.resolve()
    assert {entry.name for entry in project_path.iterdir()} == _PROJECT_ENTRY_NAMES


def test_init_preserves_unrelated_existing_entries(tmp_path: Path) -> None:
    project_path = tmp_path / "my-talk"
    project_path.mkdir()
    notes = project_path / "notes.txt"
    notes.write_text("Keep this content.\n", encoding="utf-8")
    unrelated_directory = project_path / "references"
    unrelated_directory.mkdir()

    Deck.init(project_path)

    assert notes.read_text(encoding="utf-8") == "Keep this content.\n"
    assert unrelated_directory.is_dir()
    assert not any(unrelated_directory.iterdir())


def test_init_resolves_directory_symlink(tmp_path: Path) -> None:
    real_path = tmp_path / "real-project"
    real_path.mkdir()
    linked_path = tmp_path / "linked-project"
    _create_symlink_or_skip(linked_path, real_path, target_is_directory=True)

    deck = Deck.init(linked_path)

    assert deck.root == real_path.resolve()
    assert (real_path / "deck.toml").is_file()


def test_init_rejects_broken_root_symlink(tmp_path: Path) -> None:
    missing_target = tmp_path / "missing-project"
    linked_path = tmp_path / "broken-project"
    _create_symlink_or_skip(linked_path, missing_target, target_is_directory=True)

    with pytest.raises(FileExistsError):
        Deck.init(linked_path)

    assert linked_path.is_symlink()
    assert not missing_target.exists()


def test_init_rejects_file_symlink_as_root(tmp_path: Path) -> None:
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("Existing project data.\n", encoding="utf-8")
    linked_path = tmp_path / "linked-project"
    _create_symlink_or_skip(linked_path, existing_file)

    with pytest.raises(FileExistsError):
        Deck.init(linked_path)

    assert linked_path.is_symlink()
    assert existing_file.read_text(encoding="utf-8") == "Existing project data.\n"


@pytest.mark.parametrize("entry_name", sorted(_PROJECT_ENTRY_NAMES))
@pytest.mark.parametrize(
    "collision_kind", ["file", "directory", "symlink", "broken-symlink"]
)
def test_init_rejects_generated_entry_collisions_before_writing(
    tmp_path: Path,
    entry_name: str,
    collision_kind: str,
) -> None:
    project_path = tmp_path / "my-talk"
    project_path.mkdir()
    collision = project_path / entry_name
    if collision_kind == "file":
        collision.write_text("Existing content.\n", encoding="utf-8")
    elif collision_kind == "directory":
        collision.mkdir()
    elif collision_kind == "symlink":
        existing_target = tmp_path / f"existing-{entry_name}"
        existing_target.write_text("Symlink target.\n", encoding="utf-8")
        _create_symlink_or_skip(collision, existing_target)
    else:
        missing_target = tmp_path / f"missing-{entry_name}"
        _create_symlink_or_skip(collision, missing_target)

    unrelated = project_path / "unrelated.txt"
    unrelated.write_text("Preserve me.\n", encoding="utf-8")
    entries_before = set(project_path.iterdir())

    with pytest.raises(FileExistsError):
        Deck.init(project_path)

    assert set(project_path.iterdir()) == entries_before
    assert unrelated.read_text(encoding="utf-8") == "Preserve me.\n"
    if collision_kind == "file":
        assert collision.read_text(encoding="utf-8") == "Existing content.\n"
    elif collision_kind == "directory":
        assert collision.is_dir()
        assert not any(collision.iterdir())
    elif collision_kind == "symlink":
        assert collision.is_symlink()
        assert collision.exists()
        assert collision.read_text(encoding="utf-8") == "Symlink target.\n"
    else:
        assert collision.is_symlink()
        assert not collision.exists()


def test_init_rejects_existing_file_as_root(tmp_path: Path) -> None:
    project_path = tmp_path / "my-talk"
    project_path.write_text("Existing project data.\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        Deck.init(project_path)

    assert project_path.read_text(encoding="utf-8") == "Existing project data.\n"


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
