from __future__ import annotations

import builtins
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import html_renderer
from slidejunction.document import (
    Emphasis,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    Paragraph,
    Presentation,
    Slide,
    SoftBreak,
    SourceBinding,
    SourceDocument,
    SourceSpan,
    Strong,
    Subscript,
    Superscript,
    Text,
)
from slidejunction.html_renderer import render_static_html
from slidejunction.layout import (
    Appearance,
    Configuration,
    ElementKind,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    Stacking,
    Theme,
    ThemePreset,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import validate_references
from slidejunction.resolver import (
    ResolvedBlock,
    ResolvedInline,
    ResolvedPresentation,
    ResolvedSection,
    ResolvedSlide,
    resolve_presentation,
)

_EXPECTED_SIMPLE_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SlideJunction</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      background: #f3f4f6;
      color: #111827;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    .sj-presentation {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 32px;
      box-sizing: border-box;
      padding: 32px;
    }
    .sj-slide {
      width: 100%;
      max-width: 1280px;
      aspect-ratio: 16 / 9;
      box-sizing: border-box;
      padding: 64px;
      overflow: auto;
      background: #ffffff;
      color: #111827;
      border: 1px solid #d1d5db;
      box-shadow: 0 4px 16px rgba(17, 24, 39, 0.12);
    }
    .sj-slide-title {
      margin-bottom: 32px;
    }
    .sj-slide-title > :first-child,
    .sj-slide-body > :first-child {
      margin-top: 0;
    }
    .sj-slide-title > :last-child,
    .sj-slide-body > :last-child {
      margin-bottom: 0;
    }
    .sj-slide code {
      white-space: pre-wrap;
    }
    .sj-unsupported-block,
    .sj-unsupported-inline {
      border: 1px dashed #d97706;
      background: #fffbeb;
      color: #92400e;
    }
    .sj-unsupported-block {
      padding: 12px;
    }
    .sj-unsupported-inline {
      display: inline-block;
      padding: 0 4px;
    }
    .sj-link--unsafe {
      color: #b91c1c;
      text-decoration: underline wavy;
    }
  </style>
</head>
<body>
  <main class="sj-presentation">
    <section class="sj-slide sj-slide--h2" data-slide-index="1" data-slide-kind="h2">
      <header class="sj-slide-title">
        <h2>Title</h2>
      </header>
      <div class="sj-slide-body">
        <p>Body</p>
      </div>
    </section>
  </main>
</body>
</html>
"""


def _layout(
    *,
    theme: Theme | None = None,
    configurations: dict[int, Configuration] | None = None,
    inline_formats: dict[int, InlineFormatConfiguration] | None = None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=theme
        or Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _resolve(
    source: str,
    layout: LayoutDocument | None = None,
) -> ResolvedPresentation:
    document = parse_markdown(source)
    actual_layout = layout or _layout()
    references = validate_references(document, actual_layout).index
    return resolve_presentation(document, actual_layout, references)


def _span() -> SourceSpan:
    return SourceSpan(
        start_offset=0,
        end_offset=0,
        start_line=0,
        start_column=0,
        end_line=0,
        end_column=0,
    )


def _text(value: str = "text") -> Text:
    return Text(value=value, source_span=_span())


def _programmatic_resolved(
    inlines: tuple[
        Text
        | Strong
        | Emphasis
        | InlineCode
        | Link
        | InlineImage
        | SoftBreak
        | InlineMath
        | InlineFormat
        | Superscript
        | Subscript,
        ...,
    ],
    *,
    layout: LayoutDocument | None = None,
) -> ResolvedPresentation:
    paragraph = Paragraph(
        children=inlines,
        source_binding=SourceBinding(syntax_span=_span()),
    )
    slide = Slide(title=None, blocks=(paragraph,), source_span=_span())
    source = SourceDocument(
        path=None,
        text="",
        presentation=Presentation(items=(slide,)),
    )
    actual_layout = layout or _layout()
    references = validate_references(source, actual_layout).index
    return resolve_presentation(source, actual_layout, references)


def _paragraph_fragment(presentation: ResolvedPresentation) -> str:
    html = render_static_html(presentation)
    start = html.index("<p>")
    end = html.index("</p>", start) + len("</p>")
    return html[start:end]


def test_public_surface_does_not_expand_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "render_static_html")
    assert html_renderer.__all__ == ["render_static_html"]


@pytest.mark.parametrize("invalid", [None, object(), parse_markdown("Text")])
def test_public_api_rejects_wrong_input_type(invalid: object) -> None:
    with pytest.raises(TypeError):
        render_static_html(invalid)  # type: ignore[arg-type]


def test_complete_html_is_exact_and_contains_the_fixed_shell_and_css() -> None:
    html = render_static_html(_resolve("## Title\n\nBody"))

    assert html == _EXPECTED_SIMPLE_HTML
    assert "<script" not in html
    assert "stylesheet" not in html
    assert "\r" not in html
    assert html.endswith("\n")
    assert not html.endswith("\n\n")


def test_empty_implicit_slide_keeps_body_without_blank_content_line() -> None:
    html = render_static_html(_resolve(""))

    assert (
        '    <section class="sj-slide sj-slide--implicit" '
        'data-slide-index="1" data-slide-kind="implicit">\n'
        '      <div class="sj-slide-body">\n'
        "      </div>\n"
        "    </section>"
    ) in html
    assert "sj-slide-title" not in html[html.index("<body>") :]


@pytest.mark.parametrize("source", ["# Empty title", "## Empty title"])
def test_titled_slide_without_blocks_still_keeps_empty_body(source: str) -> None:
    html = render_static_html(_resolve(source))
    lines = html.splitlines()
    body_index = lines.index('      <div class="sj-slide-body">')

    assert lines[body_index : body_index + 2] == [
        '      <div class="sj-slide-body">',
        "      </div>",
    ]
    assert '<header class="sj-slide-title">' in html


def test_valid_empty_resolved_presentation_has_exact_empty_main() -> None:
    source = SourceDocument(
        path=None,
        text="",
        presentation=Presentation(items=()),
    )
    presentation = ResolvedPresentation(source_document=source, items=())

    html = render_static_html(presentation)
    lines = html.splitlines()
    main_index = lines.index('  <main class="sj-presentation">')

    assert lines[main_index : main_index + 2] == [
        '  <main class="sj-presentation">',
        "  </main>",
    ]
    assert html.endswith("</body>\n</html>\n")


def test_flatten_preserves_top_level_and_section_slide_order() -> None:
    source = (
        "## Before\n\nBefore body\n\n"
        "# Section\n\nSection body\n\n"
        "## Child\n\nChild body\n"
    )
    html = render_static_html(_resolve(source))

    openings = [
        line.strip()
        for line in html.splitlines()
        if line.strip().startswith('<section class="sj-slide ')
    ]
    assert openings == [
        (
            '<section class="sj-slide sj-slide--h2" data-slide-index="1" '
            'data-slide-kind="h2">'
        ),
        (
            '<section class="sj-slide sj-slide--h1" data-slide-index="2" '
            'data-slide-kind="h1">'
        ),
        (
            '<section class="sj-slide sj-slide--h2" data-slide-index="3" '
            'data-slide-kind="h2">'
        ),
    ]
    assert (
        html.index("Before body")
        < html.index("Section body")
        < html.index("Child body")
    )


def test_blocks_keep_resolved_tuple_order_despite_opposite_paint_order() -> None:
    source = "<!-- sj:ref=1 -->\nFirst in source\n\n<!-- sj:ref=2 -->\nSecond in source"
    presentation = _resolve(
        source,
        _layout(
            configurations={
                1: Configuration(stacking=Stacking(z_index=100)),
                2: Configuration(stacking=Stacking(z_index=-100)),
            }
        ),
    )
    blocks = presentation.items[0].blocks
    assert [block.configuration.stacking.z_index for block in blocks] == [100, -100]

    html = render_static_html(presentation)

    assert html.index("<p>First in source</p>") < html.index("<p>Second in source</p>")


def test_renderer_uses_resolved_blocks_and_inlines_not_semantic_children() -> None:
    presentation = _resolve("Visible resolved text")
    slide = presentation.items[0]
    block = slide.blocks[0]
    object.__setattr__(slide.node, "blocks", ())
    object.__setattr__(block.node, "children", (_text("semantic sentinel"),))

    html = render_static_html(presentation)

    assert "<p>Visible resolved text</p>" in html
    assert "semantic sentinel" not in html


@pytest.mark.parametrize(
    ("source", "level"),
    [
        ("# One", 1),
        ("## Two", 2),
        ("### Three", 3),
        ("#### Four", 4),
        ("##### Five", 5),
        ("###### Six", 6),
    ],
)
def test_heading_uses_semantic_heading_level(source: str, level: int) -> None:
    html = render_static_html(_resolve(source))

    word = source.split()[-1]
    assert f"<h{level}>{word}</h{level}>" in html


def test_empty_paragraph_is_rendered_as_an_empty_element() -> None:
    assert _paragraph_fragment(_programmatic_resolved(())) == "<p></p>"


@pytest.mark.parametrize(
    ("source", "node_type", "hidden_payloads"),
    [
        ("- private list item", "ListBlock", ("private list item",)),
        ("> private quote", "BlockQuote", ("private quote",)),
        (
            "```python private-info\nprivate code\n```",
            "CodeBlock",
            ("private code", "python", "private-info"),
        ),
        (
            '![private alt](private.png "private title")',
            "ImageBlock",
            ("private alt", "private.png", "private title"),
        ),
        ("---", "ThematicBreak", ()),
        ("\\[\nprivate math\n\\]", "MathBlock", ("private math",)),
    ],
)
def test_unsupported_blocks_use_exact_nonrecursive_placeholder(
    source: str,
    node_type: str,
    hidden_payloads: tuple[str, ...],
) -> None:
    html = render_static_html(_resolve(source))
    expected = (
        f'<div class="sj-unsupported-block" data-node-type="{node_type}">'
        f"[Unsupported block: {node_type}]</div>"
    )

    assert f"        {expected}\n" in html
    for hidden_payload in hidden_payloads:
        assert hidden_payload not in html


def test_supported_inlines_render_without_synthetic_whitespace() -> None:
    source = "A**B***C*`D  E`[F](relative)^{G}_{H}<sj-format ref=8>I</sj-format>J"
    paragraph = _paragraph_fragment(_resolve(source))

    assert paragraph == (
        "<p>A<strong>B</strong><em>C</em><code>D  E</code>"
        '<a class="sj-link" href="relative">F</a>'
        "<sup>G</sup><sub>H</sub>"
        '<span class="sj-inline-format" data-config-ref="8">I</span>J</p>'
    )


def test_deep_inline_containers_preserve_child_order() -> None:
    nested = Strong(
        children=(
            _text("A"),
            Emphasis(
                children=(
                    InlineFormat(
                        config_ref=8,
                        children=(
                            Superscript(children=(_text("B"),), source_span=_span()),
                            Subscript(children=(_text("C"),), source_span=_span()),
                        ),
                        source_span=_span(),
                    ),
                ),
                source_span=_span(),
            ),
            _text("D"),
        ),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((nested,))) == (
        "<p><strong>A<em>"
        '<span class="sj-inline-format" data-config-ref="8">'
        "<sup>B</sup><sub>C</sub></span>"
        "</em>D</strong></p>"
    )


def test_empty_inline_containers_render_exact_empty_elements() -> None:
    inlines = (
        Strong(children=(), source_span=_span()),
        Emphasis(children=(), source_span=_span()),
        Superscript(children=(), source_span=_span()),
        Subscript(children=(), source_span=_span()),
        InlineFormat(config_ref=8, children=(), source_span=_span()),
    )

    assert _paragraph_fragment(_programmatic_resolved(inlines)) == (
        "<p><strong></strong><em></em><sup></sup><sub></sub>"
        '<span class="sj-inline-format" data-config-ref="8"></span></p>'
    )


def test_inline_format_preserves_arbitrary_size_reference_as_decimal() -> None:
    ref_id = 10**400
    formatted = InlineFormat(
        config_ref=ref_id,
        children=(_text("large"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((formatted,))) == (
        f'<p><span class="sj-inline-format" data-config-ref="{ref_id}">large</span></p>'
    )


def test_soft_and_hard_breaks_have_exact_inline_serialization() -> None:
    paragraph = _paragraph_fragment(_resolve("soft\nnext  \nhard"))

    assert paragraph == "<p>soft\nnext<br>hard</p>"


def test_inline_code_preserves_spaces_and_newlines_and_has_pre_wrap_css() -> None:
    code = InlineCode(code="one  two\nthree", source_span=_span())
    html = render_static_html(_programmatic_resolved((code,)))

    assert "<p><code>one  two\nthree</code></p>" in html
    assert "    .sj-slide code {\n      white-space: pre-wrap;\n    }" in html


@pytest.mark.parametrize(
    ("inline", "node_type", "payload"),
    [
        (
            InlineMath(content='<x & "y">', source_span=_span()),
            "InlineMath",
            '&lt;x &amp; "y"&gt;',
        ),
        (
            InlineImage(
                src="secret.png",
                alt='<Diagram & "caption">',
                title="secret title",
                source_span=_span(),
            ),
            "InlineImage",
            '&lt;Diagram &amp; "caption"&gt;',
        ),
        (InlineMath(content="", source_span=_span()), "InlineMath", ""),
        (
            InlineImage(src="secret.png", alt="", source_span=_span()),
            "InlineImage",
            "",
        ),
    ],
)
def test_unsupported_inline_placeholder_preserves_and_escapes_full_payload(
    inline: InlineMath | InlineImage,
    node_type: str,
    payload: str,
) -> None:
    paragraph = _paragraph_fragment(_programmatic_resolved((inline,)))

    assert paragraph == (
        '<p><span class="sj-unsupported-inline" '
        f'data-node-type="{node_type}">'
        f"[Unsupported inline: {node_type}: {payload}]</span></p>"
    )
    assert "secret.png" not in paragraph
    assert "secret title" not in paragraph


def test_text_code_and_link_attributes_use_context_appropriate_escaping() -> None:
    inlines = (
        _text('<script>alert("x") & tail</script>'),
        InlineCode(code='<b>& "code"</b>', source_span=_span()),
        Link(
            destination='https://example.test/?a=1&b="2"',
            title='"quoted" & <title>',
            children=(_text("<label>"),),
            source_span=_span(),
        ),
    )
    paragraph = _paragraph_fragment(_programmatic_resolved(inlines))

    assert paragraph == (
        '<p>&lt;script&gt;alert("x") &amp; tail&lt;/script&gt;'
        '<code>&lt;b&gt;&amp; "code"&lt;/b&gt;</code>'
        '<a class="sj-link" '
        'href="https://example.test/?a=1&amp;b=&quot;2&quot;" '
        'title="&quot;quoted&quot; &amp; &lt;title&gt;">'
        "&lt;label&gt;</a></p>"
    )
    assert "<script>" not in paragraph
    assert "<b>" not in paragraph


@pytest.mark.parametrize(
    "destination",
    [
        "",
        "relative/path",
        "./relative",
        "../relative",
        "/root-relative",
        "?query=yes",
        "#fragment",
        "http://example.test/path",
        "https://example.test/path",
        "mailto:user@example.test",
        "HTTP://EXAMPLE.TEST",
        "MAILTO:user@example.test",
    ],
)
def test_safe_link_destinations_keep_the_exact_original_href(
    destination: str,
) -> None:
    link = Link(
        destination=destination,
        children=(_text("label"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((link,))) == (
        f'<p><a class="sj-link" href="{destination}">label</a></p>'
    )


@pytest.mark.parametrize(
    "destination",
    [
        "javascript:alert(1)",
        "data:text/html,bad",
        "vbscript:bad",
        "file:///tmp/secret",
        "custom:value",
        "//example.test/path",
        "///example.test/path",
        "////example.test/path",
        r"\\example.test\path",
        r"/\example.test/path",
        r"\/example.test/path",
        r"relative\path",
        r"https:\example.test",
        " leading",
        "trailing ",
        "\u00a0relative",
        "relative\u3000",
        "http://[::1",
    ],
)
def test_unsafe_link_destinations_omit_href(destination: str) -> None:
    link = Link(
        destination=destination,
        title="kept",
        children=(_text("label"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((link,))) == (
        '<p><a class="sj-link sj-link--unsafe" title="kept">label</a></p>'
    )


@pytest.mark.parametrize("codepoint", [*range(0x20), 0x7F])
def test_every_ascii_control_character_makes_a_link_unsafe(codepoint: int) -> None:
    link = Link(
        destination=f"before{chr(codepoint)}after",
        children=(_text("label"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((link,))) == (
        '<p><a class="sj-link sj-link--unsafe">label</a></p>'
    )


def test_link_attribute_order_and_empty_title_are_stable() -> None:
    safe = Link(
        destination="/safe",
        title="",
        children=(_text(),),
        source_span=_span(),
    )
    unsafe = Link(
        destination="javascript:bad",
        title="",
        children=(_text(),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((safe,))) == (
        '<p><a class="sj-link" href="/safe" title="">text</a></p>'
    )
    assert _paragraph_fragment(_programmatic_resolved((unsafe,))) == (
        '<p><a class="sj-link sj-link--unsafe" title="">text</a></p>'
    )


def test_unsafe_link_title_is_attribute_escaped() -> None:
    link = Link(
        destination="javascript:bad",
        title='"quoted" & <title>',
        children=(_text("label"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((link,))) == (
        '<p><a class="sj-link sj-link--unsafe" '
        'title="&quot;quoted&quot; &amp; &lt;title&gt;">label</a></p>'
    )


def _nested_link(*, outer_destination: str, indirect: str | None = None) -> Link:
    child: Text | Link | Strong | Emphasis | InlineFormat | Superscript | Subscript
    child = Link(
        destination="/inner",
        children=(_text("inner"),),
        source_span=_span(),
    )
    if indirect == "Strong":
        child = Strong(children=(child,), source_span=_span())
    elif indirect == "Emphasis":
        child = Emphasis(children=(child,), source_span=_span())
    elif indirect == "InlineFormat":
        child = InlineFormat(config_ref=8, children=(child,), source_span=_span())
    elif indirect == "Superscript":
        child = Superscript(children=(child,), source_span=_span())
    elif indirect == "Subscript":
        child = Subscript(children=(child,), source_span=_span())
    return Link(
        destination=outer_destination,
        children=(child,),
        source_span=_span(),
    )


def test_direct_nested_link_is_rejected() -> None:
    presentation = _programmatic_resolved((_nested_link(outer_destination="/outer"),))

    with pytest.raises(ValueError, match="^Nested Link nodes are unsupported$"):
        render_static_html(presentation)


@pytest.mark.parametrize(
    "container",
    ["Strong", "Emphasis", "InlineFormat", "Superscript", "Subscript"],
)
def test_nested_link_through_each_supported_container_is_rejected(
    container: str,
) -> None:
    presentation = _programmatic_resolved(
        (_nested_link(outer_destination="/outer", indirect=container),)
    )

    with pytest.raises(ValueError, match="^Nested Link nodes are unsupported$"):
        render_static_html(presentation)


def test_nested_link_error_wins_for_unsafe_outer_link() -> None:
    presentation = _programmatic_resolved(
        (_nested_link(outer_destination="javascript:bad"),)
    )

    with pytest.raises(ValueError, match="^Nested Link nodes are unsupported$"):
        render_static_html(presentation)


def test_sibling_links_are_legal() -> None:
    inlines = (
        Link(destination="/one", children=(_text("one"),), source_span=_span()),
        _text(" and "),
        Link(
            destination="javascript:bad",
            children=(_text("two"),),
            source_span=_span(),
        ),
    )

    assert _paragraph_fragment(_programmatic_resolved(inlines)) == (
        '<p><a class="sj-link" href="/one">one</a> and '
        '<a class="sj-link sj-link--unsafe">two</a></p>'
    )


@pytest.mark.parametrize("bad_level", [True, 2.0, 0, 7])
def test_malformed_runtime_heading_level_is_rejected(bad_level: object) -> None:
    presentation = _resolve("### Heading")
    heading = presentation.items[0].blocks[0].node
    object.__setattr__(heading, "level", bad_level)

    with pytest.raises(ValueError):
        render_static_html(presentation)


def test_malformed_runtime_slide_kind_is_rejected() -> None:
    presentation = _resolve("## Heading")
    object.__setattr__(presentation.items[0], "kind", "h2")

    with pytest.raises(ValueError):
        render_static_html(presentation)


@pytest.mark.parametrize("bad_ref", [True, 0, -1, 1.0])
def test_malformed_runtime_inline_format_reference_is_rejected(
    bad_ref: object,
) -> None:
    formatted = InlineFormat(
        config_ref=1,
        children=(_text(),),
        source_span=_span(),
    )
    presentation = _programmatic_resolved((formatted,))
    object.__setattr__(formatted, "config_ref", bad_ref)

    with pytest.raises(ValueError):
        render_static_html(presentation)


@dataclass(frozen=True, slots=True, kw_only=True)
class _FutureText(Text):
    pass


def test_inline_subclass_is_rejected_instead_of_rendered_as_known_type() -> None:
    presentation = _programmatic_resolved(
        (_FutureText(value="future", source_span=_span()),)
    )

    with pytest.raises(TypeError):
        render_static_html(presentation)


@dataclass(frozen=True, slots=True, kw_only=True)
class _FutureParagraph(Paragraph):
    pass


def test_block_subclass_is_rejected_instead_of_rendered_as_known_type() -> None:
    presentation = _resolve("Paragraph")
    block = presentation.items[0].blocks[0]
    original = block.node
    future = _FutureParagraph(
        children=original.children,
        source_binding=original.source_binding,
        config_ref=original.config_ref,
    )
    object.__setattr__(block, "node", future)

    with pytest.raises(TypeError):
        render_static_html(presentation)


class _FutureResolvedInline(ResolvedInline):
    __slots__ = ()


class _FutureResolvedBlock(ResolvedBlock):
    __slots__ = ()


class _FutureResolvedSlide(ResolvedSlide):
    __slots__ = ()


class _FutureResolvedSection(ResolvedSection):
    __slots__ = ()


def _presentation_with_future_resolved_wrapper(kind: str) -> ResolvedPresentation:
    if kind == "section":
        presentation = _resolve("# Section")
        section = presentation.items[0]
        assert isinstance(section, ResolvedSection)
        future_section = _FutureResolvedSection(
            node=section.node,
            title_slide=section.title_slide,
            slides=section.slides,
        )
        return replace(presentation, items=(future_section,))

    presentation = _resolve("## Slide\n\ntext")
    slide = presentation.items[0]
    assert isinstance(slide, ResolvedSlide)
    if kind == "slide":
        future_slide = _FutureResolvedSlide(
            node=slide.node,
            kind=slide.kind,
            configuration=slide.configuration,
            title=slide.title,
            blocks=slide.blocks,
        )
        return replace(presentation, items=(future_slide,))

    block = slide.blocks[0]
    if kind == "block":
        future_block = _FutureResolvedBlock(
            node=block.node,
            element_kind=block.element_kind,
            semantic_role=block.semantic_role,
            configuration=block.configuration,
            inlines=block.inlines,
            list_items=block.list_items,
            blocks=block.blocks,
        )
        return replace(
            presentation,
            items=(replace(slide, blocks=(future_block,)),),
        )

    if kind == "inline":
        inline = block.inlines[0]
        future_inline = _FutureResolvedInline(
            node=inline.node,
            style=inline.style,
            children=inline.children,
        )
        return replace(
            presentation,
            items=(
                replace(
                    slide,
                    blocks=(replace(block, inlines=(future_inline,)),),
                ),
            ),
        )
    raise AssertionError(f"Unhandled test wrapper kind: {kind}")


@pytest.mark.parametrize("kind", ["slide", "section", "block", "inline"])
def test_resolved_wrapper_subclasses_are_rejected(kind: str) -> None:
    presentation = _presentation_with_future_resolved_wrapper(kind)

    with pytest.raises(TypeError):
        render_static_html(presentation)


@pytest.mark.parametrize("field", ["text", "code", "math", "image-alt"])
def test_non_string_html_payload_is_rejected(field: str) -> None:
    if field == "text":
        inline = Text(value=42, source_span=_span())  # type: ignore[arg-type]
    elif field == "code":
        inline = InlineCode(code=42, source_span=_span())  # type: ignore[arg-type]
    elif field == "math":
        inline = InlineMath(content=42, source_span=_span())  # type: ignore[arg-type]
    else:
        inline = InlineImage(
            src="image.png",
            alt=42,  # type: ignore[arg-type]
            source_span=_span(),
        )

    with pytest.raises(TypeError):
        render_static_html(_programmatic_resolved((inline,)))


@pytest.mark.parametrize("field", ["destination", "title"])
def test_non_string_link_attribute_is_rejected(field: str) -> None:
    kwargs: dict[str, object] = {
        "destination": "/safe",
        "title": "title",
        "children": (_text(),),
        "source_span": _span(),
    }
    kwargs[field] = 42
    link = Link(**kwargs)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        render_static_html(_programmatic_resolved((link,)))


def _styled_layout(value: int) -> LayoutDocument:
    return _layout(
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
            slide=Configuration(appearance=Appearance(opacity=value / 10)),
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(font_size=value),
                    appearance=Appearance(opacity=value / 10),
                    stacking=Stacking(z_index=value),
                )
            },
        ),
        inline_formats={
            8: InlineFormatConfiguration(typography=InlineTypography(font_size=value))
        },
    )


def test_resolved_visual_styles_do_not_change_m8_html() -> None:
    source = "<sj-format ref=8>Styled</sj-format>"
    first = _resolve(source, _styled_layout(2))
    second = _resolve(source, _styled_layout(8))

    first_block = first.items[0].blocks[0]
    second_block = second.items[0].blocks[0]
    assert first.items[0].configuration != second.items[0].configuration
    assert first_block.configuration != second_block.configuration
    assert first_block.inlines[0].style != second_block.inlines[0].style
    assert render_static_html(first) == render_static_html(second)


class _UnreadableSourceDocument:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"renderer traversed source_document.{name}")


def test_renderer_does_not_traverse_source_document() -> None:
    presentation = _resolve("Paragraph")
    object.__setattr__(presentation, "source_document", _UnreadableSourceDocument())

    assert "<p>Paragraph</p>" in render_static_html(presentation)


def test_renderer_performs_no_filesystem_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    presentation = _resolve("Paragraph")

    def reject_access(*args: object, **kwargs: object) -> None:
        raise AssertionError("renderer accessed the filesystem")

    monkeypatch.setattr(builtins, "open", reject_access)
    monkeypatch.setattr(Path, "open", reject_access)
    monkeypatch.setattr(Path, "read_text", reject_access)
    monkeypatch.setattr(Path, "write_text", reject_access)

    assert "<p>Paragraph</p>" in render_static_html(presentation)


def test_render_is_repeatable_and_does_not_mutate_input() -> None:
    presentation = _resolve("## Title\n\nA **bold** paragraph")
    original_repr = repr(presentation)
    original_item = presentation.items[0]
    original_block = original_item.blocks[0]

    first = render_static_html(presentation)
    second = render_static_html(presentation)

    assert first == second
    assert repr(presentation) == original_repr
    assert presentation.items[0] is original_item
    assert presentation.items[0].blocks[0] is original_block


def test_deck_load_snapshot_renders_through_the_public_api(tmp_path: Path) -> None:
    deck = slidejunction.Deck.init(tmp_path / "talk")
    (deck.root / "slides.md").write_text(
        "## Loaded title\n\nLoaded body\n",
        encoding="utf-8",
        newline="\n",
    )

    result = deck.load()
    assert result.snapshot is not None

    html = render_static_html(result.snapshot.resolved_presentation)

    assert html.startswith("<!doctype html>\n")
    assert "<h2>Loaded title</h2>" in html
    assert "<p>Loaded body</p>" in html
    assert html.endswith("</html>\n")
