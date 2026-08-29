"""Parse Markdown into SlideJunction's immutable Document Model."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock
from markdown_it.rules_block import html_block as commonmark_html_block
from markdown_it.rules_inline import StateInline
from markdown_it.token import Token

from ._markdown_source import (
    MappedText,
    SourceIndex,
    TrackingParserBlock,
    TrackingParserInline,
    block_node_start,
    token_block_span,
    token_relative_span,
)
from .document import (
    Block,
    BlockQuote,
    CodeBlock,
    Diagnostic,
    DiagnosticSeverity,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    Inline,
    InlineCode,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    ListItem,
    MathBlock,
    Paragraph,
    Presentation,
    Section,
    Slide,
    SoftBreak,
    SourceBinding,
    SourceDocument,
    SourceSpan,
    Strong,
    Text,
    ThematicBreak,
)

_VALID_CONFIG_REF = re.compile(r"^<!-- sj:ref=([1-9][0-9]*) -->$")
_MARKER_INTENT = re.compile(r"^\s*<!--\s*sj:ref\b")
_COMMENT = re.compile(r"^\s*<!--[\s\S]*-->\s*$")


@dataclass(frozen=True, slots=True)
class _Construct:
    kind: Literal["block", "marker", "barrier"]
    start_line: int
    end_line: int
    block: Block | None = None
    boundary_level: int | None = None
    marker_ref: int | None = None
    marker_span: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class _SlideDraft:
    kind: Literal["implicit", "h1", "h2"]
    title: Heading | None
    blocks: tuple[Block, ...]
    start: int


def parse_markdown(
    text: str,
    *,
    path: str | Path | None = None,
) -> SourceDocument:
    """Parse ``text`` without performing filesystem I/O.

    Unsupported source is reported through diagnostics whenever a lossless,
    explicit recovery is available. An internal source-location inconsistency
    raises ``ValueError`` rather than returning guessed ranges.
    """

    index = SourceIndex(text)
    parser = _create_parser()
    environment: dict[str, Any] = {}
    tokens = parser.parse(text, environment)
    converter = _Converter(index)
    constructs, next_token = converter.convert_sequence(tokens, 0, depth=0)
    if next_token != len(tokens):
        raise ValueError("Markdown block conversion did not consume every token")

    blocks = _bind_config_refs(constructs, converter.diagnostics)
    presentation = _assemble_presentation(blocks, index, converter.diagnostics)
    return SourceDocument(
        path=None if path is None else Path(path),
        text=text,
        presentation=presentation,
    )


def _create_parser() -> MarkdownIt:
    parser = MarkdownIt(
        "commonmark",
        {
            "html": True,
            "inline_definitions": True,
            "store_labels": True,
        },
    )
    parser.block = TrackingParserBlock()
    parser.inline = TrackingParserInline()
    parser.block.ruler.at(
        "html_block",
        _recovering_html_block_rule,
        {"alt": ["paragraph", "reference", "blockquote"]},
    )
    parser.inline.ruler2.disable(["fragments_join"])
    parser.core.ruler.disable(["text_join"])
    parser.inline.ruler.before("escape", "slidejunction_math", _inline_math_rule)
    parser.block.ruler.before(
        "fence",
        "slidejunction_math",
        _block_math_rule,
        {"alt": ["paragraph", "reference", "blockquote", "list"]},
    )
    return parser


def _recovering_html_block_rule(
    state: StateBlock,
    start_line: int,
    end_line: int,
    silent: bool,
) -> bool:
    """Keep comments intact, but recover after the first unsupported HTML line."""

    token_count = len(state.tokens)
    if not commonmark_html_block(state, start_line, end_line, silent):
        return False
    if silent:
        return True
    if len(state.tokens) != token_count + 1:
        raise ValueError("Raw HTML rule produced an unexpected token structure")
    token = state.tokens[-1]
    if token.content.lstrip(" \t").startswith("<!--"):
        return True

    token.map = [start_line, start_line + 1]
    token.content = state.getLines(
        start_line,
        start_line + 1,
        state.blkIndent,
        True,
    )
    state.line = start_line + 1
    return True


def _inline_math_rule(state: StateInline, silent: bool) -> bool:
    start = state.pos
    if not state.src.startswith(r"\(", start):
        return False

    line_end = state.src.find("\n", start + 2, state.posMax)
    if line_end < 0:
        line_end = state.posMax
    close = start + 2
    while close < line_end:
        close = state.src.find(r"\)", close, line_end)
        if close < 0:
            break
        preceding = 0
        cursor = close - 1
        while cursor >= start and state.src[cursor] == "\\":
            preceding += 1
            cursor -= 1
        if preceding % 2 == 0:
            break
        close += 2

    if close < 0:
        if silent:
            state.pos = line_end
            return True
        token = state.push("sj_math_inline_unterminated", "", 0)
        token.content = state.src[start:line_end]
        state.pos = line_end
        return True

    if silent:
        state.pos = close + 2
        return True
    token = state.push("sj_math_inline", "math", 0)
    token.content = state.src[start + 2 : close]
    token.markup = r"\("
    state.pos = close + 2
    return True


def _block_math_rule(
    state: StateBlock,
    start_line: int,
    end_line: int,
    silent: bool,
) -> bool:
    if state.is_code_block(start_line):
        return False
    start = state.bMarks[start_line] + state.tShift[start_line]
    line_end = state.eMarks[start_line]
    if not state.src.startswith(r"\[", start):
        return False

    opener_tail = state.src[start + 2 : line_end]
    same_line_close = _find_unescaped(opener_tail, r"\]")
    if same_line_close >= 0:
        close_end = same_line_close + 2
        if opener_tail[close_end:].strip(" \t"):
            return _push_unterminated_block_math(
                state,
                start_line,
                start,
                line_end,
                silent,
            )
        if silent:
            return True
        token = state.push("sj_math_block", "math", 0)
        token.map = [start_line, start_line + 1]
        token.meta["payload_ranges"] = [(start + 2, start + 2 + same_line_close)]
        token.content = opener_tail[:same_line_close]
        state.line = start_line + 1
        return True

    if opener_tail.strip(" \t"):
        return _push_unterminated_block_math(
            state,
            start_line,
            start,
            line_end,
            silent,
        )

    close_line = start_line + 1
    while close_line < end_line:
        content_start = state.bMarks[close_line] + state.tShift[close_line]
        content_end = state.eMarks[close_line]
        node_start = block_node_start(state, close_line)
        local_indent = state.src[node_start:content_start]
        if len(local_indent) > 3 or local_indent.strip(" "):
            close_line += 1
            continue
        logical_line = state.src[content_start:content_end]
        if re.fullmatch(r"\\\][ \t]*", logical_line):
            if silent:
                return True
            ranges: list[tuple[int, int]] = []
            opener_newline_end = min(line_end + 1, len(state.src))
            ranges.append((line_end, opener_newline_end))
            for line in range(start_line + 1, close_line):
                payload_start = block_node_start(state, line)
                payload_end = state.eMarks[line]
                if payload_end < len(state.src) and state.src[payload_end] == "\n":
                    payload_end += 1
                ranges.append((payload_start, payload_end))
            token = state.push("sj_math_block", "math", 0)
            token.map = [start_line, close_line + 1]
            token.meta["payload_ranges"] = ranges
            token.content = "".join(state.src[left:right] for left, right in ranges)
            state.line = close_line + 1
            return True
        close_line += 1

    return _push_unterminated_block_math(
        state,
        start_line,
        start,
        line_end,
        silent,
    )


def _push_unterminated_block_math(
    state: StateBlock,
    start_line: int,
    start: int,
    line_end: int,
    silent: bool,
) -> bool:
    if silent:
        return True
    token = state.push("sj_math_block_unterminated", "", 0)
    token.map = [start_line, start_line + 1]
    token.meta["literal_range"] = (start, line_end)
    token.content = state.src[start:line_end]
    state.line = start_line + 1
    return True


def _find_unescaped(source: str, delimiter: str) -> int:
    position = 0
    while True:
        position = source.find(delimiter, position)
        if position < 0:
            return -1
        preceding = 0
        cursor = position - 1
        while cursor >= 0 and source[cursor] == "\\":
            preceding += 1
            cursor -= 1
        if preceding % 2 == 0:
            return position
        position += len(delimiter)


class _Converter:
    def __init__(self, index: SourceIndex) -> None:
        self.index = index
        self.diagnostics: list[Diagnostic] = []

    def convert_sequence(
        self,
        tokens: list[Token],
        position: int,
        *,
        depth: int,
        stop_type: str | None = None,
    ) -> tuple[list[_Construct], int]:
        constructs: list[_Construct] = []
        while position < len(tokens):
            token = tokens[position]
            if token.type == stop_type:
                return constructs, position + 1

            if token.type in {"paragraph_open", "heading_open"}:
                construct, position = self._convert_text_block(
                    tokens, position, depth=depth
                )
                if construct is not None:
                    constructs.append(construct)
                continue
            if token.type == "blockquote_open":
                construct, position = self._convert_blockquote(
                    tokens, position, depth=depth
                )
                constructs.append(construct)
                continue
            if token.type in {"bullet_list_open", "ordered_list_open"}:
                construct, position = self._convert_list(tokens, position, depth=depth)
                constructs.append(construct)
                continue
            if token.type in {"fence", "code_block"}:
                constructs.append(self._convert_code_block(token))
                position += 1
                continue
            if token.type == "hr":
                span = self._block_span(token)
                constructs.append(
                    self._block_construct(
                        token,
                        ThematicBreak(source_binding=SourceBinding(syntax_span=span)),
                    )
                )
                position += 1
                continue
            if token.type == "sj_math_block":
                constructs.append(self._convert_math_block(token))
                position += 1
                continue
            if token.type == "sj_math_block_unterminated":
                constructs.append(self._recover_unterminated_math_block(token))
                position += 1
                continue
            if token.type in {"html_block", "definition"}:
                construct = self._convert_hidden_construct(token, depth=depth)
                if construct is not None:
                    constructs.append(construct)
                position += 1
                continue
            if token.nesting == -1:
                raise ValueError(f"Unexpected Markdown closing token: {token.type}")
            raise ValueError(f"Unsupported Markdown token: {token.type}")

        if stop_type is not None:
            raise ValueError(f"Missing Markdown closing token: {stop_type}")
        return constructs, position

    def _convert_text_block(
        self,
        tokens: list[Token],
        position: int,
        *,
        depth: int,
    ) -> tuple[_Construct | None, int]:
        opening = tokens[position]
        if position + 2 >= len(tokens):
            raise ValueError("Markdown text block is incomplete")
        inline = tokens[position + 1]
        closing = tokens[position + 2]
        expected_close = opening.type.removesuffix("_open") + "_close"
        if inline.type != "inline" or closing.type != expected_close:
            raise ValueError("Markdown text block token structure is invalid")

        if opening.type == "heading_open" and opening.markup in {"=", "-"}:
            block = self._recover_setext(opening, inline)
            construct = self._block_construct(opening, block)
            return construct, position + 3

        mapped = MappedText.from_token(
            inline,
            self.index,
            strip_atx_closer=opening.type == "heading_open",
        )
        children = self._convert_inlines(inline.children or [], mapped)
        syntax_span = self._block_span(opening)
        binding = SourceBinding(syntax_span=syntax_span)
        if opening.type == "heading_open":
            level = int(opening.tag[1:])
            block: Block = Heading(
                level=level,
                children=children,
                source_binding=binding,
            )
            boundary = level if depth == 0 and level in {1, 2} else None
            return self._block_construct(opening, block, boundary), position + 3

        if len(children) == 1 and isinstance(children[0], InlineImage):
            image = children[0]
            block = ImageBlock(
                src=image.src,
                alt=image.alt,
                title=image.title,
                source_binding=binding,
            )
            return self._block_construct(opening, block), position + 3
        if not children:
            return self._barrier_construct(
                opening
            ) if depth == 0 else None, position + 3
        block = Paragraph(children=children, source_binding=binding)
        return self._block_construct(opening, block), position + 3

    def _convert_blockquote(
        self,
        tokens: list[Token],
        position: int,
        *,
        depth: int,
    ) -> tuple[_Construct, int]:
        opening = tokens[position]
        children, position = self.convert_sequence(
            tokens,
            position + 1,
            depth=depth + 1,
            stop_type="blockquote_close",
        )
        block = BlockQuote(
            blocks=tuple(
                child.block
                for child in children
                if child.kind == "block" and child.block is not None
            ),
            source_binding=SourceBinding(syntax_span=self._block_span(opening)),
        )
        return self._block_construct(opening, block), position

    def _convert_list(
        self,
        tokens: list[Token],
        position: int,
        *,
        depth: int,
    ) -> tuple[_Construct, int]:
        opening = tokens[position]
        closing_type = opening.type.removesuffix("_open") + "_close"
        ordered = opening.type == "ordered_list_open"
        items: list[ListItem] = []
        position += 1
        while position < len(tokens) and tokens[position].type != closing_type:
            item_open = tokens[position]
            if item_open.type != "list_item_open":
                raise ValueError("List contains a non-item token")
            item_constructs, position = self.convert_sequence(
                tokens,
                position + 1,
                depth=depth + 1,
                stop_type="list_item_close",
            )
            items.append(
                ListItem(
                    blocks=tuple(
                        child.block
                        for child in item_constructs
                        if child.kind == "block" and child.block is not None
                    ),
                    source_span=self._block_span(item_open),
                )
            )
        if position >= len(tokens):
            raise ValueError(f"Missing Markdown closing token: {closing_type}")
        position += 1
        start_value = opening.attrGet("start")
        block = ListBlock(
            ordered=ordered,
            start=int(start_value) if ordered and start_value is not None else None,
            items=tuple(items),
            source_binding=SourceBinding(syntax_span=self._block_span(opening)),
        )
        return self._block_construct(opening, block), position

    def _convert_code_block(self, token: Token) -> _Construct:
        info = token.info if token.type == "fence" else ""
        language = info.strip().split(maxsplit=1)[0] if info.strip() else None
        block = CodeBlock(
            code=token.content,
            language=language,
            info=info or None,
            source_binding=SourceBinding(syntax_span=self._block_span(token)),
        )
        return self._block_construct(token, block)

    def _convert_math_block(self, token: Token) -> _Construct:
        ranges = token.meta.get("payload_ranges")
        if type(ranges) is not list:
            raise ValueError("Math block has no exact payload ranges")
        content_parts: list[str] = []
        for normalized_range in ranges:
            if not (
                isinstance(normalized_range, tuple)
                and len(normalized_range) == 2
                and all(isinstance(value, int) for value in normalized_range)
            ):
                raise ValueError("Math payload range is invalid")
            left, right = self.index.normalized_range(*normalized_range)
            content_parts.append(self.index.text[left:right])
        block = MathBlock(
            content="".join(content_parts),
            source_binding=SourceBinding(
                syntax_span=self._block_span(token, include_container=True)
            ),
        )
        return self._block_construct(token, block)

    def _recover_unterminated_math_block(self, token: Token) -> _Construct:
        syntax_span = self._block_span(token, include_container=True)
        literal_range = token.meta.get("literal_range")
        if not (
            isinstance(literal_range, tuple)
            and len(literal_range) == 2
            and all(isinstance(value, int) for value in literal_range)
        ):
            raise ValueError("Unterminated math block has no exact literal range")
        left, right = self.index.normalized_range(*literal_range)
        text = Text(value=self.index.text[left:right], source_span=syntax_span)
        block = Paragraph(
            children=(text,),
            source_binding=SourceBinding(syntax_span=syntax_span),
        )
        self._diagnose(
            DiagnosticSeverity.ERROR,
            "unterminated-block-math",
            "Block math opener has no matching delimiter.",
            syntax_span,
        )
        return self._block_construct(token, block)

    def _recover_setext(self, opening: Token, inline: Token) -> Paragraph:
        syntax_span = self._block_span(opening, include_container=True)
        mapped = MappedText.from_token(inline, self.index)
        value = mapped.original_text(0, len(mapped.text))
        if opening.map is None:
            raise ValueError("Setext heading has no source line map")
        title_line = self.index.lines[inline.map[0]] if inline.map is not None else None
        if title_line is None:
            raise ValueError("Setext inline token has no source line map")
        line_ending = self.index.text[title_line.content_end : title_line.end]
        underline_line = self.index.lines[opening.map[1] - 1]
        underline_source = self.index.text[
            underline_line.start : underline_line.content_end
        ]
        match = re.search(r"[=-]+[ \t]*$", underline_source)
        if match is None:
            raise ValueError("Unable to recover Setext underline source")
        value += line_ending + match.group(0)
        text = Text(value=value, source_span=syntax_span)
        self._diagnose(
            DiagnosticSeverity.ERROR,
            "unsupported-setext-heading",
            "Setext headings are unsupported and were preserved as literal text.",
            syntax_span,
        )
        return Paragraph(
            children=(text,),
            source_binding=SourceBinding(syntax_span=syntax_span),
        )

    def _convert_hidden_construct(
        self,
        token: Token,
        *,
        depth: int,
    ) -> _Construct | None:
        if token.type == "definition":
            return self._barrier_construct(token) if depth == 0 else None

        content = token.content.removesuffix("\n")
        span = self._block_span(token)
        if _COMMENT.fullmatch(content):
            valid = _VALID_CONFIG_REF.fullmatch(content)
            if valid is not None:
                marker_span = self._comment_span(token, content)
                if depth > 0:
                    self._diagnose(
                        DiagnosticSeverity.WARNING,
                        "unsupported-nested-config-ref",
                        "Configuration references inside containers are unsupported.",
                        marker_span,
                    )
                    return None
                return _Construct(
                    kind="marker",
                    start_line=token.map[0],
                    end_line=token.map[1],
                    marker_ref=int(valid.group(1)),
                    marker_span=marker_span,
                )
            if _MARKER_INTENT.match(content):
                self._diagnose(
                    DiagnosticSeverity.ERROR,
                    "invalid-config-ref-marker",
                    "Configuration reference marker syntax is invalid.",
                    span,
                )
            return self._barrier_construct(token) if depth == 0 else None

        self._diagnose(
            DiagnosticSeverity.ERROR,
            "unsupported-raw-html",
            "Raw HTML is unsupported and was omitted.",
            span,
        )
        return self._barrier_construct(token) if depth == 0 else None

    def _convert_inlines(
        self,
        tokens: list[Token],
        mapped: MappedText,
        start: int = 0,
        stop_type: str | None = None,
    ) -> tuple[Inline, ...]:
        children: list[Inline] = []
        position = start
        while position < len(tokens):
            token = tokens[position]
            if token.type == stop_type:
                return tuple(children)
            relative_start, relative_end = token_relative_span(token)
            span = mapped.span(relative_start, relative_end)
            if token.type in {"text", "text_special"}:
                if token.content:
                    children.append(Text(value=token.content, source_span=span))
                position += 1
                continue
            if token.type in {"strong_open", "em_open", "link_open"}:
                close_type = token.type.removesuffix("_open") + "_close"
                close_position = _matching_close(tokens, position, close_type)
                nested = self._convert_inlines(
                    tokens,
                    mapped,
                    position + 1,
                    close_type,
                )
                close_start, close_end = token_relative_span(tokens[close_position])
                composite_span = mapped.span(
                    min(relative_start, close_start),
                    max(relative_end, close_end),
                )
                if token.type == "strong_open":
                    children.append(Strong(children=nested, source_span=composite_span))
                elif token.type == "em_open":
                    children.append(
                        Emphasis(children=nested, source_span=composite_span)
                    )
                else:
                    children.append(
                        Link(
                            destination=token.attrGet("href") or "",
                            title=token.attrGet("title"),
                            children=nested,
                            source_span=composite_span,
                        )
                    )
                position = close_position + 1
                continue
            if token.type in {"strong_close", "em_close", "link_close"}:
                raise ValueError(f"Unexpected inline closing token: {token.type}")
            if token.type == "code_inline":
                children.append(InlineCode(code=token.content, source_span=span))
            elif token.type == "image":
                children.append(
                    InlineImage(
                        src=token.attrGet("src") or "",
                        alt=_inline_plain_text(token.children or []),
                        title=token.attrGet("title"),
                        source_span=span,
                    )
                )
            elif token.type == "softbreak":
                children.append(SoftBreak(source_span=span))
            elif token.type == "hardbreak":
                children.append(HardBreak(source_span=span))
            elif token.type == "sj_math_inline":
                children.append(
                    InlineMath(
                        content=mapped.original_text(
                            relative_start + 2,
                            relative_end - 2,
                        ),
                        source_span=span,
                    )
                )
            elif token.type == "sj_math_inline_unterminated":
                children.append(
                    Text(
                        value=mapped.original_text(relative_start, relative_end),
                        source_span=span,
                    )
                )
                self._diagnose(
                    DiagnosticSeverity.ERROR,
                    "unterminated-inline-math",
                    "Inline math opener has no matching delimiter.",
                    span,
                )
            elif token.type == "html_inline":
                self._convert_inline_html(token, span)
            else:
                raise ValueError(f"Unsupported inline token: {token.type}")
            position += 1

        if stop_type is not None:
            raise ValueError(f"Missing inline closing token: {stop_type}")
        return tuple(children)

    def _convert_inline_html(self, token: Token, span: SourceSpan) -> None:
        if _COMMENT.fullmatch(token.content):
            if _MARKER_INTENT.match(token.content):
                self._diagnose(
                    DiagnosticSeverity.ERROR,
                    "invalid-config-ref-marker",
                    "Configuration reference marker must be a standalone block.",
                    span,
                )
            return
        self._diagnose(
            DiagnosticSeverity.ERROR,
            "unsupported-raw-html",
            "Raw HTML is unsupported and was omitted.",
            span,
        )

    def _block_span(
        self,
        token: Token,
        *,
        include_container: bool = False,
    ) -> SourceSpan:
        if token.map is None:
            raise ValueError(f"Block token {token.type!r} has no source line map")
        if include_container:
            return self.index.lines_span(token.map)
        left, right = self.index.normalized_range(*token_block_span(token))
        return self.index.span(left, right)

    def _comment_span(self, token: Token, content: str) -> SourceSpan:
        if token.map is None:
            raise ValueError("HTML comment has no source line map")
        line = self.index.lines[token.map[0]]
        original_line = self.index.text[line.start : line.content_end]
        normalized_start = self.index.source.original_to_normalized[line.start]
        normalized_end = self.index.source.original_to_normalized[line.content_end]
        if normalized_start is None or normalized_end is None:
            raise ValueError("HTML comment boundaries cannot be normalized")
        normalized_line = self.index.source.normalized[normalized_start:normalized_end]
        start_in_line = normalized_line.find(content)
        if start_in_line < 0:
            raise ValueError("Unable to locate HTML comment source")
        left, right = self.index.normalized_range(
            normalized_start + start_in_line,
            normalized_start + start_in_line + len(content),
        )
        if self.index.text[left:right] != content or not original_line:
            raise ValueError("HTML comment source mapping is inconsistent")
        return self.index.span(left, right)

    def _block_construct(
        self,
        token: Token,
        block: Block,
        boundary_level: int | None = None,
    ) -> _Construct:
        if token.map is None:
            raise ValueError(f"Block token {token.type!r} has no source line map")
        return _Construct(
            kind="block",
            start_line=token.map[0],
            end_line=token.map[1],
            block=block,
            boundary_level=boundary_level,
        )

    def _barrier_construct(self, token: Token) -> _Construct:
        if token.map is None:
            raise ValueError(f"Block token {token.type!r} has no source line map")
        return _Construct(
            kind="barrier",
            start_line=token.map[0],
            end_line=token.map[1],
        )

    def _diagnose(
        self,
        severity: DiagnosticSeverity,
        code: str,
        message: str,
        span: SourceSpan,
    ) -> None:
        self.diagnostics.append(
            Diagnostic(
                severity=severity,
                code=code,
                message=message,
                source_span=span,
            )
        )


def _matching_close(tokens: list[Token], start: int, close_type: str) -> int:
    depth = 0
    open_type = tokens[start].type
    for position in range(start + 1, len(tokens)):
        if tokens[position].type == open_type:
            depth += 1
        elif tokens[position].type == close_type:
            if depth == 0:
                return position
            depth -= 1
    raise ValueError(f"Missing inline closing token: {close_type}")


def _inline_plain_text(tokens: list[Token]) -> str:
    parts: list[str] = []
    for token in tokens:
        if token.type in {"text", "text_special", "code_inline"}:
            parts.append(token.content)
        elif token.type in {"softbreak", "hardbreak"}:
            parts.append("\n")
        elif token.type == "image":
            parts.append(_inline_plain_text(token.children or []))
        elif token.type == "sj_math_inline":
            parts.append(token.content)
    return "".join(parts)


def _bind_config_refs(
    constructs: list[_Construct],
    diagnostics: list[Diagnostic],
) -> list[_Construct]:
    result: list[_Construct] = []
    pending: _Construct | None = None
    for construct in constructs:
        if construct.kind == "marker":
            if pending is not None:
                diagnostics.append(_unused_marker(pending))
            pending = construct
            continue
        if construct.kind == "barrier":
            if pending is not None:
                diagnostics.append(_unused_marker(pending))
                pending = None
            continue
        if construct.block is None:
            raise ValueError("Block construct has no block")
        block = construct.block
        if pending is not None:
            if pending.end_line == construct.start_line:
                if pending.marker_ref is None or pending.marker_span is None:
                    raise ValueError("Configuration marker is incomplete")
                binding = replace(
                    block.source_binding,
                    config_marker_span=pending.marker_span,
                )
                block = replace(
                    block,
                    source_binding=binding,
                    config_ref=pending.marker_ref,
                )
            else:
                diagnostics.append(_unused_marker(pending))
            pending = None
        result.append(replace(construct, block=block))
    if pending is not None:
        diagnostics.append(_unused_marker(pending))
    return result


def _unused_marker(marker: _Construct) -> Diagnostic:
    if marker.marker_span is None:
        raise ValueError("Configuration marker has no source span")
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="unused-config-ref",
        message="Configuration reference is not immediately followed by a block.",
        source_span=marker.marker_span,
    )


def _assemble_presentation(
    constructs: list[_Construct],
    index: SourceIndex,
    diagnostics: list[Diagnostic],
) -> Presentation:
    drafts: list[_SlideDraft] = []
    current_kind: Literal["h1", "h2"] | None = None
    current_title: Heading | None = None
    current_blocks: list[Block] = []
    preamble: list[Block] = []

    def finish_current() -> None:
        nonlocal current_kind, current_title, current_blocks
        if current_kind is None or current_title is None:
            return
        drafts.append(
            _SlideDraft(
                kind=current_kind,
                title=current_title,
                blocks=tuple(current_blocks),
                start=_block_start(current_title),
            )
        )
        current_kind = None
        current_title = None
        current_blocks = []

    for construct in constructs:
        if construct.kind != "block" or construct.block is None:
            continue
        if construct.boundary_level in {1, 2}:
            finish_current()
            if preamble:
                drafts.append(
                    _SlideDraft(
                        kind="implicit",
                        title=None,
                        blocks=tuple(preamble),
                        start=_block_start(preamble[0]),
                    )
                )
                preamble = []
            if not isinstance(construct.block, Heading):
                raise ValueError("Slide boundary is not a Heading")
            current_kind = "h1" if construct.boundary_level == 1 else "h2"
            current_title = construct.block
        elif current_kind is None:
            preamble.append(construct.block)
        else:
            current_blocks.append(construct.block)

    finish_current()
    if preamble:
        drafts.append(
            _SlideDraft(
                kind="implicit",
                title=None,
                blocks=tuple(preamble),
                start=_block_start(preamble[0]),
            )
        )
    if not drafts:
        drafts.append(
            _SlideDraft(
                kind="implicit",
                title=None,
                blocks=(),
                start=0,
            )
        )

    slides = [
        Slide(
            title=draft.title,
            blocks=draft.blocks,
            source_span=index.span(
                draft.start,
                drafts[position + 1].start
                if position + 1 < len(drafts)
                else len(index.text),
            ),
        )
        for position, draft in enumerate(drafts)
    ]

    items: list[Slide | Section] = []
    position = 0
    while position < len(drafts):
        if drafts[position].kind != "h1":
            items.append(slides[position])
            position += 1
            continue
        title_slide = slides[position]
        position += 1
        section_slides: list[Slide] = []
        while position < len(drafts) and drafts[position].kind != "h1":
            section_slides.append(slides[position])
            position += 1
        items.append(Section(title_slide=title_slide, slides=tuple(section_slides)))

    sorted_diagnostics = tuple(
        sorted(
            diagnostics,
            key=lambda diagnostic: (
                diagnostic.source_span.start_offset,
                diagnostic.source_span.end_offset,
                diagnostic.code,
            ),
        )
    )
    return Presentation(items=tuple(items), diagnostics=sorted_diagnostics)


def _block_start(block: Block) -> int:
    marker = block.source_binding.config_marker_span
    return (
        marker.start_offset
        if marker is not None
        else block.source_binding.syntax_span.start_offset
    )


__all__ = ["parse_markdown"]
