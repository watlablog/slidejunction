"""Pure minimal static HTML rendering for resolved presentations."""

from __future__ import annotations

from html import escape
from urllib.parse import urlsplit

from .document import (
    BlockQuote,
    CodeBlock,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    MathBlock,
    Paragraph,
    SoftBreak,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)
from .layout import SlideKind
from .resolver import (
    ResolvedBlock,
    ResolvedInline,
    ResolvedPresentation,
    ResolvedSection,
    ResolvedSlide,
)

_DOCUMENT_PREFIX = (
    "<!doctype html>",
    "<html>",
    "<head>",
    '  <meta charset="utf-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1">',
    "  <title>SlideJunction</title>",
    "  <style>",
    "    body {",
    "      margin: 0;",
    "      min-height: 100vh;",
    "      background: #f3f4f6;",
    "      color: #111827;",
    '      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;',
    "      line-height: 1.5;",
    "    }",
    "    .sj-presentation {",
    "      display: flex;",
    "      flex-direction: column;",
    "      align-items: center;",
    "      gap: 32px;",
    "      box-sizing: border-box;",
    "      padding: 32px;",
    "    }",
    "    .sj-slide {",
    "      width: 100%;",
    "      max-width: 1280px;",
    "      aspect-ratio: 16 / 9;",
    "      box-sizing: border-box;",
    "      padding: 64px;",
    "      overflow: auto;",
    "      background: #ffffff;",
    "      color: #111827;",
    "      border: 1px solid #d1d5db;",
    "      box-shadow: 0 4px 16px rgba(17, 24, 39, 0.12);",
    "    }",
    "    .sj-slide-title {",
    "      margin-bottom: 32px;",
    "    }",
    "    .sj-slide-title > :first-child,",
    "    .sj-slide-body > :first-child {",
    "      margin-top: 0;",
    "    }",
    "    .sj-slide-title > :last-child,",
    "    .sj-slide-body > :last-child {",
    "      margin-bottom: 0;",
    "    }",
    "    .sj-slide code {",
    "      white-space: pre-wrap;",
    "    }",
    "    .sj-unsupported-block,",
    "    .sj-unsupported-inline {",
    "      border: 1px dashed #d97706;",
    "      background: #fffbeb;",
    "      color: #92400e;",
    "    }",
    "    .sj-unsupported-block {",
    "      padding: 12px;",
    "    }",
    "    .sj-unsupported-inline {",
    "      display: inline-block;",
    "      padding: 0 4px;",
    "    }",
    "    .sj-link--unsafe {",
    "      color: #b91c1c;",
    "      text-decoration: underline wavy;",
    "    }",
    "  </style>",
    "</head>",
    "<body>",
    '  <main class="sj-presentation">',
)

_DOCUMENT_SUFFIX = (
    "  </main>",
    "</body>",
    "</html>",
)

_SLIDE_KIND_VALUE = {
    SlideKind.H1: "h1",
    SlideKind.H2: "h2",
    SlideKind.IMPLICIT: "implicit",
}

_UNSUPPORTED_BLOCK_NAMES = {
    ListBlock: "ListBlock",
    BlockQuote: "BlockQuote",
    CodeBlock: "CodeBlock",
    ImageBlock: "ImageBlock",
    ThematicBreak: "ThematicBreak",
    MathBlock: "MathBlock",
}

_INLINE_CONTAINER_TAGS = {
    Strong: "strong",
    Emphasis: "em",
    Superscript: "sup",
    Subscript: "sub",
}


def render_static_html(presentation: ResolvedPresentation) -> str:
    """Render a resolved presentation as deterministic standalone HTML."""
    if not isinstance(presentation, ResolvedPresentation):
        raise TypeError("presentation must be a ResolvedPresentation")

    lines = list(_DOCUMENT_PREFIX)
    for index, slide in enumerate(_flatten_slides(presentation), start=1):
        lines.extend(_render_slide(slide, index))
    lines.extend(_DOCUMENT_SUFFIX)
    return "\n".join(lines) + "\n"


def _flatten_slides(
    presentation: ResolvedPresentation,
) -> tuple[ResolvedSlide, ...]:
    slides: list[ResolvedSlide] = []
    for item in presentation.items:
        if type(item) is ResolvedSlide:
            slides.append(item)
        elif type(item) is ResolvedSection:
            slides.append(item.title_slide)
            slides.extend(item.slides)
        else:
            raise TypeError("Resolved presentation contains an unsupported item")
    return tuple(slides)


def _render_slide(slide: ResolvedSlide, index: int) -> tuple[str, ...]:
    if type(slide) is not ResolvedSlide:
        raise TypeError("Resolved presentation contains an unsupported slide")
    if type(slide.kind) is not SlideKind:
        raise ValueError("Resolved slide has an invalid kind")
    try:
        kind = _SLIDE_KIND_VALUE[slide.kind]
    except (KeyError, TypeError) as error:
        raise ValueError("Resolved slide has an invalid kind") from error

    escaped_kind = _escape_attribute(kind)
    escaped_index = _escape_attribute(str(index))
    lines = [
        (
            f'    <section class="sj-slide sj-slide--{escaped_kind}" '
            f'data-slide-index="{escaped_index}" '
            f'data-slide-kind="{escaped_kind}">'
        )
    ]
    if slide.title is not None:
        lines.append('      <header class="sj-slide-title">')
        lines.append(f"        {_render_block(slide.title)}")
        lines.append("      </header>")
    lines.append('      <div class="sj-slide-body">')
    lines.extend(f"        {_render_block(block)}" for block in slide.blocks)
    lines.append("      </div>")
    lines.append("    </section>")
    return tuple(lines)


def _render_block(block: ResolvedBlock) -> str:
    if type(block) is not ResolvedBlock:
        raise TypeError("Resolved slide contains an unsupported block wrapper")
    node = block.node
    node_type = type(node)
    if node_type is Heading:
        if type(node.level) is not int or not 1 <= node.level <= 6:
            raise ValueError("Heading level must be between 1 and 6")
        content = _render_inlines(block.inlines, inside_link=False)
        return f"<h{node.level}>{content}</h{node.level}>"
    if node_type is Paragraph:
        content = _render_inlines(block.inlines, inside_link=False)
        return f"<p>{content}</p>"
    if node_type in _UNSUPPORTED_BLOCK_NAMES:
        name = _escape_text(_UNSUPPORTED_BLOCK_NAMES[node_type])
        name_attribute = _escape_attribute(_UNSUPPORTED_BLOCK_NAMES[node_type])
        return (
            '<div class="sj-unsupported-block" '
            f'data-node-type="{name_attribute}">'
            f"[Unsupported block: {name}]</div>"
        )
    raise TypeError("Resolved block contains an unsupported node type")


def _render_inlines(
    inlines: tuple[ResolvedInline, ...],
    *,
    inside_link: bool,
) -> str:
    return "".join(
        _render_inline(inline, inside_link=inside_link) for inline in inlines
    )


def _render_inline(inline: ResolvedInline, *, inside_link: bool) -> str:
    if type(inline) is not ResolvedInline:
        raise TypeError("Resolved block contains an unsupported inline wrapper")
    node = inline.node
    node_type = type(node)

    if node_type is Text:
        return _escape_text(node.value)
    if node_type is InlineCode:
        return f"<code>{_escape_text(node.code)}</code>"
    if node_type is SoftBreak:
        return "\n"
    if node_type is HardBreak:
        return "<br>"
    if node_type in _INLINE_CONTAINER_TAGS:
        tag = _INLINE_CONTAINER_TAGS[node_type]
        children = _render_inlines(inline.children, inside_link=inside_link)
        return f"<{tag}>{children}</{tag}>"
    if node_type is Link:
        return _render_link(inline, inside_link=inside_link)
    if node_type is InlineFormat:
        ref_id = node.config_ref
        if type(ref_id) is not int or ref_id < 1:
            raise ValueError("InlineFormat reference must be a positive integer")
        children = _render_inlines(inline.children, inside_link=inside_link)
        escaped_ref_id = _escape_attribute(str(ref_id))
        return (
            '<span class="sj-inline-format" '
            f'data-config-ref="{escaped_ref_id}">{children}</span>'
        )
    if node_type is InlineMath:
        name = "InlineMath"
        content = _escape_text(node.content)
        return (
            '<span class="sj-unsupported-inline" '
            f'data-node-type="{_escape_attribute(name)}">'
            f"[Unsupported inline: {_escape_text(name)}: {content}]</span>"
        )
    if node_type is InlineImage:
        name = "InlineImage"
        alt = _escape_text(node.alt)
        return (
            '<span class="sj-unsupported-inline" '
            f'data-node-type="{_escape_attribute(name)}">'
            f"[Unsupported inline: {_escape_text(name)}: {alt}]</span>"
        )
    raise TypeError("Resolved inline contains an unsupported node type")


def _render_link(inline: ResolvedInline, *, inside_link: bool) -> str:
    if inside_link:
        raise ValueError("Nested Link nodes are unsupported")

    node = inline.node
    if type(node) is not Link:  # pragma: no cover - private caller invariant
        raise TypeError("Resolved inline is not a Link")
    children = _render_inlines(inline.children, inside_link=True)
    safe = _is_safe_link_destination(node.destination)

    attributes = ['class="sj-link"' if safe else 'class="sj-link sj-link--unsafe"']
    if safe:
        attributes.append(f'href="{_escape_attribute(node.destination)}"')
    if node.title is not None:
        attributes.append(f'title="{_escape_attribute(node.title)}"')
    return f"<a {' '.join(attributes)}>{children}</a>"


def _is_safe_link_destination(destination: str) -> bool:
    if not isinstance(destination, str):
        raise TypeError("Link destination must be a string")
    if destination != destination.strip():
        return False
    if any(
        ord(character) <= 0x1F or ord(character) == 0x7F for character in destination
    ):
        return False
    if destination.startswith("//"):
        return False
    if "\\" in destination:
        return False
    try:
        parsed = urlsplit(destination)
    except ValueError:
        return False
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https", "mailto"}:
        return True
    return scheme == "" and parsed.netloc == ""


def _escape_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("HTML text values must be strings")
    return escape(value, quote=False)


def _escape_attribute(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("HTML attribute values must be strings")
    return escape(value, quote=True)


__all__ = ["render_static_html"]
