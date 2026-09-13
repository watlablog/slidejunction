"""Command-line interface for SlideJunction."""

from __future__ import annotations

import argparse
import stat
import sys
from collections.abc import Sequence
from pathlib import Path

from .deck import Deck
from .html_renderer import render_static_html
from .project import DeckLoadResult


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="slidejunction")
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser(
        "init",
        help="Create a SlideJunction project.",
        description="Create a SlideJunction project.",
    )
    init_parser.add_argument("directory")

    build_parser = commands.add_parser(
        "build",
        help="Build a SlideJunction project as static HTML.",
        description="Build a SlideJunction project as static HTML.",
    )
    build_parser.add_argument("project", nargs="?", default=".")
    return parser


def _print_error(error: OSError | ValueError) -> None:
    print(f"error: {error}", file=sys.stderr)


def _print_diagnostics(result: DeckLoadResult) -> None:
    for diagnostic in result.diagnostics:
        severity = diagnostic.severity.value.upper()
        print(
            f"{severity} {diagnostic.code}: {diagnostic.message}",
            file=sys.stderr,
        )


def _init_project(directory: str) -> int:
    try:
        deck = Deck.init(directory)
    except (OSError, ValueError) as error:
        _print_error(error)
        return 1

    print(f"Created SlideJunction project: {deck.root}")
    return 0


def _prepare_build_output(root: Path) -> Path:
    build_directory = root / "build"
    try:
        build_status = build_directory.lstat()
    except FileNotFoundError:
        build_directory.mkdir()
    else:
        if stat.S_ISLNK(build_status.st_mode):
            raise ValueError(
                f"Build output directory must not be a symlink: {build_directory}"
            )
        if not stat.S_ISDIR(build_status.st_mode):
            raise ValueError(
                f"Build output path must be a directory: {build_directory}"
            )

    output = build_directory / "index.html"
    try:
        output_status = output.lstat()
    except FileNotFoundError:
        return output

    if stat.S_ISLNK(output_status.st_mode):
        raise ValueError(f"Build output file must not be a symlink: {output}")
    if not stat.S_ISREG(output_status.st_mode):
        raise ValueError(f"Build output path must be a regular file: {output}")
    if output_status.st_nlink != 1:
        raise ValueError(f"Build output file must have exactly one hard link: {output}")
    return output


def _build_project(project: str) -> int:
    try:
        deck = Deck.open(project)
        result = deck.load()
    except (OSError, ValueError) as error:
        _print_error(error)
        return 1

    _print_diagnostics(result)
    snapshot = result.snapshot
    if snapshot is None:
        print(
            "error: build failed: no renderable project snapshot",
            file=sys.stderr,
        )
        return 1

    html = render_static_html(snapshot.resolved_presentation)

    try:
        output = _prepare_build_output(deck.root)
    except (OSError, ValueError) as error:
        _print_error(error)
        return 1

    try:
        output.write_text(html, encoding="utf-8", newline="\n")
    except OSError as error:
        _print_error(error)
        return 1

    print(f"Built: {output}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the SlideJunction command-line interface."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print("SlideJunction")
        return 0

    namespace = _parser().parse_args(arguments)
    if namespace.command == "init":
        return _init_project(namespace.directory)
    if namespace.command == "build":
        return _build_project(namespace.project)
    raise ValueError(f"Unsupported command: {namespace.command}")
