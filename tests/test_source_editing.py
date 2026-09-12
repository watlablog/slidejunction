import builtins
from dataclasses import replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import source_editing
from slidejunction.layout import (
    Configuration,
    InlineFormatConfiguration,
    LayoutDocument,
    Stacking,
    Theme,
    ThemePreset,
)
from slidejunction.markdown import parse_markdown
from slidejunction.reference_editing import (
    ReferenceEditResult,
    SourceReferenceChange,
    detach_reference,
    edit_consumer_locally,
    edit_shared_definition,
    set_consumer_reference,
)
from slidejunction.references import ReferenceKind, validate_references
from slidejunction.source_editing import apply_reference_edit_to_source


def _layout(*, configurations=None, inline_formats=None):
    return LayoutDocument(
        format_version=1,
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
        ),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _index(source, layout):
    return validate_references(source, layout).index


def _consumer(source, layout, ref_id, kind):
    expected = (
        ReferenceKind.CONFIGURATION if kind == "block" else ReferenceKind.INLINE_FORMAT
    )
    return next(
        usage.consumer
        for usage in _index(source, layout).usages_for(ref_id)
        if usage.kind is expected
    )


def _replace_block(source, old, new):
    item = source.presentation.items[0]
    return replace(
        source,
        presentation=replace(
            source.presentation,
            items=(
                replace(
                    item,
                    blocks=tuple(
                        new if block is old else block for block in item.blocks
                    ),
                ),
            ),
        ),
    )


def _result(source, layout, consumer, change):
    return ReferenceEditResult(
        source_document=source,
        layout_document=layout,
        selected_consumer=consumer,
        source_changes=(change,),
        selected_ref_id=change.new_ref_id,
    )


def test_public_exports_are_limited_to_source_application():
    assert source_editing.__all__ == ["apply_reference_edit_to_source"]
    assert slidejunction.__all__ == ["Deck"]


def test_wrong_public_argument_type_is_rejected():
    with pytest.raises(TypeError):
        apply_reference_edit_to_source(None)


@pytest.mark.parametrize("operation", ["local", "shared", "editor-noop"])
def test_definition_only_results_are_source_identity_noops(operation, monkeypatch):
    text = "<!-- sj:ref=3 -->\nBody\n\n<!-- sj:ref=3 -->\nOther"
    source = parse_markdown(text, path=Path("slides.md"))
    layout = _layout(configurations={3: Configuration()})
    consumer = _consumer(source, layout, 3, "block")
    index = _index(source, layout)

    if operation == "local":
        single_source = parse_markdown(
            "<!-- sj:ref=3 -->\nBody", path=Path("slides.md")
        )
        consumer = _consumer(single_source, layout, 3, "block")
        result = edit_consumer_locally(
            single_source,
            layout,
            _index(single_source, layout),
            consumer,
            editor=lambda value: replace(value, stacking=Stacking(z_index=2)),
        )
        source = single_source
    elif operation == "shared":
        result = edit_shared_definition(
            source,
            layout,
            index,
            consumer,
            editor=lambda value: replace(value, stacking=Stacking(z_index=2)),
        )
    else:
        result = edit_consumer_locally(
            source,
            layout,
            index,
            consumer,
            editor=lambda value: replace(value),
        )

    monkeypatch.setattr(
        source_editing,
        "parse_markdown",
        lambda *args, **kwargs: pytest.fail("identity no-op must not reparse"),
    )
    assert result.source_changes == ()
    assert apply_reference_edit_to_source(result) is source


@pytest.mark.parametrize(
    "body,type_name",
    [
        ("### Heading", "Heading"),
        ("Paragraph", "Paragraph"),
        ("- Item", "ListBlock"),
        ("> Quote", "BlockQuote"),
        ("```python\nx\n```", "CodeBlock"),
        ("![alt](image.png)", "ImageBlock"),
        ("***", "ThematicBreak"),
        ("\\[\nx\n\\]", "MathBlock"),
    ],
)
def test_block_attach_supports_every_block_kind(body, type_name):
    source = parse_markdown(body, path=Path("slides.md"))
    block = source.presentation.items[0].blocks[0]
    assert type(block).__name__ == type_name
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source,
        layout,
        _index(source, layout),
        block,
        ref_id=8,
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == f"<!-- sj:ref=8 -->\n{body}"
    assert updated.path == Path("slides.md")
    assert _consumer(updated, layout, 8, "block").config_ref == 8
    assert updated is not source


@pytest.mark.parametrize("level", [1, 2])
def test_block_attach_supports_section_and_slide_titles(level):
    source = parse_markdown("#" * level + " Title")
    item = source.presentation.items[0]
    block = item.title_slide.title if level == 1 else item.title
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == "<!-- sj:ref=8 -->\n" + "#" * level + " Title"
    assert _consumer(updated, layout, 8, "block").config_ref == 8


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_block_attach_at_source_start_uses_target_syntax_line_ending(line_ending):
    text = f"first{line_ending}second"
    source = parse_markdown(text)
    block = source.presentation.items[0].blocks[0]
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == f"<!-- sj:ref=8 -->{line_ending}{text}"


def test_block_attach_without_existing_line_ending_falls_back_to_lf():
    source = parse_markdown("Body")
    block = source.presentation.items[0].blocks[0]
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    assert apply_reference_edit_to_source(result).text == ("<!-- sj:ref=8 -->\nBody")


def test_noninitial_block_attach_reuses_immediately_preceding_mixed_line_ending():
    source = parse_markdown("First\r\n\r\nSecond\ncontinued")
    block = source.presentation.items[0].blocks[1]
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == "First\r\n\r\n<!-- sj:ref=8 -->\r\nSecond\ncontinued"


@pytest.mark.parametrize("case", ["ordinary", "crlf-midpoint"])
def test_block_attach_rejects_anchor_that_is_not_a_logical_line_start(case):
    source = parse_markdown("First\r\n\r\nSecond")
    block = source.presentation.items[0].blocks[1]
    syntax = block.source_binding.syntax_span
    start = 1 if case == "ordinary" else source.text.index("\n")
    forged = replace(
        block,
        source_binding=replace(
            block.source_binding,
            syntax_span=replace(syntax, start_offset=start),
        ),
    )
    source = _replace_block(source, block, forged)
    layout = _layout(configurations={8: Configuration()})
    change = SourceReferenceChange(consumer=forged, new_ref_id=8)
    result = _result(source, layout, forged, change)

    with pytest.raises(ValueError):
        apply_reference_edit_to_source(result)


@pytest.mark.parametrize("new_ref_id", [8, 128, 10**400])
@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_block_retarget_replaces_only_the_exact_marker_span(new_ref_id, line_ending):
    text = f"Before{line_ending}{line_ending}<!-- sj:ref=3 -->{line_ending}Body"
    source = parse_markdown(text)
    layout = _layout(configurations={3: Configuration(), new_ref_id: Configuration()})
    block = _consumer(source, layout, 3, "block")
    result = set_consumer_reference(
        source,
        layout,
        _index(source, layout),
        block,
        ref_id=new_ref_id,
    )

    updated = apply_reference_edit_to_source(result)

    expected = text.replace("<!-- sj:ref=3 -->", f"<!-- sj:ref={new_ref_id} -->")
    assert updated.text == expected
    assert _consumer(updated, layout, new_ref_id, "block").config_ref == new_ref_id


@pytest.mark.parametrize(
    "previous",
    [
        "Previous",
        "# Previous",
        "- Previous",
        "```\nPrevious\n```",
    ],
)
@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_block_detach_removes_marker_text_and_preserves_its_line_ending(
    previous, line_ending
):
    marker = "<!-- sj:ref=3 -->"
    text = f"{previous}{line_ending}{line_ending}{marker}{line_ending}Current"
    source = parse_markdown(text)
    layout = _layout(configurations={3: Configuration()})
    block = _consumer(source, layout, 3, "block")
    result = detach_reference(source, layout, _index(source, layout), block)

    updated = apply_reference_edit_to_source(result)

    assert updated.text == text.replace(marker, "")
    assert updated.text.endswith(f"{line_ending}{line_ending}Current")
    assert _index(updated, layout).usages_for(3) == ()


def test_block_detach_at_source_start_preserves_leading_blank_line():
    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    layout = _layout(configurations={3: Configuration()})
    block = _consumer(source, layout, 3, "block")
    result = detach_reference(source, layout, _index(source, layout), block)

    updated = apply_reference_edit_to_source(result)

    assert updated.text == "\nBody"
    assert updated.presentation.items[0].blocks[0].config_ref is None


def test_block_detach_rejects_marker_and_syntax_adjacency_mismatch():
    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    layout = _layout(configurations={3: Configuration()})
    block = _consumer(source, layout, 3, "block")
    syntax = block.source_binding.syntax_span
    forged = replace(
        block,
        source_binding=replace(
            block.source_binding,
            syntax_span=replace(
                syntax,
                start_offset=syntax.start_offset + 1,
            ),
        ),
    )
    source = _replace_block(source, block, forged)
    change = SourceReferenceChange(consumer=forged, new_ref_id=None)
    result = _result(source, layout, forged, change)

    with pytest.raises(ValueError):
        apply_reference_edit_to_source(result)


@pytest.mark.parametrize(
    "opening",
    [
        "<sj-format ref=3>",
        "<sj-format ref =3>",
        "<sj-format ref= 3>",
        "<sj-format ref \t=\t3>",
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        "",
        "日本語",
        "first\nsecond",
        "first\r\nsecond",
        "outer <sj-format ref=4>inner</sj-format>",
    ],
)
def test_inline_retarget_changes_only_id_digits(opening, body):
    text = f"Before {opening}{body}</sj-format> after"
    source = parse_markdown(text, path=Path("slides.md"))
    layout = _layout(
        inline_formats={
            3: InlineFormatConfiguration(),
            4: InlineFormatConfiguration(),
            128: InlineFormatConfiguration(),
        }
    )
    inline = _consumer(source, layout, 3, "inline")
    result = set_consumer_reference(
        source,
        layout,
        _index(source, layout),
        inline,
        ref_id=128,
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == text.replace(opening, opening.replace("3", "128"), 1)
    assert updated.path == source.path
    assert _consumer(updated, layout, 128, "inline").config_ref == 128


@pytest.mark.parametrize(
    "body",
    [
        "",
        "plain",
        "**strong** and *emphasis*",
        "[link](target) and \\(x^2\\)",
        "first\nsecond",
        "first\r\nsecond",
        "outer <sj-format ref=4>inner</sj-format>",
    ],
)
def test_inline_unwrap_removes_only_outer_tags_and_reparses_exact_body(body):
    opening = "<sj-format ref \t=\t3>"
    text = f"Before {opening}{body}</sj-format> after"
    source = parse_markdown(text, path=Path("slides.md"))
    layout = _layout(
        inline_formats={3: InlineFormatConfiguration(), 4: InlineFormatConfiguration()}
    )
    inline = _consumer(source, layout, 3, "inline")
    result = detach_reference(source, layout, _index(source, layout), inline)

    updated = apply_reference_edit_to_source(result)
    expected_text = f"Before {body} after"

    assert updated.text == expected_text
    assert updated == parse_markdown(expected_text, path=source.path)
    if "ref=4" in body:
        assert "<sj-format ref=4>inner</sj-format>" in updated.text


def test_inline_unwrap_adopts_fresh_adjacent_markdown_semantics():
    text = "x<sj-format ref=3>*a*</sj-format>y"
    source = parse_markdown(text)
    layout = _layout(inline_formats={3: InlineFormatConfiguration()})
    inline = _consumer(source, layout, 3, "inline")
    result = detach_reference(source, layout, _index(source, layout), inline)

    updated = apply_reference_edit_to_source(result)

    assert updated.text == "x*a*y"
    assert updated == parse_markdown("x*a*y")


def test_actual_change_parses_once_with_original_path(monkeypatch):
    source = parse_markdown("Body", path=Path("project/slides.md"))
    layout = _layout(configurations={8: Configuration()})
    block = source.presentation.items[0].blocks[0]
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )
    calls = []
    original = parse_markdown

    def tracking_parse(text, *, path=None):
        calls.append((text, path))
        return original(text, path=path)

    monkeypatch.setattr(source_editing, "parse_markdown", tracking_parse)

    updated = apply_reference_edit_to_source(result)

    assert calls == [("<!-- sj:ref=8 -->\nBody", source.path)]
    assert updated.path == source.path


def test_actual_change_performs_no_filesystem_io(monkeypatch):
    source = parse_markdown("Body")
    layout = _layout(configurations={8: Configuration()})
    block = source.presentation.items[0].blocks[0]
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    def forbidden(*args, **kwargs):
        pytest.fail("source application must not access the filesystem")

    monkeypatch.setattr(builtins, "open", forbidden)
    assert apply_reference_edit_to_source(result).text.endswith("Body")


def test_reapplying_the_same_immutable_result_is_deterministic():
    source = parse_markdown("<sj-format ref=3>日本語</sj-format>")
    layout = _layout(
        inline_formats={
            3: InlineFormatConfiguration(),
            8: InlineFormatConfiguration(),
        }
    )
    inline = _consumer(source, layout, 3, "inline")
    result = set_consumer_reference(
        source, layout, _index(source, layout), inline, ref_id=8
    )

    first = apply_reference_edit_to_source(result)
    second = apply_reference_edit_to_source(result)

    assert first == second
    assert first is not second
    assert result.source_document is source
    assert result.selected_consumer is inline


def test_unknown_derived_operation_is_rejected_defensively():
    class UnknownOperationChange(SourceReferenceChange):
        @property
        def operation(self):
            return "future-operation"

    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    block = _consumer(source, layout, 3, "block")
    change = UnknownOperationChange(consumer=block, new_ref_id=8)
    result = _result(source, layout, block, change)

    with pytest.raises(ValueError):
        apply_reference_edit_to_source(result)


def test_inconsistent_derived_kind_is_rejected_defensively():
    class WrongKindChange(SourceReferenceChange):
        @property
        def kind(self):
            return ReferenceKind.INLINE_FORMAT

    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    block = _consumer(source, layout, 3, "block")
    change = WrongKindChange(consumer=block, new_ref_id=8)
    result = _result(source, layout, block, change)

    with pytest.raises(ValueError):
        apply_reference_edit_to_source(result)


def test_original_source_and_m6_result_remain_unchanged():
    text = "<!-- sj:ref=3 -->\r\nBody"
    source = parse_markdown(text)
    layout = _layout(configurations={3: Configuration()})
    block = _consumer(source, layout, 3, "block")
    result = detach_reference(source, layout, _index(source, layout), block)

    updated = apply_reference_edit_to_source(result)

    assert source.text == text
    assert block.config_ref == 3
    assert result.source_document is source
    assert result.source_changes[0].consumer is block
    assert updated.text == "\r\nBody"
