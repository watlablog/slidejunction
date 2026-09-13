import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import slidejunction
from slidejunction import Deck, cli
from slidejunction.cli import main

_README_SLIDES = """# My Presentation

Welcome to SlideJunction.

## First Slide

Hello **SlideJunction**!

## Second Slide

Write your presentation in Markdown.
"""


def test_bare_command_preserves_the_original_banner(capsys) -> None:
    assert main([]) == 0

    captured = capsys.readouterr()
    assert captured.out == "SlideJunction\n"
    assert captured.err == ""


@pytest.mark.parametrize(
    ("arguments", "expected_text"),
    [
        (["--help"], "{init,build}"),
        (["init", "--help"], "Create a SlideJunction project."),
        (["build", "--help"], "Build a SlideJunction project as static HTML."),
    ],
)
def test_help_uses_argparse_stdout_and_exit_zero(
    capsys,
    arguments: list[str],
    expected_text: str,
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(arguments)

    assert raised.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("usage: slidejunction")
    assert expected_text in captured.out
    assert captured.err == ""


@pytest.mark.parametrize("arguments", [["unknown"], ["init"]])
def test_invalid_grammar_uses_argparse_stderr_and_exit_two(
    capsys,
    arguments: list[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(arguments)

    assert raised.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: slidejunction")
    assert "error:" in captured.err


def test_init_delegates_once_and_reports_the_canonical_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    requested = tmp_path / "talks" / "my-talk"
    calls: list[str | Path] = []
    original_init = Deck.init.__func__

    def observed_init(cls, path: str | Path) -> Deck:
        calls.append(path)
        return original_init(cls, path)

    monkeypatch.setattr(Deck, "init", classmethod(observed_init))

    assert main(["init", str(requested)]) == 0

    assert len(calls) == 1
    assert Path(calls[0]) == requested
    captured = capsys.readouterr()
    assert captured.out == f"Created SlideJunction project: {requested.resolve()}\n"
    assert captured.err == ""
    assert (requested / "slides.md").read_text(encoding="utf-8") == (
        "# Untitled Presentation\n"
    )


def test_init_accepts_an_empty_directory_and_preserves_unrelated_entries(
    tmp_path: Path,
    capsys,
) -> None:
    project = tmp_path / "my-talk"
    project.mkdir()
    notes = project / "notes.txt"
    notes.write_bytes(b"keep\n")

    assert main(["init", str(project)]) == 0

    assert notes.read_bytes() == b"keep\n"
    assert (project / "assets").is_dir()
    assert capsys.readouterr().err == ""


def test_init_collision_is_an_operational_error(
    tmp_path: Path,
    capsys,
) -> None:
    project = tmp_path / "my-talk"
    project.mkdir()
    (project / "slides.md").write_text("keep\n", encoding="utf-8")

    assert main(["init", str(project)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "error: Cannot initialize project; entries already exist: slides.md\n"
    )
    assert (project / "slides.md").read_text(encoding="utf-8") == "keep\n"


def test_init_then_build_default_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    project = tmp_path / "my-talk"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(project)

    assert main(["build"]) == 0

    output = project / "build" / "index.html"
    html = output.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>\n")
    assert "<h1>Untitled Presentation</h1>" in html
    assert html.endswith("</html>\n")
    captured = capsys.readouterr()
    assert captured.out == f"Built: {output.resolve()}\n"
    assert captured.err == ""


def test_readme_first_workflow_renders_edited_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    project = tmp_path / "my-talk"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    (project / "slides.md").write_text(_README_SLIDES, encoding="utf-8")
    monkeypatch.chdir(project)

    assert main(["build"]) == 0

    html = (project / "build" / "index.html").read_text(encoding="utf-8")
    assert "<h1>My Presentation</h1>" in html
    assert "<p>Welcome to SlideJunction.</p>" in html
    assert "<h2>First Slide</h2>" in html
    assert "Hello <strong>SlideJunction</strong>!" in html
    assert "<h2>Second Slide</h2>" in html
    assert "Write your presentation in Markdown." in html
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("location", ["outside", "root", "nested"])
def test_build_uses_deck_open_discovery_from_supported_locations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    location: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    outside = tmp_path / "outside"
    outside.mkdir()
    nested = project / "notes" / "nested"
    nested.mkdir(parents=True)
    if location == "outside":
        monkeypatch.chdir(outside)
        arguments = ["build", str(project)]
    elif location == "root":
        monkeypatch.chdir(project)
        arguments = ["build"]
    else:
        monkeypatch.chdir(nested)
        arguments = ["build"]

    assert main(arguments) == 0

    output = project / "build" / "index.html"
    assert output.is_file()
    captured = capsys.readouterr()
    assert captured.out == f"Built: {output}\n"
    assert captured.err == ""


def test_build_delegates_to_open_load_and_renderer_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    open_calls: list[str | Path] = []
    load_calls: list[Path] = []
    render_calls: list[object] = []
    original_open = Deck.open.__func__
    original_load = Deck.load
    original_render = cli.render_static_html

    def observed_open(cls, path: str | Path = ".") -> Deck:
        open_calls.append(path)
        return original_open(cls, path)

    def observed_load(self: Deck):
        load_calls.append(self.root)
        return original_load(self)

    def observed_render(presentation):
        render_calls.append(presentation)
        return original_render(presentation)

    monkeypatch.setattr(Deck, "open", classmethod(observed_open))
    monkeypatch.setattr(Deck, "load", observed_load)
    monkeypatch.setattr(cli, "render_static_html", observed_render)

    assert main(["build", str(project)]) == 0

    assert len(open_calls) == 1
    assert Path(open_calls[0]) == project
    assert load_calls == [project]
    assert len(render_calls) == 1
    assert capsys.readouterr().err == ""


def test_rebuild_refreshes_html_and_preserves_other_build_files(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    source = project / "slides.md"
    source.write_text("# First version\n", encoding="utf-8")

    assert main(["build", str(project)]) == 0
    capsys.readouterr()
    output = project / "build" / "index.html"
    first_html = output.read_bytes()
    unrelated = project / "build" / "notes.txt"
    unrelated.write_bytes(b"preserve\n")
    source.write_text("# Second version\n\nUpdated body.\n", encoding="utf-8")

    assert main(["build", str(project)]) == 0

    second_html = output.read_bytes()
    assert second_html != first_html
    assert b"Second version" in second_html
    assert b"Updated body." in second_html
    assert b"First version" not in second_html
    assert unrelated.read_bytes() == b"preserve\n"
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("preexisting_output", [False, True])
def test_fatal_layout_reports_diagnostics_and_does_not_touch_output(
    tmp_path: Path,
    capsys,
    preexisting_output: bool,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    (project / "layout.json").write_text("{", encoding="utf-8")
    output = project / "build" / "index.html"
    if preexisting_output:
        output.parent.mkdir()
        output.write_bytes(b"existing output\n")
    result = Deck.open(project).load()
    assert result.snapshot is None

    assert main(["build", str(project)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        _diagnostic_text(result)
        + "error: build failed: no renderable project snapshot\n"
    )
    if preexisting_output:
        assert output.read_bytes() == b"existing output\n"
    else:
        assert not output.exists()
        assert not output.parent.exists()


def test_recoverable_errors_are_reported_but_still_build(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    source = "Text </sj-format>\n\n<!-- sj:ref=8 -->\nReferenced"
    layout = {
        "format_version": 1,
        "theme": {"preset": {"name": "future-preset", "version": 7}},
        "configurations": {},
        "inline_formats": {},
    }
    (project / "slides.md").write_text(source, encoding="utf-8")
    (project / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
    result = Deck.open(project).load()
    assert result.snapshot is not None
    assert result.has_errors

    assert main(["build", str(project)]) == 0

    output = project / "build" / "index.html"
    assert output.is_file()
    captured = capsys.readouterr()
    assert captured.out == f"Built: {output}\n"
    assert captured.err == _diagnostic_text(result)
    assert captured.err.splitlines() == [
        f"{item.severity.value.upper()} {item.code}: {item.message}"
        for item in result.diagnostics
    ]


def test_build_preserves_every_project_input(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    asset = project / "assets" / "nested" / "image.bin"
    asset.parent.mkdir()
    asset.write_bytes(b"asset bytes\x00\xff")
    inputs = [
        project / "deck.toml",
        project / "deck.py",
        project / "slides.md",
        project / "layout.json",
        project / "theme.css",
        asset,
    ]
    before = {path: path.read_bytes() for path in inputs}

    assert main(["build", str(project)]) == 0

    assert {path: path.read_bytes() for path in inputs} == before
    assert asset.parent.is_dir()
    assert capsys.readouterr().err == ""


def test_build_rejects_a_regular_file_at_the_build_path(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    build = project / "build"
    build.write_bytes(b"keep\n")

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output path must be a directory: {build}",
    )
    assert build.read_bytes() == b"keep\n"


def test_build_rejects_a_directory_symlink_without_writing_to_its_target(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    target = tmp_path / "external-build"
    target.mkdir()
    build = project / "build"
    _symlink_or_skip(build, target, target_is_directory=True)

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output directory must not be a symlink: {build}",
    )
    assert not (target / "index.html").exists()


@pytest.mark.parametrize("target_exists", [True, False])
def test_build_rejects_an_index_symlink_and_preserves_its_target(
    tmp_path: Path,
    capsys,
    target_exists: bool,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    build = project / "build"
    build.mkdir()
    target = tmp_path / "external-index.html"
    if target_exists:
        target.write_bytes(b"external bytes\n")
    output = build / "index.html"
    _symlink_or_skip(output, target)

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output file must not be a symlink: {output}",
    )
    if target_exists:
        assert target.read_bytes() == b"external bytes\n"
    else:
        assert not target.exists()


def test_build_rejects_an_index_hard_link_and_preserves_linked_bytes(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    build = project / "build"
    build.mkdir()
    linked = tmp_path / "linked.html"
    linked.write_bytes(b"linked bytes\n")
    output = build / "index.html"
    try:
        os.link(linked, output)
    except OSError as error:
        pytest.skip(f"Hard links are unavailable: {error}")

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output file must have exactly one hard link: {output}",
    )
    assert output.read_bytes() == b"linked bytes\n"
    assert linked.read_bytes() == b"linked bytes\n"


def test_build_rejects_a_nonregular_index_entry(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    output = project / "build" / "index.html"
    output.mkdir(parents=True)

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output path must be a regular file: {output}",
    )
    assert output.is_dir()


def test_build_overwrites_a_single_link_regular_index(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    output = project / "build" / "index.html"
    output.parent.mkdir()
    output.write_bytes(b"old output\n")
    assert output.stat().st_nlink == 1

    assert main(["build", str(project)]) == 0

    assert output.read_bytes().startswith(b"<!doctype html>\n")
    assert output.read_bytes().endswith(b"</html>\n")
    assert capsys.readouterr().err == ""


def test_output_write_os_error_becomes_a_short_operational_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    output = project / "build" / "index.html"
    original_write_text = Path.write_text

    def denied_write(path: Path, data: str, *args, **kwargs) -> int:
        if path == output:
            raise PermissionError("write denied")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", denied_write)

    assert main(["build", str(project)]) == 1

    _assert_operational_error(capsys, "write denied")
    assert not output.exists()


@pytest.mark.parametrize(
    ("command", "stage", "exception"),
    [
        ("init", "init", ValueError("invalid init")),
        ("build", "open", OSError("open failed")),
        ("build", "load", ValueError("load failed")),
    ],
)
def test_deck_operational_errors_become_exit_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    command: str,
    stage: str,
    exception: Exception,
) -> None:
    project = tmp_path / "my-talk"

    class LoadFailure:
        root = project

        def load(self):
            raise exception

    if stage == "init":

        def fail_init(cls, path):
            raise exception

        monkeypatch.setattr(Deck, "init", classmethod(fail_init))
    elif stage == "open":

        def fail_open(cls, path="."):
            raise exception

        monkeypatch.setattr(Deck, "open", classmethod(fail_open))
    else:
        monkeypatch.setattr(
            Deck,
            "open",
            classmethod(lambda cls, path=".": LoadFailure()),
        )

    arguments = [command, str(project)]
    assert main(arguments) == 1

    _assert_operational_error(capsys, str(exception))


@pytest.mark.parametrize(
    "exception",
    [
        TypeError("wrong type"),
        RuntimeError("unexpected"),
        KeyboardInterrupt(),
        SystemExit(7),
    ],
)
def test_unexpected_and_base_exceptions_are_not_caught(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception: BaseException,
) -> None:
    project = tmp_path / "my-talk"

    def fail_open(cls, path="."):
        raise exception

    monkeypatch.setattr(Deck, "open", classmethod(fail_open))

    with pytest.raises(type(exception)) as raised:
        main(["build", str(project)])

    if isinstance(exception, SystemExit):
        assert raised.value.code == 7


@pytest.mark.parametrize(
    "exception_type",
    [TypeError, ValueError],
)
def test_renderer_contract_errors_propagate_without_touching_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[Exception],
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    output = project / "build" / "index.html"
    output.parent.mkdir()
    output.write_bytes(b"existing output\n")

    def fail_render(presentation):
        raise exception_type("invalid resolved presentation")

    monkeypatch.setattr(cli, "render_static_html", fail_render)

    with pytest.raises(exception_type, match="invalid resolved presentation"):
        main(["build", str(project)])

    assert output.read_bytes() == b"existing output\n"


def test_cli_does_not_expand_the_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "main")
    assert not hasattr(slidejunction, "render_static_html")


def test_module_entrypoint_supports_init_and_build_subcommands(tmp_path: Path) -> None:
    project = tmp_path / "my-talk"
    initialized = subprocess.run(
        [sys.executable, "-m", "slidejunction", "init", str(project)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert initialized.returncode == 0
    assert initialized.stdout == f"Created SlideJunction project: {project.resolve()}\n"
    assert initialized.stderr == ""
    (project / "slides.md").write_text(_README_SLIDES, encoding="utf-8")

    built = subprocess.run(
        [sys.executable, "-m", "slidejunction", "build"],
        cwd=project,
        check=False,
        capture_output=True,
        text=True,
    )

    output = project / "build" / "index.html"
    assert built.returncode == 0
    assert built.stdout == f"Built: {output}\n"
    assert built.stderr == ""
    assert "<strong>SlideJunction</strong>" in output.read_text(encoding="utf-8")


def _diagnostic_text(result) -> str:
    return "".join(
        f"{item.severity.value.upper()} {item.code}: {item.message}\n"
        for item in result.diagnostics
    )


def _assert_operational_error(capsys, message: str) -> None:
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: {message}\n"
    assert "Traceback" not in captured.err


def _symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
