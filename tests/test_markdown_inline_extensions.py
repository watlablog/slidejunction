import pytest

from slidejunction.document import (
    CodeBlock,
    Emphasis,
    HardBreak,
    ImageBlock,
    Inline,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    MathBlock,
    Paragraph,
    SoftBreak,
    Strong,
    Subscript,
    Superscript,
    Text,
)
from slidejunction.markdown import parse_markdown


def _paragraph(source: str, index: int = 0) -> Paragraph:
    item = parse_markdown(source).presentation.items[0]
    block = item.blocks[index]
    assert isinstance(block, Paragraph)
    return block


def _syntax(source: str, node: Inline) -> str:
    span = node.source_span
    return source[span.start_offset : span.end_offset]


def _codes(source: str) -> list[str]:
    return [
        diagnostic.code
        for diagnostic in parse_markdown(source).presentation.diagnostics
    ]


def _walk(children: tuple[Inline, ...]) -> list[Inline]:
    result: list[Inline] = []
    for child in children:
        result.append(child)
        nested = getattr(child, "children", None)
        if isinstance(nested, tuple):
            result.extend(_walk(nested))
    return result


def test_inline_format_builds_model_with_exact_outer_and_child_spans() -> None:
    source = "before <sj-format ref=8>重要</sj-format> after"
    paragraph = _paragraph(source)
    formatted = next(
        child for child in paragraph.children if isinstance(child, InlineFormat)
    )

    assert formatted.config_ref == 8
    assert _syntax(source, formatted) == "<sj-format ref=8>重要</sj-format>"
    assert formatted.children == (
        Text(value="重要", source_span=formatted.children[0].source_span),
    )
    assert _syntax(source, formatted.children[0]) == "重要"
    assert _codes(source) == []


@pytest.mark.parametrize(
    "opening",
    [
        "<sj-format ref=8>",
        "<sj-format ref =8>",
        "<sj-format ref= 8>",
        "<sj-format ref \t=\t8>",
    ],
)
def test_inline_format_allows_ascii_horizontal_space_only_around_equals(
    opening: str,
) -> None:
    source = f"{opening}x</sj-format>"
    formatted = _paragraph(source).children[0]

    assert isinstance(formatted, InlineFormat)
    assert formatted.config_ref == 8
    assert _syntax(source, formatted) == source


def test_inline_format_supports_empty_nested_and_shared_references() -> None:
    source = (
        "<sj-format ref=3></sj-format> "
        "<sj-format ref=3>outer <sj-format ref=3>inner</sj-format></sj-format>"
    )
    paragraph = _paragraph(source)
    formats = [
        node for node in _walk(paragraph.children) if isinstance(node, InlineFormat)
    ]

    assert [node.config_ref for node in formats] == [3, 3, 3]
    assert formats[0].children == ()
    assert _syntax(source, formats[-1]) == "<sj-format ref=3>inner</sj-format>"


def test_inline_format_may_span_breaks_within_one_inline_block() -> None:
    source = "<sj-format ref=4>soft\nnext  \nhard</sj-format>\n"
    formatted = _paragraph(source).children[0]

    assert isinstance(formatted, InlineFormat)
    assert [type(child) for child in formatted.children] == [
        Text,
        SoftBreak,
        Text,
        HardBreak,
        Text,
    ]
    assert _syntax(source, formatted) == source.rstrip("\n")


@pytest.mark.parametrize(
    "source",
    [
        "<sj-format ref=4>first\n\nsecond</sj-format>\n",
        "<sj-format ref=4>first\n\n## second</sj-format>\n",
        "<sj-format ref=4>first\n\n# second</sj-format>\n",
    ],
)
def test_inline_format_never_crosses_a_markdown_block_boundary(source: str) -> None:
    document = parse_markdown(source)
    inlines: list[Inline] = []
    for item in document.presentation.items:
        slides = (
            (item,) if hasattr(item, "blocks") else (item.title_slide, *item.slides)
        )
        for slide in slides:
            if slide.title is not None:
                inlines.extend(_walk(slide.title.children))
            for block in slide.blocks:
                if isinstance(block, Paragraph):
                    inlines.extend(_walk(block.children))

    assert not any(isinstance(node, InlineFormat) for node in inlines)
    assert _codes(source) == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]


@pytest.mark.parametrize(
    ("tag", "expected_literal"),
    [
        ("<sj-format>", "<sj-format>"),
        ("<sj-format ref=0>", "<sj-format ref=0>"),
        ("<sj-format ref=03>", "<sj-format ref=03>"),
        ("<sj-format color=8>", "<sj-format color=8>"),
        ("<sj-format ref=8 extra=x>", "<sj-format ref=8 extra=x>"),
        ("<sj-format ref=8 >", "<sj-format ref=8 >"),
        ("<sj-format ref=8 no closer", "<sj-format ref=8 no closer"),
    ],
)
def test_invalid_inline_format_tag_recovers_original_literal(
    tag: str,
    expected_literal: str,
) -> None:
    source = f"before {tag}\nafter"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    recovered = next(
        child
        for child in paragraph.children
        if isinstance(child, Text) and child.value == expected_literal
    )

    assert _syntax(source, recovered) == expected_literal
    assert _codes(source) == ["invalid-inline-format-tag"]


def test_unterminated_and_unexpected_inline_format_recover_exact_literals() -> None:
    unterminated = "<sj-format ref=8>content"
    unexpected = "content </sj-format>"
    first = _paragraph(unterminated)
    second = _paragraph(unexpected)

    assert [child.value for child in first.children if isinstance(child, Text)] == [
        "<sj-format ref=8>",
        "content",
    ]
    assert [child.value for child in second.children if isinstance(child, Text)] == [
        "content ",
        "</sj-format>",
    ]
    assert _codes(unterminated) == ["unterminated-inline-format"]
    assert _codes(unexpected) == ["unexpected-inline-format-close"]
    assert all(_syntax(unterminated, child) == child.value for child in first.children)
    assert all(_syntax(unexpected, child) == child.value for child in second.children)


def test_inline_format_and_commonmark_containers_nest_in_both_directions() -> None:
    source = (
        "<sj-format ref=8>**bold** *em* [link](target)</sj-format> "
        "**<sj-format ref=9>inside</sj-format>** "
        "[<sj-format ref=10>label</sj-format>](destination)"
    )
    paragraph = _paragraph(source)
    first = paragraph.children[0]
    outer_strong = paragraph.children[2]
    outer_link = paragraph.children[4]

    assert isinstance(first, InlineFormat)
    assert [type(child) for child in first.children if not isinstance(child, Text)] == [
        Strong,
        Emphasis,
        Link,
    ]
    assert isinstance(outer_strong, Strong)
    assert isinstance(outer_strong.children[0], InlineFormat)
    assert isinstance(outer_link, Link)
    assert isinstance(outer_link.children[0], InlineFormat)


def test_inline_format_can_contain_math_and_child_recovery_without_failing() -> None:
    source = r"<sj-format ref=8>\(x^2\) ^{unfinished</sj-format>"
    formatted = _paragraph(source).children[0]

    assert isinstance(formatted, InlineFormat)
    assert any(isinstance(child, InlineMath) for child in formatted.children)
    assert not any(isinstance(child, Superscript) for child in formatted.children)
    assert _codes(source) == []


def test_inline_format_closer_inside_inline_code_does_not_close_outer() -> None:
    source = "<sj-format ref=8>`</sj-format>` tail</sj-format>"
    formatted = _paragraph(source).children[0]

    assert isinstance(formatted, InlineFormat)
    assert [type(child) for child in formatted.children] == [InlineCode, Text]
    assert _syntax(source, formatted) == source
    assert _codes(source) == []


@pytest.mark.parametrize(
    ("source", "node_type", "content"),
    [
        ("x^{2}", Superscript, "2"),
        ("H_{2}O", Subscript, "2"),
        ("^{}", Superscript, ""),
        ("_{}", Subscript, ""),
        ("^{a_{i}}", Superscript, "a"),
    ],
)
def test_superscript_and_subscript_build_balanced_nodes(
    source: str,
    node_type: type[Superscript] | type[Subscript],
    content: str,
) -> None:
    nodes = _walk(_paragraph(source).children)
    node = next(item for item in nodes if isinstance(item, node_type))

    assert _syntax(source, node).startswith("^{" if node_type is Superscript else "_{")
    assert (
        "".join(child.value for child in node.children if isinstance(child, Text))
        == content
    )
    assert _codes(source) == []


def test_script_matching_ignores_escaped_nested_and_opaque_braces() -> None:
    source = "^{a\\}b {c} `}` \\(}\\) _{i}}"
    outer = _paragraph(source).children[0]

    assert isinstance(outer, Superscript)
    assert isinstance(outer.children[-1], Subscript)
    assert _syntax(source, outer) == source


@pytest.mark.parametrize("source", ["^{unfinished", "_{unfinished", "x ^{a {b}"])
def test_unbalanced_script_uses_commonmark_without_custom_diagnostic(
    source: str,
) -> None:
    document = parse_markdown(source)
    nodes = _walk(document.presentation.items[0].blocks[0].children)

    assert not any(isinstance(node, Superscript | Subscript) for node in nodes)
    assert document.presentation.diagnostics == ()


def test_extensions_are_disabled_inside_inline_code_and_inline_math() -> None:
    source = (
        r"`<sj-format ref=8>x</sj-format> ^{2} _{i}` "
        r"\(<sj-format ref=8>x</sj-format> ^{2} _{i}\)"
    )
    paragraph = _paragraph(source)

    assert [
        type(child) for child in paragraph.children if not isinstance(child, Text)
    ] == [
        InlineCode,
        InlineMath,
    ]
    assert not any(
        isinstance(node, InlineFormat | Superscript | Subscript)
        for node in _walk(paragraph.children)
    )
    assert _codes(source) == []


def test_extensions_are_disabled_inside_code_and_math_blocks() -> None:
    source = (
        "```markdown\n<sj-format ref=8>x</sj-format> ^{2} _{i}\n```\n\n"
        "\\[\n<sj-format ref=8>x</sj-format> ^{2} _{i}\n\\]\n"
    )
    blocks = parse_markdown(source).presentation.items[0].blocks

    assert [type(block) for block in blocks] == [CodeBlock, MathBlock]
    assert blocks[0].code == "<sj-format ref=8>x</sj-format> ^{2} _{i}\n"
    assert blocks[1].content == "\n<sj-format ref=8>x</sj-format> ^{2} _{i}\n"
    assert _codes(source) == []


def test_commonmark_escape_is_the_user_authored_literal_mechanism() -> None:
    source = r"\<sj-format ref=8>x\</sj-format> \^{2} \_{i}"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    nodes = _walk(paragraph.children)

    assert not any(
        isinstance(node, InlineFormat | Superscript | Subscript) for node in nodes
    )
    assert "".join(node.value for node in nodes if isinstance(node, Text)) == (
        "<sj-format ref=8>x</sj-format> ^{2} _{i}"
    )
    assert document.text == source
    assert document.presentation.diagnostics == ()


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_extension_spans_map_to_original_line_endings_and_unicode(
    line_ending: str,
) -> None:
    source = f"<sj-format ref=8>日{line_ending}本\0^{{語}}</sj-format>{line_ending}"
    formatted = _paragraph(source).children[0]
    superscript = next(
        node for node in _walk(formatted.children) if isinstance(node, Superscript)
    )

    assert isinstance(formatted, InlineFormat)
    assert _syntax(source, formatted) == source.removesuffix(line_ending)
    assert _syntax(source, superscript) == "^{語}"
    assert any(
        isinstance(child, Text) and "�" in child.value for child in formatted.children
    )


def test_valid_image_alt_extensions_flatten_without_creating_ref_consumers() -> None:
    source = "before ![A <sj-format ref=8>bold</sj-format> ^{2} _{i}](image.png) after"
    paragraph = _paragraph(source)
    image = next(
        child for child in paragraph.children if isinstance(child, InlineImage)
    )

    assert image.alt == "A bold 2 i"
    assert _syntax(source, image) == (
        "![A <sj-format ref=8>bold</sj-format> ^{2} _{i}](image.png)"
    )
    assert not any(isinstance(node, InlineFormat) for node in paragraph.children)
    assert _codes(source) == []


def test_link_image_alt_format_has_exact_public_spans() -> None:
    source = "[![<sj-format ref=8>x</sj-format>](img)](outer)"
    document = parse_markdown(source)
    link = document.presentation.items[0].blocks[0].children[0]

    assert isinstance(link, Link)
    image = link.children[0]
    assert isinstance(image, InlineImage)
    assert image.alt == "x"
    assert _syntax(source, link) == source
    assert _syntax(source, image) == "![<sj-format ref=8>x</sj-format>](img)"
    assert document.presentation.diagnostics == ()


def test_link_image_alt_recovery_uses_exact_original_source() -> None:
    source = "[![<sj-format ref=8>x](img) tail](outer) outside </sj-format>"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    link = paragraph.children[0]

    assert isinstance(link, Link)
    image = link.children[0]
    assert isinstance(image, InlineImage)
    assert image.alt == "<sj-format ref=8>x"
    assert _syntax(source, link) == "[![<sj-format ref=8>x](img) tail](outer)"
    assert _syntax(source, image) == "![<sj-format ref=8>x](img)"

    diagnostics = document.presentation.diagnostics
    assert [item.code for item in diagnostics] == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]
    assert [
        source[item.source_span.start_offset : item.source_span.end_offset]
        for item in diagnostics
    ] == ["<sj-format ref=8>", "</sj-format>"]


def test_native_container_rebase_keeps_link_image_recovery_exact() -> None:
    source = "<sj-format ref=1>[![<sj-format ref=8>x](img)](outer)</sj-format>"
    document = parse_markdown(source)
    outer = document.presentation.items[0].blocks[0].children[0]

    assert isinstance(outer, InlineFormat)
    link = outer.children[0]
    assert isinstance(link, Link)
    image = link.children[0]
    assert isinstance(image, InlineImage)
    assert image.alt == "<sj-format ref=8>x"
    assert _syntax(source, outer) == source
    assert _syntax(source, link) == "[![<sj-format ref=8>x](img)](outer)"
    assert _syntax(source, image) == "![<sj-format ref=8>x](img)"

    diagnostics = document.presentation.diagnostics
    assert [item.code for item in diagnostics] == ["unterminated-inline-format"]
    diagnostic_span = diagnostics[0].source_span
    assert diagnostic_span is not None
    assert source[diagnostic_span.start_offset : diagnostic_span.end_offset] == (
        "<sj-format ref=8>"
    )


def test_strong_link_image_keeps_commonmark_structure_and_exact_spans() -> None:
    source = "**[![alt](img)](outer)**"
    document = parse_markdown(source)
    strong = document.presentation.items[0].blocks[0].children[0]

    assert isinstance(strong, Strong)
    link = strong.children[0]
    assert isinstance(link, Link)
    image = link.children[0]
    assert isinstance(image, InlineImage)
    assert image.alt == "alt"
    assert _syntax(source, strong) == source
    assert _syntax(source, link) == "[![alt](img)](outer)"
    assert _syntax(source, image) == "![alt](img)"
    assert document.presentation.diagnostics == ()


@pytest.mark.parametrize(
    ("alt", "literal", "code"),
    [
        ("<sj-format ref=0>x", "<sj-format ref=0>", "invalid-inline-format-tag"),
        ("<sj-format ref=8>x", "<sj-format ref=8>", "unterminated-inline-format"),
        ("x</sj-format>", "</sj-format>", "unexpected-inline-format-close"),
    ],
)
def test_image_alt_inline_format_recovery_has_exact_original_diagnostic(
    alt: str,
    literal: str,
    code: str,
) -> None:
    source = f"before ![{alt}](image.png) after"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    image = next(
        child for child in paragraph.children if isinstance(child, InlineImage)
    )
    diagnostic = document.presentation.diagnostics[0]

    assert image.alt == alt
    assert diagnostic.code == code
    span = diagnostic.source_span
    assert span is not None
    assert source[span.start_offset : span.end_offset] == literal


def test_native_tags_do_not_emit_raw_html_but_similar_tags_still_do() -> None:
    native = "<sj-format ref=8>x</sj-format>"
    similar = "before <sj-formatting>x</sj-formatting> after"

    assert _codes(native) == []
    assert _codes(similar) == ["unsupported-raw-html", "unsupported-raw-html"]


def test_inline_format_diagnostics_remain_in_source_order() -> None:
    source = "</sj-format> x <sj-format ref=0> y <sj-format ref=8>z"
    diagnostics = parse_markdown(source).presentation.diagnostics

    assert [item.code for item in diagnostics] == [
        "unexpected-inline-format-close",
        "invalid-inline-format-tag",
        "unterminated-inline-format",
    ]
    assert [item.source_span.start_offset for item in diagnostics] == sorted(
        item.source_span.start_offset for item in diagnostics
    )


@pytest.mark.parametrize("image_label", [False, True])
def test_inline_format_cannot_take_a_closer_outside_link_or_image_label(
    image_label: bool,
) -> None:
    source = (
        "![<sj-format ref=8>x](image.png) outside </sj-format>"
        if image_label
        else "[<sj-format ref=8>x](url) outside </sj-format>"
    )
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    first = paragraph.children[0]

    assert isinstance(first, InlineImage if image_label else Link)
    if isinstance(first, InlineImage):
        assert first.alt == "<sj-format ref=8>x"
    else:
        assert [child.value for child in first.children] == [
            "<sj-format ref=8>",
            "x",
        ]
        assert not any(isinstance(node, InlineFormat) for node in _walk(first.children))

    diagnostics = document.presentation.diagnostics
    assert [item.code for item in diagnostics] == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]
    assert [
        source[item.source_span.start_offset : item.source_span.end_offset]
        for item in diagnostics
    ] == ["<sj-format ref=8>", "</sj-format>"]


@pytest.mark.parametrize("image_label", [False, True])
@pytest.mark.parametrize(
    ("marker", "node_type"),
    [("^", Superscript), ("_", Subscript)],
)
def test_unbalanced_script_cannot_take_a_closer_outside_a_label(
    image_label: bool,
    marker: str,
    node_type: type[Superscript] | type[Subscript],
) -> None:
    label = f"x{marker}{{2"
    source = (
        f"![{label}](image.png) outside }}"
        if image_label
        else f"[{label}](url) outside }}"
    )
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    first = paragraph.children[0]

    assert isinstance(first, InlineImage if image_label else Link)
    if isinstance(first, InlineImage):
        assert first.alt == label
    else:
        assert "".join(child.value for child in first.children) == label
        assert not any(isinstance(node, node_type) for node in _walk(first.children))
    assert paragraph.children[-1].value == " outside }"
    assert document.presentation.diagnostics == ()


def test_inline_code_fake_close_inside_label_does_not_close_inline_format() -> None:
    source = "[<sj-format ref=8>`</sj-format>`](url) outside </sj-format>"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    link = paragraph.children[0]

    assert isinstance(link, Link)
    assert [type(child) for child in link.children] == [Text, InlineCode]
    assert link.children[0].value == "<sj-format ref=8>"
    assert link.children[1].code == "</sj-format>"
    assert [item.code for item in document.presentation.diagnostics] == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]


@pytest.mark.parametrize(
    ("marker", "node_type"),
    [("^", Superscript), ("_", Subscript)],
)
def test_recursive_native_constructs_do_not_cross_outer_boundaries(
    marker: str,
    node_type: type[Superscript] | type[Subscript],
) -> None:
    format_source = f"<sj-format ref=1>before {marker}{{x</sj-format> outside }}"
    script_source = f"{marker}{{before <sj-format ref=2>x}} outside </sj-format>"
    formatted = _paragraph(format_source).children[0]
    script_document = parse_markdown(script_source)
    script = script_document.presentation.items[0].blocks[0].children[0]

    assert isinstance(formatted, InlineFormat)
    assert not any(isinstance(node, node_type) for node in _walk(formatted.children))
    assert _syntax(format_source, formatted) == (
        f"<sj-format ref=1>before {marker}{{x</sj-format>"
    )

    assert isinstance(script, node_type)
    assert not any(isinstance(node, InlineFormat) for node in _walk(script.children))
    assert _syntax(script_source, script) == (f"{marker}{{before <sj-format ref=2>x}}")
    assert [item.code for item in script_document.presentation.diagnostics] == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]


def test_recursive_inline_format_respects_a_nested_link_label_boundary() -> None:
    source = "<sj-format ref=1>[<sj-format ref=2>x](url) after </sj-format>"
    document = parse_markdown(source)
    formatted = document.presentation.items[0].blocks[0].children[0]

    assert isinstance(formatted, InlineFormat)
    link = formatted.children[0]
    assert isinstance(link, Link)
    assert not any(isinstance(node, InlineFormat) for node in _walk(link.children))
    assert _syntax(source, formatted) == source
    assert [item.code for item in document.presentation.diagnostics] == [
        "unterminated-inline-format"
    ]


def test_commonmark_nested_bracket_and_link_results_remain_unchanged() -> None:
    bracket = _paragraph("[outer [bracket]](url)")
    nested_link = _paragraph("[outer [inner](one)](two)")
    image_document = parse_markdown("![outer [bracket]](image.png)")
    image = image_document.presentation.items[0].blocks[0]

    assert [type(child) for child in bracket.children] == [Link]
    assert bracket.children[0].children[0].value == "outer [bracket]"
    assert [type(child) for child in nested_link.children] == [Text, Link, Text]
    assert nested_link.children[1].destination == "one"
    assert isinstance(image, ImageBlock)
    assert image.alt == "outer [bracket]"
