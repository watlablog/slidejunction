"""Private exact source-location support for SlideJunction Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from markdown_it.parser_block import ParserBlock
from markdown_it.parser_inline import ParserInline
from markdown_it.rules_block import StateBlock
from markdown_it.rules_inline.state_inline import StateInline
from markdown_it.token import Token

from .document import SourceSpan

_SPAN_META_KEY = "slidejunction_source_span"
_BLOCK_SPAN_META_KEY = "slidejunction_block_source_span"


@dataclass(frozen=True, slots=True)
class _Line:
    start: int
    content_end: int
    end: int


@dataclass(frozen=True, slots=True)
class NormalizedSource:
    """Markdown-it normalization with reversible source boundaries."""

    original: str
    normalized: str
    normalized_to_original: tuple[int, ...]
    original_to_normalized: tuple[int | None, ...]

    @classmethod
    def from_text(cls, text: str) -> NormalizedSource:
        normalized: list[str] = []
        normalized_to_original = [0]
        original_to_normalized: list[int | None] = [None] * (len(text) + 1)
        original_to_normalized[0] = 0
        original_offset = 0
        normalized_offset = 0

        while original_offset < len(text):
            original_to_normalized[original_offset] = normalized_offset
            if text.startswith("\r\n", original_offset):
                normalized.append("\n")
                original_offset += 2
                normalized_offset += 1
                normalized_to_original.append(original_offset)
                original_to_normalized[original_offset] = normalized_offset
                continue

            character = text[original_offset]
            if character == "\r":
                character = "\n"
            elif character == "\0":
                character = "\ufffd"
            normalized.append(character)
            original_offset += 1
            normalized_offset += 1
            normalized_to_original.append(original_offset)
            original_to_normalized[original_offset] = normalized_offset

        return cls(
            original=text,
            normalized="".join(normalized),
            normalized_to_original=tuple(normalized_to_original),
            original_to_normalized=tuple(original_to_normalized),
        )

    def original_range(self, start: int, end: int) -> tuple[int, int]:
        if not 0 <= start <= end <= len(self.normalized):
            raise ValueError("Normalized source range is out of bounds")
        return self.normalized_to_original[start], self.normalized_to_original[end]


class SourceIndex:
    """Convert original offsets and Markdown line maps into SourceSpan values."""

    def __init__(self, text: str) -> None:
        self.source = NormalizedSource.from_text(text)
        self.lines = self._build_lines(text)

    @staticmethod
    def _build_lines(text: str) -> tuple[_Line, ...]:
        lines: list[_Line] = []
        start = 0
        offset = 0
        while offset < len(text):
            if text.startswith("\r\n", offset):
                lines.append(_Line(start=start, content_end=offset, end=offset + 2))
                offset += 2
                start = offset
                continue
            if text[offset] in {"\r", "\n"}:
                lines.append(_Line(start=start, content_end=offset, end=offset + 1))
                offset += 1
                start = offset
                continue
            offset += 1
        lines.append(_Line(start=start, content_end=len(text), end=len(text)))
        return tuple(lines)

    @property
    def text(self) -> str:
        return self.source.original

    def span(self, start_offset: int, end_offset: int) -> SourceSpan:
        start_line, start_column = self.position(start_offset)
        end_line, end_column = self.position(end_offset)
        return SourceSpan(
            start_offset=start_offset,
            end_offset=end_offset,
            start_line=start_line,
            start_column=start_column,
            end_line=end_line,
            end_column=end_column,
        )

    def position(self, offset: int) -> tuple[int, int]:
        if not 0 <= offset <= len(self.text):
            raise ValueError("Source offset is out of bounds")
        low = 0
        high = len(self.lines)
        while low + 1 < high:
            middle = (low + high) // 2
            if self.lines[middle].start <= offset:
                low = middle
            else:
                high = middle
        return low, offset - self.lines[low].start

    def lines_span(self, line_map: list[int] | tuple[int, int]) -> SourceSpan:
        start_line, end_line = line_map
        if not 0 <= start_line < end_line <= len(self.lines):
            raise ValueError("Markdown token line map is invalid")
        return self.span(
            self.lines[start_line].start,
            self.lines[end_line - 1].content_end,
        )

    def normalized_range(self, start: int, end: int) -> tuple[int, int]:
        return self.source.original_range(start, end)


@dataclass(frozen=True, slots=True)
class MappedText:
    """Inline source text with an original range for every normalized character."""

    text: str
    character_ranges: tuple[tuple[int, int], ...]
    index: SourceIndex

    @classmethod
    def from_token(
        cls,
        token: Token,
        index: SourceIndex,
        *,
        strip_atx_closer: bool = False,
    ) -> MappedText:
        if token.map is None:
            raise ValueError("Inline token has no source line map")
        content_lines = token.content.split("\n")
        start_line, end_line = token.map
        if end_line - start_line != len(content_lines):
            raise ValueError("Inline content does not match its source line map")

        ranges: list[tuple[int, int]] = []
        for relative_line, content_line in enumerate(content_lines):
            line_number = start_line + relative_line
            source_line = index.lines[line_number]
            normalized_start = index.source.original_to_normalized[source_line.start]
            normalized_end = index.source.original_to_normalized[
                source_line.content_end
            ]
            if normalized_start is None or normalized_end is None:
                raise ValueError("Source line boundary cannot be normalized exactly")
            raw_line = index.source.normalized[normalized_start:normalized_end]
            candidate = raw_line
            if strip_atx_closer:
                candidate = _remove_atx_closer(candidate)
            if relative_line == len(content_lines) - 1:
                candidate = candidate.rstrip(" \t")
            if not candidate.endswith(content_line):
                raise ValueError("Unable to map inline content to original source")
            content_start = normalized_start + len(candidate) - len(content_line)
            for position, character in enumerate(content_line):
                normalized_position = content_start + position
                if index.source.normalized[normalized_position] != character:
                    raise ValueError("Inline source character mapping is inconsistent")
                ranges.append(
                    index.normalized_range(normalized_position, normalized_position + 1)
                )

            if relative_line + 1 < len(content_lines):
                if source_line.end == source_line.content_end:
                    raise ValueError("Inline newline has no original line ending")
                ranges.append((source_line.content_end, source_line.end))

        if len(ranges) != len(token.content):
            raise ValueError("Inline source mapping length is inconsistent")
        return cls(text=token.content, character_ranges=tuple(ranges), index=index)

    def span(self, start: int, end: int) -> SourceSpan:
        if not 0 <= start <= end <= len(self.text):
            raise ValueError("Inline range is out of bounds")
        if start == end:
            if not self.character_ranges:
                return self.index.span(0, 0)
            boundary = (
                self.character_ranges[start][0]
                if start < len(self.character_ranges)
                else self.character_ranges[-1][1]
            )
            return self.index.span(boundary, boundary)
        return self.index.span(
            self.character_ranges[start][0],
            self.character_ranges[end - 1][1],
        )

    def original_text(self, start: int, end: int) -> str:
        if start == end:
            return ""
        parts = [
            self.index.text[original_start:original_end]
            for original_start, original_end in self.character_ranges[start:end]
        ]
        return "".join(parts)


def _remove_atx_closer(line: str) -> str:
    stripped = line.rstrip(" \t")
    marker_start = len(stripped)
    while marker_start > 0 and stripped[marker_start - 1] == "#":
        marker_start -= 1
    if marker_start == len(stripped):
        return line
    if marker_start > 0 and stripped[marker_start - 1] in {" ", "\t"}:
        return stripped[:marker_start].rstrip(" \t")
    return line


class TrackingStateInline(StateInline):
    """StateInline retaining exact relative ranges for emitted tokens."""

    pending_start: int | None
    rule_start: int

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pending_start = None
        self.rule_start = 0

    def pushPending(self) -> Token:
        if self.pending_start is None:
            raise ValueError("Pending inline text has no exact source start")
        token = super().pushPending()
        token.meta[_SPAN_META_KEY] = (
            self.pending_start,
            self.pending_start + len(token.content),
        )
        self.pending_start = None
        return token


class TrackingParserInline(ParserInline):
    """ParserInline adapter proven to retain exact rule-consumption ranges."""

    def tokenize(self, state: TrackingStateInline) -> None:
        rules = self.ruler.getRules("")
        end = state.posMax
        max_nesting = state.md.options["maxNesting"]

        while state.pos < end:
            matched = False
            if state.level < max_nesting:
                for rule in rules:
                    start = state.pos
                    token_count = len(state.tokens)
                    pending_before = state.pending
                    state.rule_start = start
                    if not rule(state, False):
                        continue

                    matched = True
                    consumed_end = state.pos
                    if (
                        not pending_before
                        and state.pending
                        and state.pending_start is None
                    ):
                        state.pending_start = start
                    for token in state.tokens[token_count:]:
                        token_span = (start, consumed_end)
                        if token.type in {"softbreak", "hardbreak"}:
                            token_span = _break_span(
                                state.src,
                                start,
                                pending_before,
                            )
                        token.meta.setdefault(_SPAN_META_KEY, token_span)
                    break

            if matched:
                if state.pos >= end:
                    break
                continue

            if state.pending_start is None:
                state.pending_start = state.pos
            state.pending += state.src[state.pos]
            state.pos += 1

        if state.pending:
            state.rule_start = state.pos
            state.pushPending()

    def parse(
        self,
        src: str,
        md: Any,
        env: dict[str, Any],
        tokens: list[Token],
    ) -> list[Token]:
        state = TrackingStateInline(src, md, env, tokens)
        self.tokenize(state)
        for rule in self.ruler2.getRules(""):
            rule(state)
        return state.tokens


class TrackingParserBlock(ParserBlock):
    """ParserBlock adapter retaining effective container-relative ranges."""

    def tokenize(self, state: StateBlock, startLine: int, endLine: int) -> None:
        rules = self.ruler.getRules("")
        line = startLine
        max_nesting = state.md.options.maxNesting
        has_empty_lines = False

        while line < endLine:
            state.line = line = state.skipEmptyLines(line)
            if line >= endLine or state.sCount[line] < state.blkIndent:
                break
            if state.level >= max_nesting:
                state.line = endLine
                break

            matched = False
            for rule in rules:
                token_count = len(state.tokens)
                if not rule(state, line, endLine, False):
                    continue
                matched = True
                for token in state.tokens[token_count:]:
                    if token.map is None or _BLOCK_SPAN_META_KEY in token.meta:
                        continue
                    token_start_line, token_end_line = token.map
                    token.meta[_BLOCK_SPAN_META_KEY] = (
                        block_node_start(state, token_start_line),
                        state.eMarks[token_end_line - 1],
                    )
                break
            if not matched:
                raise ValueError("Markdown block parser made no source progress")

            state.tight = not has_empty_lines
            line = state.line
            if (line - 1) < endLine and state.isEmpty(line - 1):
                has_empty_lines = True
            if line < endLine and state.isEmpty(line):
                has_empty_lines = True
                line += 1
                state.line = line


def block_node_start(state: StateBlock, line: int) -> int:
    """Skip parent-container indentation while retaining node-local syntax."""

    position = state.bMarks[line]
    line_start = position
    indentation = 0
    while position < state.eMarks[line] and indentation < state.blkIndent:
        character = state.src[position]
        if character == "\t":
            indentation += 4 - (indentation + state.bsCount[line]) % 4
        elif character == " " or position - line_start < state.tShift[line]:
            indentation += 1
        else:
            break
        position += 1
    return position


def _break_span(source: str, start: int, pending_before: str) -> tuple[int, int]:
    if source[start] == "\\":
        return start, start + 2
    trailing_spaces = len(pending_before) - len(pending_before.rstrip(" "))
    return start - trailing_spaces, start + 1


def token_relative_span(token: Token) -> tuple[int, int]:
    value = token.meta.get(_SPAN_META_KEY)
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not all(isinstance(position, int) for position in value)
    ):
        raise ValueError(f"Inline token {token.type!r} has no exact source span")
    return value


def token_block_span(token: Token) -> tuple[int, int]:
    value = token.meta.get(_BLOCK_SPAN_META_KEY)
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not all(isinstance(position, int) for position in value)
    ):
        raise ValueError(f"Block token {token.type!r} has no exact source span")
    return value


__all__ = [
    "MappedText",
    "NormalizedSource",
    "SourceIndex",
    "TrackingParserBlock",
    "TrackingParserInline",
    "block_node_start",
    "token_block_span",
    "token_relative_span",
]
