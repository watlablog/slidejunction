"""SlideJunction presentation project."""

import os
import stat
import tomllib
from pathlib import Path
from typing import Self

_PROJECT_FILES = {
    "deck.toml": (
        "[deck]\n"
        "format_version = 1\n"
        'source = "slides.md"\n'
        'theme = "theme.css"\n'
        'layout = "layout.css"\n'
        'assets = "assets"\n'
    ),
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
_ASSETS_DIRECTORY = "assets"
_PROJECT_ENTRY_NAMES = (*_PROJECT_FILES, _ASSETS_DIRECTORY)
_MANIFEST_NAME = "deck.toml"
_SUPPORTED_FORMAT_VERSION = 1
_CONFIGURED_FILE_KEYS = ("source", "theme", "layout")
_CONFIGURED_PATH_KEYS = (*_CONFIGURED_FILE_KEYS, "assets")


def _entry_exists(path: Path) -> bool:
    """Return whether a path entry exists, including a broken symlink."""
    return path.exists() or path.is_symlink()


def _discovery_start(path: str | Path) -> Path:
    """Return the canonical directory from which project discovery starts."""
    requested_path = Path(path).expanduser()
    try:
        mode = requested_path.stat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Cannot open a project from a missing path: {requested_path}"
        ) from None

    if stat.S_ISDIR(mode):
        return requested_path.resolve()
    if stat.S_ISREG(mode):
        return requested_path.parent.resolve()
    raise ValueError(f"Project discovery path must be a file or directory: {path}")


def _discover_manifest(start: Path) -> Path:
    """Find the nearest deck.toml entry at or above *start*."""
    for directory in (start, *start.parents):
        manifest = directory / _MANIFEST_NAME
        if _entry_exists(manifest):
            return manifest
    raise FileNotFoundError(f"No {_MANIFEST_NAME} found from: {start}")


def _load_manifest(manifest: Path) -> dict[str, object]:
    """Load a deck.toml marker after validating its filesystem type."""
    try:
        mode = manifest.stat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(f"Project marker is missing: {manifest}") from None

    if stat.S_ISDIR(mode):
        raise IsADirectoryError(f"Project marker must be a file: {manifest}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"Project marker must be a regular file: {manifest}")

    with manifest.open("rb") as manifest_file:
        return tomllib.load(manifest_file)


def _validate_manifest(config: dict[str, object]) -> dict[str, str]:
    """Validate and return the configured project paths."""
    deck_config = config.get("deck")
    if not isinstance(deck_config, dict):
        raise ValueError(  # noqa: TRY004
            "deck.toml must contain a [deck] table"
        )

    if "format_version" not in deck_config:
        raise ValueError("Missing required deck setting: format_version")
    format_version = deck_config["format_version"]
    if not isinstance(format_version, int) or isinstance(format_version, bool):
        raise ValueError(  # noqa: TRY004
            "deck.format_version must be an integer"
        )
    if format_version != _SUPPORTED_FORMAT_VERSION:
        raise ValueError(f"Unsupported deck format version: {format_version}")

    configured_paths: dict[str, str] = {}
    for key in _CONFIGURED_PATH_KEYS:
        if key not in deck_config:
            raise ValueError(f"Missing required deck setting: {key}")
        value = deck_config[key]
        if not isinstance(value, str) or not value:
            raise ValueError(f"deck.{key} must be a non-empty string")
        configured_paths[key] = value
    return configured_paths


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


def _validate_required_file(path: Path, name: str) -> None:
    """Require *path* to be a regular file, following valid symlinks."""
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(f"Required {name} file is missing: {path}") from None

    if stat.S_ISDIR(mode):
        raise IsADirectoryError(f"Required {name} entry must be a file: {path}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"Required {name} entry must be a regular file: {path}")


def _validate_required_directory(path: Path, name: str) -> None:
    """Require *path* to be a directory, following valid symlinks."""
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Required {name} directory is missing: {path}"
        ) from None

    if stat.S_ISREG(mode):
        raise NotADirectoryError(f"Required {name} entry must be a directory: {path}")
    if not stat.S_ISDIR(mode):
        raise ValueError(f"Required {name} entry must be a directory: {path}")


def _validate_project(root: Path, configured_paths: dict[str, str]) -> None:
    """Validate the required filesystem entries for a project."""
    _validate_required_file(root / "deck.py", "deck.py")
    for key in _CONFIGURED_FILE_KEYS:
        _validate_required_file(
            _project_path(root, key, configured_paths[key]),
            key,
        )
    _validate_required_directory(
        _project_path(root, "assets", configured_paths["assets"]),
        "assets",
    )


class Deck:
    """A SlideJunction presentation project."""

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
        configured_paths = _validate_manifest(_load_manifest(manifest))
        root = manifest.parent
        _validate_project(root, configured_paths)
        return cls._from_root(root)

    @classmethod
    def init(cls, path: str | Path) -> Self:
        """Create a minimal SlideJunction project at *path*."""
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

        for name, content in _PROJECT_FILES.items():
            with (root / name).open(
                "x", encoding="utf-8", newline="\n"
            ) as project_file:
                project_file.write(content)

        (root / _ASSETS_DIRECTORY).mkdir()
        return cls._from_root(root)
