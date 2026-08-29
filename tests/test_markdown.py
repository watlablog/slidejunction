from pathlib import Path

import pytest

import slidejunction
from slidejunction.document import (
    BlockQuote,
    CodeBlock,
    DiagnosticSeverity,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    InlineCode,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    MathBlock,
    Paragraph,
    Section,
    Slide,
    SoftBreak,
    Strong,
    Text,
    ThematicBreak,
)
from slidejunction.markdown import parse_markdown


def _slides(source: str) -> tuple[Slide, ...]:
    items = parse_markdown(source).presentation.items
    slides: list[Slide] = []
    for item in items:
        if isinstance(item, Section):
            slides.append(item.title_slide)
            slides.extend(item.slides)
        else:
            slides.append(item)
    return tuple(slides)


def _codes(source: str) -> list[str]:
    return [
        diagnostic.code
        for diagnostic in parse_markdown(source).presentation.diagnostics
    ]


def test_parser_builds_implicit_h1_h2_and_section_structure() -> None:
    source = "Before\n\n## Unsectioned\n\n# Section\nBody\n\n## Child\n"
    document = parse_markdown(source)

    implicit, unsectioned, section = document.presentation.items
    assert isinstance(implicit, Slide)
    assert implicit.title is None
    assert isinstance(unsectioned, Slide)
    assert unsectioned.title.level == 2
    assert isinstance(section, Section)
    assert section.title_slide.title.level == 1
    assert len(section.title_slide.blocks) == 1
    assert section.slides[0].title.level == 2


def test_nested_h1_h2_and_h3_are_ordinary_headings() -> None:
    source = "> # Nested H1\n> ## Nested H2\n\n### Detail\n"
    (slide,) = _slides(source)

    quote = slide.blocks[0]
    assert isinstance(quote, BlockQuote)
    assert [block.level for block in quote.blocks if isinstance(block, Heading)] == [
        1,
        2,
    ]
    assert isinstance(slide.blocks[1], Heading)
    assert slide.blocks[1].level == 3


def test_nested_child_binding_excludes_parent_prefix_but_is_continuous() -> None:
    source = "> - Paragraph\n>   continued\n"
    quote = _slides(source)[0].blocks[0]
    nested_list = quote.blocks[0]
    paragraph = nested_list.items[0].blocks[0]
    span = paragraph.source_binding.syntax_span

    assert source[span.start_offset : span.end_offset] == ("Paragraph\n>   continued")


def test_empty_and_comment_only_sources_return_one_implicit_slide() -> None:
    empty = _slides("")[0]
    comment_source = "<!-- ordinary -->\n"
    comment = _slides(comment_source)[0]

    assert empty.blocks == ()
    assert empty.source_span.start_offset == empty.source_span.end_offset == 0
    assert comment.blocks == ()
    assert comment.source_span.start_offset == 0
    assert comment.source_span.end_offset == len(comment_source)


def test_slide_spans_own_title_markers_and_end_at_next_slide_start() -> None:
    source = "<!-- sj:ref=3 -->\n## FFT\nBody\n\n<!-- sj:ref=4 -->\n## STFT\nFinal\n"
    first, second = _slides(source)
    next_start = source.index("<!-- sj:ref=4 -->")

    assert first.source_span.start_offset == 0
    assert first.source_span.end_offset == next_start
    assert source[
        first.source_span.start_offset : first.source_span.end_offset
    ].endswith("\n\n")
    assert second.source_span.start_offset == next_start
    assert second.source_span.end_offset == len(source)
    assert first.title.config_ref == 3
    assert second.title.config_ref == 4


def test_source_positions_use_original_crlf_cr_nul_and_unicode_offsets() -> None:
    source = "## 日本\r\nline  \rnext\0\n"
    slide = _slides(source)[0]
    paragraph = slide.blocks[0]

    assert isinstance(paragraph, Paragraph)
    assert paragraph.source_binding.syntax_span.start_offset == source.index("line")
    assert paragraph.source_binding.syntax_span.end_offset == source.index("\n", 7)
    assert isinstance(paragraph.children[1], HardBreak)
    hardbreak = paragraph.children[1].source_span
    assert source[hardbreak.start_offset : hardbreak.end_offset] == "  \r"
    assert paragraph.children[2].value == "next�"


def test_top_level_setext_recovers_literal_paragraph_and_continues() -> None:
    source = "Title\r\n=====\r\nAfter\n"
    (slide,) = _slides(source)
    recovered, after = slide.blocks

    assert isinstance(recovered, Paragraph)
    assert recovered.children == (
        Text(
            value="Title\r\n=====",
            source_span=recovered.source_binding.syntax_span,
        ),
    )
    assert isinstance(after, Paragraph)
    assert _codes(source) == ["unsupported-setext-heading"]


def test_nested_setext_removes_container_prefix_but_keeps_lossless_span() -> None:
    source = "> Title\n> =====\n"
    quote = _slides(source)[0].blocks[0]

    assert isinstance(quote, BlockQuote)
    recovered = quote.blocks[0]
    assert isinstance(recovered, Paragraph)
    text = recovered.children[0]
    assert isinstance(text, Text)
    assert text.value == "Title\n====="
    span = text.source_span
    assert source[span.start_offset : span.end_offset] == "> Title\n> ====="


def test_valid_marker_can_bind_recovered_top_level_setext_paragraph() -> None:
    source = "<!-- sj:ref=8 -->\nTitle\n=====\n"
    recovered = _slides(source)[0].blocks[0]

    assert isinstance(recovered, Paragraph)
    assert recovered.config_ref == 8
    assert recovered.source_binding.config_marker_span is not None


def test_valid_marker_binds_only_immediate_top_level_block() -> None:
    source = "<!-- sj:ref=7 -->\n> Quoted\n"
    block = _slides(source)[0].blocks[0]

    assert isinstance(block, BlockQuote)
    assert block.config_ref == 7
    marker = block.source_binding.config_marker_span
    assert source[marker.start_offset : marker.end_offset] == "<!-- sj:ref=7 -->"


def test_same_reference_can_be_shared_by_separate_markers() -> None:
    source = "<!-- sj:ref=2 -->\nOne\n\n<!-- sj:ref=2 -->\nTwo\n"
    blocks = _slides(source)[0].blocks

    assert [block.config_ref for block in blocks] == [2, 2]
    assert parse_markdown(source).presentation.diagnostics == ()


@pytest.mark.parametrize(
    ("source", "codes"),
    [
        (" <!-- sj:ref=3 -->\nText\n", ["invalid-config-ref-marker"]),
        ("   <!-- sj:ref =3 -->\nText\n", ["invalid-config-ref-marker"]),
        ("<!-- sj:ref=03 -->\nText\n", ["invalid-config-ref-marker"]),
        ("<!-- sj:ref=0 -->\nText\n", ["invalid-config-ref-marker"]),
        ("<!-- sj:ref=3 -->\n\nText\n", ["unused-config-ref"]),
        ("<!-- sj:ref=3 -->\n", ["unused-config-ref"]),
    ],
)
def test_invalid_blank_separated_and_dangling_markers_report_diagnostics(
    source: str,
    codes: list[str],
) -> None:
    assert _codes(source) == codes
    assert (
        _slides(source)[0].blocks[-1].config_ref is None if "Text" in source else True
    )


def test_consecutive_markers_make_only_the_last_marker_bind() -> None:
    source = "<!-- sj:ref=1 -->\n<!-- sj:ref=2 -->\nText\n"
    document = parse_markdown(source)
    block = _slides(source)[0].blocks[0]

    assert block.config_ref == 2
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == [
        "unused-config-ref"
    ]


def test_nested_valid_and_invalid_markers_are_nonbinding_diagnostics() -> None:
    valid = parse_markdown("> <!-- sj:ref=3 -->\n> Text\n")
    invalid = parse_markdown("> <!-- sj:ref =3 -->\n> Text\n")

    valid_quote = valid.presentation.items[0].blocks[0]
    invalid_quote = invalid.presentation.items[0].blocks[0]
    assert valid_quote.config_ref is None
    assert valid_quote.blocks[0].config_ref is None
    assert [item.code for item in valid.presentation.diagnostics] == [
        "unsupported-nested-config-ref"
    ]
    assert [item.code for item in invalid.presentation.diagnostics] == [
        "invalid-config-ref-marker"
    ]
    assert invalid_quote.blocks[0].config_ref is None


@pytest.mark.parametrize(
    "source",
    [
        "    <!-- sj:ref=3 -->\n",
        "```markdown\n<!-- sj:ref =3 -->\n```\n",
        "`<!-- sj:ref=3 -->`\n",
    ],
)
def test_marker_like_text_in_code_has_no_marker_diagnostic(source: str) -> None:
    document = parse_markdown(source)

    assert document.presentation.diagnostics == ()


@pytest.mark.parametrize(
    "intervening",
    [
        "<!-- ordinary -->\n",
        "<!-- sj:ref =4 -->\n",
        "<div>raw</div>\n\n",
        "[id]: target\n",
    ],
)
def test_source_constructs_stop_pending_marker_binding(intervening: str) -> None:
    source = f"<!-- sj:ref=3 -->\n{intervening}Paragraph\n"
    document = parse_markdown(source)
    paragraph = _slides(source)[0].blocks[-1]

    assert paragraph.config_ref is None
    assert "unused-config-ref" in [
        diagnostic.code for diagnostic in document.presentation.diagnostics
    ]


def test_inline_raw_html_keeps_paragraph_binding_but_is_omitted() -> None:
    source = "<!-- sj:ref=3 -->\nA <b>x</b> z\n"
    document = parse_markdown(source)
    paragraph = _slides(source)[0].blocks[0]

    assert isinstance(paragraph, Paragraph)
    assert paragraph.config_ref == 3
    assert "".join(
        child.value for child in paragraph.children if isinstance(child, Text)
    ) == ("A x z")
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == [
        "unsupported-raw-html",
        "unsupported-raw-html",
    ]


def test_standalone_raw_html_stops_binding_without_hiding_following_markdown() -> None:
    source = "<!-- sj:ref=3 -->\n<div>\nParagraph\n"
    document = parse_markdown(source)
    paragraph = _slides(source)[0].blocks[0]

    assert isinstance(paragraph, Paragraph)
    assert paragraph.children[0].value == "Paragraph"
    assert paragraph.config_ref is None
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == [
        "unused-config-ref",
        "unsupported-raw-html",
    ]


def test_ordinary_inline_comment_is_hidden_without_raw_html_diagnostic() -> None:
    source = "Before <!-- note --> after\n"
    paragraph = _slides(source)[0].blocks[0]

    assert isinstance(paragraph, Paragraph)
    assert [child.value for child in paragraph.children if isinstance(child, Text)] == [
        "Before ",
        " after",
    ]
    assert parse_markdown(source).presentation.diagnostics == ()


def test_commonmark_blocks_and_inlines_map_to_document_model() -> None:
    source = (
        "Paragraph with **strong**, *em*, `code`, [link](target), and image "
        "![alt](image.png).  \nnext\nsoft\n\n"
        "- item\n\n> quote\n\n```python\nprint(1)\n```\n\n---\n"
    )
    slide = _slides(source)[0]
    paragraph, list_block, quote, code, thematic = slide.blocks

    assert isinstance(paragraph, Paragraph)
    assert any(isinstance(child, Strong) for child in paragraph.children)
    assert any(isinstance(child, Emphasis) for child in paragraph.children)
    assert any(isinstance(child, InlineCode) for child in paragraph.children)
    assert any(isinstance(child, Link) for child in paragraph.children)
    assert any(isinstance(child, InlineImage) for child in paragraph.children)
    assert any(isinstance(child, HardBreak) for child in paragraph.children)
    assert any(isinstance(child, SoftBreak) for child in paragraph.children)
    assert isinstance(list_block, ListBlock)
    assert isinstance(quote, BlockQuote)
    assert isinstance(code, CodeBlock)
    assert code.language == "python"
    assert isinstance(thematic, ThematicBreak)


def test_image_only_paragraph_is_promoted_but_linked_image_is_not() -> None:
    source = "![*alt* &amp; `code`](one.png)\n\n[![alt](two.png)](target)\n"
    promoted, linked = _slides(source)[0].blocks

    assert isinstance(promoted, ImageBlock)
    assert promoted.alt == "alt & code"
    assert isinstance(linked, Paragraph)
    assert isinstance(linked.children[0], Link)


def test_inline_math_preserves_payload_and_unterminated_math_recovers() -> None:
    source = "A \\( x + 1 \\) B\n\nBefore \\(unfinished\n## Next\n"
    document = parse_markdown(source)
    first, _next = _slides(source)
    first_paragraph, recovered = first.blocks

    assert isinstance(first_paragraph, Paragraph)
    math = next(
        child for child in first_paragraph.children if isinstance(child, InlineMath)
    )
    assert math.content == " x + 1 "
    assert source[math.source_span.start_offset : math.source_span.end_offset] == (
        "\\( x + 1 \\)"
    )
    assert isinstance(recovered, Paragraph)
    assert "unterminated-inline-math" in [
        diagnostic.code for diagnostic in document.presentation.diagnostics
    ]


def test_inline_math_uses_first_unescaped_closer() -> None:
    source = r"\(a \\) b \) after"
    paragraph = _slides(source)[0].blocks[0]
    math = next(child for child in paragraph.children if isinstance(child, InlineMath))

    assert math.content == r"a \\) b "
    assert paragraph.children[-1].value == " after"


def test_inline_math_inside_link_has_semantics_and_exact_spans() -> None:
    source = r"[value \(x^2\)](target)"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    link = paragraph.children[0]

    assert isinstance(link, Link)
    assert [type(child) for child in link.children] == [Text, InlineMath]
    math = link.children[1]
    assert isinstance(math, InlineMath)
    assert math.content == "x^2"
    assert source[link.source_span.start_offset : link.source_span.end_offset] == source
    assert source[math.source_span.start_offset : math.source_span.end_offset] == (
        r"\(x^2\)"
    )
    assert document.presentation.diagnostics == ()


@pytest.mark.parametrize(
    ("source", "container_type"),
    [
        (r"**value \(x^2\)**", Strong),
        (r"*value \(x^2\)*", Emphasis),
    ],
)
def test_inline_math_inside_emphasis_containers_has_exact_spans(
    source: str,
    container_type: type[Strong] | type[Emphasis],
) -> None:
    paragraph = parse_markdown(source).presentation.items[0].blocks[0]
    container = paragraph.children[0]

    assert isinstance(container, container_type)
    math = container.children[1]
    assert isinstance(math, InlineMath)
    assert (
        source[container.source_span.start_offset : container.source_span.end_offset]
        == source
    )
    assert source[math.source_span.start_offset : math.source_span.end_offset] == (
        r"\(x^2\)"
    )


def test_inline_math_inside_image_alt_preserves_existing_plain_text_policy() -> None:
    source = r"before ![value \(x^2\)](image.png) after"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    image = next(
        child for child in paragraph.children if isinstance(child, InlineImage)
    )

    assert image.alt == "value x^2"
    assert source[image.source_span.start_offset : image.source_span.end_offset] == (
        r"![value \(x^2\)](image.png)"
    )
    assert document.presentation.diagnostics == ()


def test_unterminated_inline_math_prevents_link_and_recovers_to_line_end() -> None:
    source = r"[value \(unfinished](target)"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]

    assert [type(child) for child in paragraph.children] == [Text, Text]
    assert [child.value for child in paragraph.children] == [
        "[value ",
        r"\(unfinished](target)",
    ]
    assert not any(isinstance(child, Link) for child in paragraph.children)
    assert _codes(source) == ["unterminated-inline-math"]
    recovered = paragraph.children[1]
    assert (
        source[recovered.source_span.start_offset : recovered.source_span.end_offset]
        == r"\(unfinished](target)"
    )


def test_block_math_preserves_payload_line_endings_and_container_semantics() -> None:
    source = "> \\[\n> a = 1\r\n> \\]\n"
    quote = _slides(source)[0].blocks[0]
    math = quote.blocks[0]

    assert isinstance(math, MathBlock)
    assert math.content == "\na = 1\r\n"
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == "> \\[\n> a = 1\r\n> \\]"


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_multiline_math_preserves_payload_indentation_and_line_endings(
    line_ending: str,
) -> None:
    source = line_ending.join([r"\[", "  x = 1", "    y = 2", r"\]", ""])
    math = parse_markdown(source).presentation.items[0].blocks[0]

    assert isinstance(math, MathBlock)
    assert math.content == line_ending.join(["", "  x = 1", "    y = 2", ""])
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == source.removesuffix(
        line_ending
    )


def test_blockquote_math_separates_prefix_from_payload_indentation() -> None:
    source = "> \\[\n>   x = 1\n>     y = 2\n> \\]\n"
    quote = parse_markdown(source).presentation.items[0].blocks[0]
    math = quote.blocks[0]

    assert isinstance(math, MathBlock)
    assert math.content == "\n  x = 1\n    y = 2\n"
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == source.removesuffix("\n")


def test_list_math_separates_container_indent_from_payload_indent() -> None:
    source = "- item\n\n  \\[\n    x = 1\n  \\]\n"
    list_block = parse_markdown(source).presentation.items[0].blocks[0]
    math = list_block.items[0].blocks[-1]

    assert isinstance(math, MathBlock)
    assert math.content == "\n  x = 1\n"
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == (
        "  \\[\n    x = 1\n  \\]"
    )


@pytest.mark.parametrize("indent", range(6))
def test_top_level_math_closer_requires_zero_to_three_local_spaces(
    indent: int,
) -> None:
    source = "\\[\nx = 1\n" + " " * indent + "\\]\n"
    document = parse_markdown(source)
    math_blocks = [
        block
        for block in document.presentation.items[0].blocks
        if isinstance(block, MathBlock)
    ]

    assert bool(math_blocks) is (indent <= 3)
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == (
        [] if indent <= 3 else ["unterminated-block-math"]
    )


@pytest.mark.parametrize("indent", range(5))
def test_blockquote_math_closer_uses_container_relative_local_indent(
    indent: int,
) -> None:
    source = "> \\[\n> x = 1\n> " + " " * indent + "\\]\n"
    document = parse_markdown(source)
    quote = document.presentation.items[0].blocks[0]
    math_blocks = [block for block in quote.blocks if isinstance(block, MathBlock)]

    assert bool(math_blocks) is (indent <= 3)
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == (
        [] if indent <= 3 else ["unterminated-block-math"]
    )


@pytest.mark.parametrize("indent", range(5))
def test_list_math_closer_excludes_required_container_indent(indent: int) -> None:
    source = "- item\n\n  \\[\n  x = 1\n" + " " * (2 + indent) + "\\]\n"
    document = parse_markdown(source)
    list_block = document.presentation.items[0].blocks[0]
    math_blocks = [
        block for block in list_block.items[0].blocks if isinstance(block, MathBlock)
    ]

    assert bool(math_blocks) is (indent <= 3)
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == (
        [] if indent <= 3 else ["unterminated-block-math"]
    )


def test_invalid_indented_closer_is_payload_when_later_valid_closer_exists() -> None:
    source = "\\[\nx = 1\n    \\]\n\\]\n"
    math = parse_markdown(source).presentation.items[0].blocks[0]

    assert isinstance(math, MathBlock)
    assert math.content == "\nx = 1\n    \\]\n"
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == source.removesuffix("\n")


def test_invalid_indented_closer_does_not_hide_following_heading() -> None:
    source = "\\[\nx = 1\n    \\]\n## Next\n"
    document = parse_markdown(source)
    recovered, next_slide = _slides(source)

    assert not any(isinstance(block, MathBlock) for block in recovered.blocks)
    assert next_slide.title.children[0].value == "Next"
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == [
        "unterminated-block-math"
    ]


def test_public_inline_nodes_retain_exact_markdown_syntax_spans() -> None:
    source = (
        r"**strong \(a\)** *emphasis* [link \(b\)](target) `code` "
        r"![alt](image.png) \(c\)"
    )
    paragraph = parse_markdown(source).presentation.items[0].blocks[0]
    strong = next(child for child in paragraph.children if isinstance(child, Strong))
    emphasis = next(
        child for child in paragraph.children if isinstance(child, Emphasis)
    )
    link = next(child for child in paragraph.children if isinstance(child, Link))
    code = next(child for child in paragraph.children if isinstance(child, InlineCode))
    image = next(
        child for child in paragraph.children if isinstance(child, InlineImage)
    )
    math = paragraph.children[-1]

    expected = [
        (strong, r"**strong \(a\)**"),
        (emphasis, "*emphasis*"),
        (link, r"[link \(b\)](target)"),
        (code, "`code`"),
        (image, "![alt](image.png)"),
        (math, r"\(c\)"),
    ]
    for node, syntax in expected:
        assert (
            source[node.source_span.start_offset : node.source_span.end_offset]
            == syntax
        )


def test_same_line_and_empty_block_math_are_supported() -> None:
    source = "\\[  x  \\]\n\n\\[\\]\n"
    blocks = _slides(source)[0].blocks

    assert [block.content for block in blocks if isinstance(block, MathBlock)] == [
        "  x  ",
        "",
    ]


def test_unterminated_block_math_recovers_only_opener_line() -> None:
    source = "\\[\n## Next\n"
    document = parse_markdown(source)
    recovered, next_slide = _slides(source)

    assert isinstance(recovered.blocks[0], Paragraph)
    assert recovered.blocks[0].children[0].value == "\\["
    assert next_slide.title.children[0].value == "Next"
    assert _codes(source) == ["unterminated-block-math"]
    assert document.text == source


@pytest.mark.parametrize("opener", ["\\[ x", "\\[ x \\] trailing"])
def test_invalid_same_line_block_math_recovers_literal_line(opener: str) -> None:
    source = f"{opener}\nAfter\n"
    recovered = _slides(source)[0].blocks[0]

    assert isinstance(recovered, Paragraph)
    assert recovered.children[0].value == opener
    assert _codes(source) == ["unterminated-block-math"]


def test_path_is_provenance_only_and_does_not_touch_filesystem(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist" / "slides.md"
    document = parse_markdown("## Slide", path=missing)

    assert document.path == missing
    assert not missing.exists()


def test_parse_markdown_is_not_added_to_top_level_api() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "parse_markdown")
    assert parse_markdown("## Slide").presentation.items


def test_diagnostics_are_sorted_in_source_order() -> None:
    source = "<!-- sj:ref=1 -->\n\n<div>x</div>\n\nTitle\n=====\n"
    diagnostics = parse_markdown(source).presentation.diagnostics

    assert [item.source_span.start_offset for item in diagnostics] == sorted(
        item.source_span.start_offset for item in diagnostics
    )
    assert all(item.severity in DiagnosticSeverity for item in diagnostics)
