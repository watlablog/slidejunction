"""Private filesystem boundary for SlideJunction project load and save.

The helpers in this module preserve exact UTF-8 text, distinguish logical
project paths from their resolved targets, and provide per-file replacement
primitives.  Multi-file commit ordering remains the responsibility of
``Deck``.
"""

from __future__ import annotations

import errno
import os
import stat
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .project import (
    LoadedTextFile,
    ProjectFileSnapshot,
    ProjectManifestSnapshot,
    StaleDeckSnapshotError,
    _project_path,
)

_MANIFEST_NAME = "deck.toml"
_ENTRYPOINT_NAME = "deck.py"
_SUPPORTED_FORMAT_VERSION = 1
_CONFIGURED_FILE_KEYS = ("source", "layout", "theme")
_CONFIGURED_PATH_KEYS = (*_CONFIGURED_FILE_KEYS, "assets")


@dataclass(frozen=True, slots=True)
class _ProjectEntries:
    root: Path
    manifest_settings: ProjectManifestSnapshot
    manifest: LoadedTextFile
    source_path: Path
    source_target_path: Path
    layout_path: Path
    layout_target_path: Path
    theme_path: Path
    theme_target_path: Path
    entrypoint_target_path: Path
    assets_path: Path
    assets_target_path: Path


@dataclass(frozen=True, slots=True)
class _StagedTextFile:
    """A fully flushed temporary file awaiting replacement of one target."""

    target_path: Path
    temporary_path: Path


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
    if not isinstance(start, Path):
        raise TypeError("Project discovery start must be a Path")
    for directory in (start, *start.parents):
        manifest = directory / _MANIFEST_NAME
        if _entry_exists(manifest):
            return manifest
    raise FileNotFoundError(f"No {_MANIFEST_NAME} found from: {start}")


def _validate_project_for_open(root: Path) -> ProjectManifestSnapshot:
    """Validate a project contract without parsing source or layout content."""
    return _inspect_project(root).manifest_settings


def _load_project_files(root: Path) -> ProjectFileSnapshot:
    """Load one exact immutable snapshot of all M7 project text inputs."""
    entries = _inspect_project(root)
    return ProjectFileSnapshot(
        root=entries.root,
        manifest_settings=entries.manifest_settings,
        manifest=entries.manifest,
        source=_loaded_text_file(
            entries.source_path,
            entries.source_target_path,
        ),
        layout=_loaded_text_file(
            entries.layout_path,
            entries.layout_target_path,
        ),
        theme=_loaded_text_file(
            entries.theme_path,
            entries.theme_target_path,
        ),
        entrypoint_target_path=entries.entrypoint_target_path,
        assets_path=entries.assets_path,
        assets_target_path=entries.assets_target_path,
    )


def _require_current_project_files(
    baseline: ProjectFileSnapshot,
    *,
    source_text: str | None = None,
    layout_text: str | None = None,
) -> ProjectFileSnapshot:
    """Return current files only when they match a loaded save baseline.

    Manifest formatting and unknown settings, theme contents, and assets
    contents may change.  Validated manifest settings, all required targets,
    and the expected source/layout text must remain unchanged.
    """
    if not isinstance(baseline, ProjectFileSnapshot):
        raise TypeError("Save baseline must be a ProjectFileSnapshot")
    if source_text is not None and not isinstance(source_text, str):
        raise TypeError("Expected source text must be a string or None")
    if layout_text is not None and not isinstance(layout_text, str):
        raise TypeError("Expected layout text must be a string or None")

    expected_source = baseline.source.text if source_text is None else source_text
    expected_layout = baseline.layout.text if layout_text is None else layout_text
    try:
        current = _load_project_files(baseline.root)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise
    except (
        FileNotFoundError,
        IsADirectoryError,
        NotADirectoryError,
        ValueError,
    ) as error:
        raise StaleDeckSnapshotError(
            "Project entries no longer match the loaded snapshot baseline"
        ) from error
    except OSError as error:
        if not _is_stale_topology_os_error(error):
            raise
        raise StaleDeckSnapshotError(
            "Project entries no longer match the loaded snapshot baseline"
        ) from error

    if current.manifest_settings != baseline.manifest_settings:
        raise StaleDeckSnapshotError(
            "Project manifest settings changed since the snapshot was loaded"
        )

    target_pairs = (
        ("manifest", current.manifest.target_path, baseline.manifest.target_path),
        (
            "entrypoint",
            current.entrypoint_target_path,
            baseline.entrypoint_target_path,
        ),
        ("source", current.source.target_path, baseline.source.target_path),
        ("layout", current.layout.target_path, baseline.layout.target_path),
        ("theme", current.theme.target_path, baseline.theme.target_path),
        ("assets", current.assets_target_path, baseline.assets_target_path),
    )
    for name, current_target, baseline_target in target_pairs:
        if current_target != baseline_target:
            raise StaleDeckSnapshotError(
                f"Project {name} target changed since the snapshot was loaded"
            )

    if current.source.text != expected_source:
        raise StaleDeckSnapshotError(
            "Project source changed since the snapshot was loaded"
        )
    if current.layout.text != expected_layout:
        raise StaleDeckSnapshotError(
            "Project layout changed since the snapshot was loaded"
        )
    return current


def _require_changed_target_not_hard_link(
    target_path: Path,
    *,
    name: str,
) -> None:
    """Reject replacement of a changed target with multiple hard links."""
    if not isinstance(target_path, Path):
        raise TypeError("Changed target path must be a Path")
    if not isinstance(name, str):
        raise TypeError("Changed target name must be a string")
    target_stat = target_path.stat()
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError(f"Changed {name} target must be a regular file")
    if target_stat.st_nlink > 1:
        raise ValueError(
            f"Cannot replace changed {name} target with multiple hard links: "
            f"{target_path}"
        )


def _stage_utf8_text(target_path: Path, text: str) -> _StagedTextFile:
    """Write, permission-match, and fsync a same-directory temporary file."""
    if not isinstance(target_path, Path):
        raise TypeError("Stage target_path must be a Path")
    if not isinstance(text, str):
        raise TypeError("Staged text must be a string")
    encoded = text.encode("utf-8")
    target_stat = target_path.stat()
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError("Staged text target must be a regular file")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.slidejunction-",
        suffix=".tmp",
        dir=target_path.parent,
    )
    temporary_path = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            descriptor_open = False
            written = temporary_file.write(encoded)
            if written != len(encoded):  # pragma: no cover - buffered I/O contract
                raise OSError("Could not write the complete staged project file")
            temporary_file.flush()
            mode = stat.S_IMODE(target_stat.st_mode)
            if hasattr(os, "fchmod"):
                os.fchmod(temporary_file.fileno(), mode)
            else:  # pragma: no cover - fchmod is available on supported POSIX builds
                os.chmod(temporary_path, mode)
            os.fsync(temporary_file.fileno())
    except BaseException:
        if descriptor_open:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        raise

    return _StagedTextFile(
        target_path=target_path,
        temporary_path=temporary_path,
    )


def _replace_staged_text(staged: _StagedTextFile) -> None:
    """Atomically replace one actual target and fsync its parent if supported.

    If directory fsync fails after ``os.replace`` succeeds, the original error
    is propagated and the target may already contain the new text.  No rollback
    is attempted.
    """
    if not isinstance(staged, _StagedTextFile):
        raise TypeError("staged must be a _StagedTextFile")
    os.replace(staged.temporary_path, staged.target_path)
    _fsync_directory(staged.target_path.parent)


def _cleanup_staged_text_files(
    staged_files: tuple[_StagedTextFile, ...],
    *,
    suppress_errors: bool,
) -> None:
    """Remove remaining temporary files, optionally preserving a primary error."""
    if not isinstance(staged_files, tuple) or not all(
        isinstance(item, _StagedTextFile) for item in staged_files
    ):
        raise TypeError("staged_files must be a tuple of _StagedTextFile")
    if not isinstance(suppress_errors, bool):
        raise TypeError("suppress_errors must be a bool")

    first_error: OSError | None = None
    for staged in staged_files:
        try:
            staged.temporary_path.unlink()
        except FileNotFoundError:
            continue
        except OSError as error:
            if first_error is None:
                first_error = error
    if first_error is not None and not suppress_errors:
        raise first_error


def _fsync_directory(directory: Path) -> None:
    """Fsync a POSIX directory, ignoring only explicit unsupported errors."""
    if not isinstance(directory, Path):
        raise TypeError("Directory fsync path must be a Path")
    if os.name != "posix":  # pragma: no cover - platform-specific contract
        return

    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor: int | None = None
    primary_error: BaseException | None = None
    try:
        descriptor = os.open(directory, flags)
        os.fsync(descriptor)
    except OSError as error:
        if error.errno not in _unsupported_directory_fsync_errnos():
            primary_error = error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                if primary_error is None:
                    primary_error = error
    if primary_error is not None:
        raise primary_error


def _inspect_project(root: Path) -> _ProjectEntries:
    if not isinstance(root, Path):
        raise TypeError("Project root must be a Path")
    manifest_path = root / _MANIFEST_NAME
    manifest_target = _require_regular_file(manifest_path, "deck.toml")
    manifest = _loaded_text_file(manifest_path, manifest_target)
    settings = _parse_manifest(manifest.text)

    entrypoint_path = root / _ENTRYPOINT_NAME
    source_path = _project_path(root, "source", settings.source)
    layout_path = _project_path(root, "layout", settings.layout)
    theme_path = _project_path(root, "theme", settings.theme)
    assets_path = _project_path(root, "assets", settings.assets)

    entrypoint_target = _require_regular_file(entrypoint_path, "deck.py")
    source_target = _require_regular_file(source_path, "source")
    layout_target = _require_regular_file(layout_path, "layout")
    theme_target = _require_regular_file(theme_path, "theme")
    assets_target = _require_directory(assets_path, "assets")

    _require_distinct_files(
        (
            ("deck.toml", manifest_path),
            ("deck.py", entrypoint_path),
            ("source", source_path),
            ("layout", layout_path),
            ("theme", theme_path),
        )
    )
    return _ProjectEntries(
        root=root,
        manifest_settings=settings,
        manifest=manifest,
        source_path=source_path,
        source_target_path=source_target,
        layout_path=layout_path,
        layout_target_path=layout_target,
        theme_path=theme_path,
        theme_target_path=theme_target,
        entrypoint_target_path=entrypoint_target,
        assets_path=assets_path,
        assets_target_path=assets_target,
    )


def _parse_manifest(text: str) -> ProjectManifestSnapshot:
    config = tomllib.loads(text)
    deck_config = config.get("deck")
    if not isinstance(deck_config, dict):
        raise ValueError(  # noqa: TRY004 - malformed external manifest
            "deck.toml must contain a [deck] table"
        )

    if "format_version" not in deck_config:
        raise ValueError("Missing required deck setting: format_version")
    format_version = deck_config["format_version"]
    if not isinstance(format_version, int) or isinstance(format_version, bool):
        raise ValueError(  # noqa: TRY004 - malformed external manifest
            "deck.format_version must be an integer"
        )
    if format_version != _SUPPORTED_FORMAT_VERSION:
        raise ValueError(f"Unsupported deck format version: {format_version}")

    paths: dict[str, str] = {}
    for key in _CONFIGURED_PATH_KEYS:
        if key not in deck_config:
            raise ValueError(f"Missing required deck setting: {key}")
        value = deck_config[key]
        if not isinstance(value, str) or not value:
            raise ValueError(f"deck.{key} must be a non-empty string")
        paths[key] = value
    return ProjectManifestSnapshot(
        format_version=format_version,
        source=paths["source"],
        layout=paths["layout"],
        theme=paths["theme"],
        assets=paths["assets"],
    )


def _require_regular_file(path: Path, name: str) -> Path:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(f"Required {name} file is missing: {path}") from None
    if stat.S_ISDIR(mode):
        raise IsADirectoryError(f"Required {name} entry must be a file: {path}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"Required {name} entry must be a regular file: {path}")
    return path.resolve(strict=True)


def _require_directory(path: Path, name: str) -> Path:
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
    return path.resolve(strict=True)


def _loaded_text_file(path: Path, target_path: Path) -> LoadedTextFile:
    return LoadedTextFile(
        path=path,
        target_path=target_path,
        text=target_path.read_bytes().decode("utf-8"),
    )


def _require_distinct_files(files: tuple[tuple[str, Path], ...]) -> None:
    samefile = getattr(os.path, "samefile", None)
    for index, (left_name, left_path) in enumerate(files):
        for right_name, right_path in files[index + 1 :]:
            if samefile is None:
                aliased = _same_file_by_stat(left_path, right_path)
            else:
                try:
                    aliased = samefile(left_path, right_path)
                except NotImplementedError:
                    aliased = _same_file_by_stat(left_path, right_path)
            if aliased:
                raise ValueError(
                    "Required project files must be distinct: "
                    f"{left_name} and {right_name} refer to the same file"
                )


def _same_file_by_stat(left: Path, right: Path) -> bool:
    left_stat = left.stat()
    right_stat = right.stat()
    return (left_stat.st_dev, left_stat.st_ino) == (
        right_stat.st_dev,
        right_stat.st_ino,
    )


def _unsupported_directory_fsync_errnos() -> frozenset[int]:
    return frozenset(
        value
        for value in (
            errno.EINVAL,
            getattr(errno, "ENOTSUP", None),
            getattr(errno, "EOPNOTSUPP", None),
        )
        if value is not None
    )


def _is_stale_topology_os_error(error: OSError) -> bool:
    """Return whether an OS error denotes an invalid required path topology."""
    return error.errno in {errno.ELOOP, errno.ENAMETOOLONG}


__all__: list[str] = []
