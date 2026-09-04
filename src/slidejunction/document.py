"""Immutable semantic Document Model for SlideJunction presentations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TypeAlias


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceSpan:
    """A zero-based, half-open range in the original source text."""

    start_offset: int
    end_offset: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def __post_init__(self) -> None:
        positions = (
            self.start_offset,
            self.end_offset,
            self.start_line,
            self.start_column,
            self.end_line,
            self.end_column,
        )
        if any(position < 0 for position in positions):
            raise ValueError("Source positions must be non-negative")
        if self.start_offset > self.end_offset:
            raise ValueError("Source span start offset must not exceed end offset")
        if (self.start_line, self.start_column) > (self.end_line, self.end_column):
            raise ValueError("Source span start position must not exceed end position")


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigPointer:
    """An RFC 6901 JSON Pointer with optional source provenance."""

    pointer: str
    path: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pointer, str):
            raise TypeError("JSON Pointer must be a string")
        if self.pointer and not self.pointer.startswith("/"):
            raise ValueError("A non-root JSON Pointer must start with '/'")
        if "~" in self.pointer.replace("~0", "").replace("~1", ""):
            raise ValueError("JSON Pointer contains an invalid escape sequence")
        if self.path is not None and not isinstance(self.path, Path):
            raise TypeError("Configuration provenance path must be a Path or None")


DiagnosticLocation: TypeAlias = SourceSpan | ConfigPointer


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceBinding:
    """Source ranges for a node's Markdown syntax and optional config marker."""

    syntax_span: SourceSpan
    config_marker_span: SourceSpan | None = None


class DiagnosticSeverity(StrEnum):
    """Severity levels for non-fatal source diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class Diagnostic:
    """A source- or configuration-bound issue."""

    severity: DiagnosticSeverity
    code: str
    message: str
    source_span: SourceSpan | None = None
    config_pointer: ConfigPointer | None = None
    ref_id: int | None = None
    related_locations: tuple[DiagnosticLocation, ...] = ()
    hint: str | None = None

    def __post_init__(self) -> None:
        if self.source_span is not None and not isinstance(
            self.source_span, SourceSpan
        ):
            raise TypeError("Diagnostic source_span must be a SourceSpan or None")
        if self.config_pointer is not None and not isinstance(
            self.config_pointer, ConfigPointer
        ):
            raise TypeError("Diagnostic config_pointer must be a ConfigPointer or None")
        if (self.source_span is None) == (self.config_pointer is None):
            raise ValueError(
                "A diagnostic must have exactly one source span or config pointer"
            )
        _validate_config_ref(self.ref_id)
        locations = tuple(self.related_locations)
        if not all(isinstance(item, SourceSpan | ConfigPointer) for item in locations):
            raise TypeError("Related diagnostic locations are invalid")
        object.__setattr__(self, "related_locations", locations)

    @property
    def location(self) -> DiagnosticLocation:
        """Return the diagnostic's derived location."""
        if self.source_span is not None:
            return self.source_span
        if self.config_pointer is None:  # pragma: no cover - protected by validation
            raise ValueError("Diagnostic location is missing")
        return self.config_pointer


@dataclass(frozen=True, slots=True, kw_only=True)
class Text:
    """Plain inline text."""

    value: str
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class Strong:
    """Strongly emphasized inline content."""

    children: tuple[Inline, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class Emphasis:
    """Emphasized inline content."""

    children: tuple[Inline, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineCode:
    """Inline code with an optional future configuration reference."""

    code: str
    source_span: SourceSpan
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class Link:
    """A hyperlink containing nested inline content."""

    destination: str
    children: tuple[Inline, ...]
    source_span: SourceSpan
    title: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineImage:
    """An image embedded within other inline content."""

    src: str
    alt: str
    source_span: SourceSpan
    title: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SoftBreak:
    """A CommonMark soft line break."""

    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class HardBreak:
    """A CommonMark hard line break."""

    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineMath:
    """Renderer-independent inline math content."""

    content: str
    source_span: SourceSpan
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


Inline: TypeAlias = (
    Text
    | Strong
    | Emphasis
    | InlineCode
    | Link
    | InlineImage
    | SoftBreak
    | HardBreak
    | InlineMath
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Heading:
    """A visible heading, including H1/H2 slide titles."""

    level: int
    children: tuple[Inline, ...]
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.level <= 6:
            raise ValueError("Heading level must be between 1 and 6")
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class Paragraph:
    """A paragraph and future GUI text-object unit."""

    children: tuple[Inline, ...]
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class ListItem:
    """A list item containing nested semantic blocks."""

    blocks: tuple[Block, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class ListBlock:
    """An ordered or unordered list represented as one layout block."""

    ordered: bool
    start: int | None
    items: tuple[ListItem, ...]
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class BlockQuote:
    """A block quote containing nested semantic blocks."""

    blocks: tuple[Block, ...]
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeBlock:
    """Display-only fenced or indented code."""

    code: str
    language: str | None
    info: str | None
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageBlock:
    """A standalone image promoted from an image-only paragraph."""

    src: str
    alt: str
    source_binding: SourceBinding
    title: str | None = None
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class ThematicBreak:
    """A thematic break within a slide."""

    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class MathBlock:
    """Renderer-independent display math content."""

    content: str
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


Block: TypeAlias = (
    Heading
    | Paragraph
    | ListBlock
    | BlockQuote
    | CodeBlock
    | ImageBlock
    | ThematicBreak
    | MathBlock
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Slide:
    """A slide spanning its complete original Markdown source.

    ``source_span`` starts at the slide title's bound configuration marker,
    when present, or at the title syntax. An implicit slide starts at its first
    block's bound marker or syntax. It ends where the next slide starts, while
    the final slide ends at EOF. Empty implicit slides may use a zero-width
    span at the start of the source.
    """

    title: Heading | None
    blocks: tuple[Block, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class Section:
    """An H1 title slide and the regular slides that follow it."""

    title_slide: Slide
    slides: tuple[Slide, ...] = ()


PresentationItem: TypeAlias = Slide | Section


@dataclass(frozen=True, slots=True, kw_only=True)
class Presentation:
    """A presentation containing unsectioned slides and H1 sections."""

    items: tuple[PresentationItem, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceDocument:
    """An immutable semantic snapshot tied to its original source text."""

    path: Path | None
    text: str
    presentation: Presentation


def _validate_config_ref(config_ref: int | None) -> None:
    if config_ref is None:
        return
    if (
        not isinstance(config_ref, int)
        or isinstance(config_ref, bool)
        or config_ref < 1
    ):
        raise ValueError("Configuration reference must be a positive integer")


__all__ = [
    "Block",
    "BlockQuote",
    "CodeBlock",
    "ConfigPointer",
    "Diagnostic",
    "DiagnosticLocation",
    "DiagnosticSeverity",
    "Emphasis",
    "HardBreak",
    "Heading",
    "ImageBlock",
    "Inline",
    "InlineCode",
    "InlineImage",
    "InlineMath",
    "Link",
    "ListBlock",
    "ListItem",
    "MathBlock",
    "Paragraph",
    "Presentation",
    "PresentationItem",
    "Section",
    "Slide",
    "SoftBreak",
    "SourceBinding",
    "SourceDocument",
    "SourceSpan",
    "Strong",
    "Text",
    "ThematicBreak",
]
