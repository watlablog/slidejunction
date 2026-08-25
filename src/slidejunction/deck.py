"""SlideJunction presentation project."""

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
    ),
    "slides.md": "# Untitled Presentation\n",
    "theme.css": "/* SlideJunction presentation theme */\n",
    "layout.css": "/* Slide-specific layout overrides */\n",
}
_ASSETS_DIRECTORY = "assets"
_PROJECT_ENTRY_NAMES = (*_PROJECT_FILES, _ASSETS_DIRECTORY)


def _entry_exists(path: Path) -> bool:
    """Return whether a path entry exists, including a broken symlink."""
    return path.exists() or path.is_symlink()


class Deck:
    """A SlideJunction presentation project."""

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        raise TypeError("Deck cannot be constructed directly; use Deck.init().")

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
