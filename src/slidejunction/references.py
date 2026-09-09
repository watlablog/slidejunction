"""Derived configuration-reference indexing and global validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias, TypeVar

from .document import (
    Block,
    BlockQuote,
    CodeBlock,
    ConfigPointer,
    Diagnostic,
    DiagnosticSeverity,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    Inline,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    MathBlock,
    Paragraph,
    Section,
    Slide,
    SoftBreak,
    SourceDocument,
    SourceSpan,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)
from .layout import Configuration, InlineFormatConfiguration, LayoutDocument


class ReferenceKind(StrEnum):
    """The definition namespace required by a semantic consumer."""

    CONFIGURATION = "configuration"
    INLINE_FORMAT = "inline-format"


ConfigurationConsumer: TypeAlias = (
    Heading
    | Paragraph
    | ListBlock
    | BlockQuote
    | CodeBlock
    | ImageBlock
    | ThematicBreak
    | MathBlock
)
ReferenceConsumer: TypeAlias = ConfigurationConsumer | InlineFormat
ReferenceValue: TypeAlias = Configuration | InlineFormatConfiguration

_CONFIGURATION_CONSUMERS = (
    Heading,
    Paragraph,
    ListBlock,
    BlockQuote,
    CodeBlock,
    ImageBlock,
    ThematicBreak,
    MathBlock,
)
_INLINE_CONTAINERS = (Strong, Emphasis, Link, Superscript, Subscript)
_INLINE_LEAVES = (Text, InlineCode, InlineImage, SoftBreak, HardBreak, InlineMath)
_KIND_ORDER = {
    ReferenceKind.CONFIGURATION: 0,
    ReferenceKind.INLINE_FORMAT: 1,
}
_BLOCKING_SOURCE_REFERENCE_DIAGNOSTIC_CODES = frozenset(
    {
        "invalid-config-ref-marker",
        "unused-config-ref",
        "unsupported-nested-config-ref",
        "unterminated-inline-format",
        "invalid-inline-format-tag",
        "unsupported-setext-heading",
        "unsupported-raw-html",
        "unterminated-inline-math",
        "unterminated-block-math",
    }
)
_NON_BLOCKING_SOURCE_REFERENCE_DIAGNOSTIC_CODES = frozenset(
    {"unexpected-inline-format-close"}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class _ConsumerOccurrence:
    """One traversal occurrence, including consumers without a reference."""

    consumer: ReferenceConsumer
    block_depth: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceDefinition:
    """One persistent layout definition in the global ref namespace."""

    ref_id: int
    kind: ReferenceKind
    value: ReferenceValue
    config_pointer: ConfigPointer

    def __post_init__(self) -> None:
        _validate_ref_id(self.ref_id)
        _validate_kind(self.kind)
        if not isinstance(self.config_pointer, ConfigPointer):
            raise TypeError("Reference definition location must be a ConfigPointer")
        expected = (
            Configuration
            if self.kind is ReferenceKind.CONFIGURATION
            else InlineFormatConfiguration
        )
        if not isinstance(self.value, expected):
            raise TypeError(f"{self.kind.value} definition has an incompatible value")
        expected_pointer = (
            f"/configurations/{self.ref_id}"
            if self.kind is ReferenceKind.CONFIGURATION
            else f"/inline_formats/{self.ref_id}"
        )
        if self.config_pointer.pointer != expected_pointer:
            raise ValueError(
                f"{self.kind.value} definition pointer must be {expected_pointer!r}"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceUsage:
    """One semantic source consumer of a configuration ref."""

    ref_id: int
    kind: ReferenceKind
    consumer: ReferenceConsumer
    source_span: SourceSpan

    def __post_init__(self) -> None:
        _validate_ref_id(self.ref_id)
        _validate_kind(self.kind)
        if not isinstance(self.source_span, SourceSpan):
            raise TypeError("Reference usage location must be a SourceSpan")
        if self.kind is ReferenceKind.CONFIGURATION:
            if not isinstance(self.consumer, _CONFIGURATION_CONSUMERS):
                raise TypeError("Configuration usage has an incompatible consumer")
            expected_span = (
                self.consumer.source_binding.config_marker_span
                if self.consumer.source_binding.config_marker_span is not None
                else self.consumer.source_binding.syntax_span
            )
        elif not isinstance(self.consumer, InlineFormat):
            raise TypeError("Inline-format usage has an incompatible consumer")
        else:
            expected_span = self.consumer.source_span
        if self.consumer.config_ref != self.ref_id:
            raise ValueError("Reference usage ID does not match the consumer ref")
        if self.source_span != expected_span:
            raise ValueError("Reference usage location does not match the consumer")


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceIndex:
    """Immutable derived lookup tables, including invalid global ref graphs."""

    definitions: Mapping[int, tuple[ReferenceDefinition, ...]]
    usages: Mapping[int, tuple[ReferenceUsage, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definitions",
            _freeze_groups(self.definitions, ReferenceDefinition, "definitions"),
        )
        object.__setattr__(
            self,
            "usages",
            _freeze_groups(self.usages, ReferenceUsage, "usages"),
        )

    def definitions_for(
        self,
        ref_id: int,
        *,
        kind: ReferenceKind | None = None,
    ) -> tuple[ReferenceDefinition, ...]:
        """Return definitions for an ID, optionally filtered by namespace."""
        _validate_ref_id(ref_id)
        _validate_optional_kind(kind)
        definitions = self.definitions.get(ref_id, ())
        if kind is None:
            return definitions
        return tuple(item for item in definitions if item.kind is kind)

    def usages_for(
        self,
        ref_id: int,
        *,
        kind: ReferenceKind | None = None,
    ) -> tuple[ReferenceUsage, ...]:
        """Return usages for an ID, optionally filtered by expected namespace."""
        _validate_ref_id(ref_id)
        _validate_optional_kind(kind)
        usages = self.usages.get(ref_id, ())
        if kind is None:
            return usages
        return tuple(item for item in usages if item.kind is kind)

    def consumer_count(self, ref_id: int, kind: ReferenceKind) -> int:
        """Count semantic consumers of one ID within one expected namespace."""
        _validate_kind(kind)
        return len(self.usages_for(ref_id, kind=kind))

    def is_shared(self, ref_id: int, kind: ReferenceKind) -> bool:
        """Whether one kind-specific ref has more than one semantic consumer."""
        _validate_kind(kind)
        return self.consumer_count(ref_id, kind) > 1


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceValidationResult:
    """A derived reference index and its cross-document diagnostics."""

    index: ReferenceIndex
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.index, ReferenceIndex):
            raise TypeError("Reference validation result requires a ReferenceIndex")
        if not isinstance(self.diagnostics, tuple) or not all(
            isinstance(item, Diagnostic) for item in self.diagnostics
        ):
            raise TypeError(
                "Reference diagnostics must be a tuple of Diagnostic objects"
            )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


def validate_references(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    *,
    layout_path: str | Path | None = None,
) -> ReferenceValidationResult:
    """Build and validate a derived ref graph without filesystem I/O."""
    provenance = None if layout_path is None else Path(layout_path)
    index = _build_reference_index(
        source_document,
        layout_document,
        layout_path=provenance,
    )
    return ReferenceValidationResult(
        index=index,
        diagnostics=_validate_index(index),
    )


def _build_reference_index(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    *,
    layout_path: Path | None,
) -> ReferenceIndex:
    """Build the pure derived index without producing diagnostics."""
    if not isinstance(source_document, SourceDocument):
        raise TypeError("source_document must be a SourceDocument")
    if not isinstance(layout_document, LayoutDocument):
        raise TypeError("layout_document must be a LayoutDocument")
    if layout_path is not None and not isinstance(layout_path, Path):
        raise TypeError("layout_path must be a Path or None")
    definitions = _collect_definitions(layout_document, layout_path)
    usages = _collect_usages(source_document)
    return ReferenceIndex(
        definitions=_group_references(definitions),
        usages=_group_references(usages),
    )


def _collect_definitions(
    document: LayoutDocument,
    path: Path | None,
) -> tuple[ReferenceDefinition, ...]:
    definitions: list[ReferenceDefinition] = []
    for ref_id, value in sorted(document.configurations.items()):
        definitions.append(
            ReferenceDefinition(
                ref_id=ref_id,
                kind=ReferenceKind.CONFIGURATION,
                value=value,
                config_pointer=ConfigPointer(
                    path=path,
                    pointer=f"/configurations/{ref_id}",
                ),
            )
        )
    for ref_id, value in sorted(document.inline_formats.items()):
        definitions.append(
            ReferenceDefinition(
                ref_id=ref_id,
                kind=ReferenceKind.INLINE_FORMAT,
                value=value,
                config_pointer=ConfigPointer(
                    path=path,
                    pointer=f"/inline_formats/{ref_id}",
                ),
            )
        )
    return tuple(definitions)


def _validate_reference_snapshot(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> None:
    """Check graph identity consistency, without proving root provenance."""
    if not isinstance(reference_index, ReferenceIndex):
        raise TypeError("reference_index must be a ReferenceIndex")
    expected_index = _build_reference_index(
        source_document,
        layout_document,
        layout_path=None,
    )
    if not _indexes_match(reference_index, expected_index):
        raise ValueError(
            "reference_index does not match source_document and layout_document"
        )


def _indexes_match(actual: ReferenceIndex, expected: ReferenceIndex) -> bool:
    if tuple(actual.definitions) != tuple(expected.definitions):
        return False
    if tuple(actual.usages) != tuple(expected.usages):
        return False
    for ref_id in expected.definitions:
        actual_group = actual.definitions[ref_id]
        expected_group = expected.definitions[ref_id]
        if len(actual_group) != len(expected_group):
            return False
        for candidate, reference in zip(actual_group, expected_group, strict=True):
            if (
                candidate.ref_id != reference.ref_id
                or candidate.kind is not reference.kind
                or candidate.value is not reference.value
                or candidate.config_pointer.pointer != reference.config_pointer.pointer
            ):
                return False
    for ref_id in expected.usages:
        actual_group = actual.usages[ref_id]
        expected_group = expected.usages[ref_id]
        if len(actual_group) != len(expected_group):
            return False
        for candidate, reference in zip(actual_group, expected_group, strict=True):
            if (
                candidate.ref_id != reference.ref_id
                or candidate.kind is not reference.kind
                or candidate.consumer is not reference.consumer
                or candidate.source_span != reference.source_span
            ):
                return False
    return True


def _require_reliable_reference_discovery(source_document: SourceDocument) -> None:
    """Reject source diagnostics that may hide reference intent, including unknowns.

    This assumes a parse_markdown() result or an equivalently consistent snapshot
    of text, semantic nodes, spans, and diagnostics. It does not reparse source or
    prove root provenance. Graph validation is separate from this source-only gate;
    severity alone never establishes that reference discovery is complete.
    """
    if not isinstance(source_document, SourceDocument):
        raise TypeError("source_document must be a SourceDocument")
    for diagnostic in source_document.presentation.diagnostics:
        if diagnostic.code in _BLOCKING_SOURCE_REFERENCE_DIAGNOSTIC_CODES:
            raise ValueError(
                f"Source diagnostic {diagnostic.code!r} blocks reference discovery"
            )
        if diagnostic.code not in _NON_BLOCKING_SOURCE_REFERENCE_DIAGNOSTIC_CODES:
            raise ValueError(
                f"Unknown source diagnostic {diagnostic.code!r}: "
                "reference discovery reliability cannot be established"
            )


def _collect_usages(document: SourceDocument) -> tuple[ReferenceUsage, ...]:
    usages: list[ReferenceUsage] = []
    for occurrence in _collect_consumer_occurrences(document):
        consumer = occurrence.consumer
        if isinstance(consumer, InlineFormat):
            usages.append(
                ReferenceUsage(
                    ref_id=consumer.config_ref,
                    kind=ReferenceKind.INLINE_FORMAT,
                    consumer=consumer,
                    source_span=consumer.source_span,
                )
            )
        elif consumer.config_ref is not None:
            marker = consumer.source_binding.config_marker_span
            usages.append(
                ReferenceUsage(
                    ref_id=consumer.config_ref,
                    kind=ReferenceKind.CONFIGURATION,
                    consumer=consumer,
                    source_span=marker or consumer.source_binding.syntax_span,
                )
            )
    return tuple(
        usage
        for _, usage in sorted(
            enumerate(usages),
            key=lambda item: (item[1].source_span.start_offset, item[0]),
        )
    )


def _collect_consumer_occurrences(
    document: SourceDocument,
) -> tuple[_ConsumerOccurrence, ...]:
    """Visit consumers in semantic traversal order without deduplicating identity."""
    if not isinstance(document, SourceDocument):
        raise TypeError("source_document must be a SourceDocument")
    occurrences: list[_ConsumerOccurrence] = []
    for item in document.presentation.items:
        if isinstance(item, Slide):
            _visit_slide(item, occurrences)
        elif isinstance(item, Section):
            _visit_slide(item.title_slide, occurrences)
            for slide in item.slides:
                _visit_slide(slide, occurrences)
        else:  # pragma: no cover - SourceDocument model contract
            raise TypeError("Presentation contains an invalid item")
    return tuple(occurrences)


def _visit_slide(slide: Slide, occurrences: list[_ConsumerOccurrence]) -> None:
    if slide.title is not None:
        _visit_block(slide.title, occurrences, depth=0)
    for block in slide.blocks:
        _visit_block(block, occurrences, depth=0)


def _visit_block(
    block: Block,
    occurrences: list[_ConsumerOccurrence],
    *,
    depth: int,
) -> None:
    if not isinstance(block, _CONFIGURATION_CONSUMERS):
        raise TypeError("Presentation contains an invalid block")
    occurrences.append(_ConsumerOccurrence(consumer=block, block_depth=depth))

    if isinstance(block, Heading | Paragraph):
        for inline in block.children:
            _visit_inline(inline, occurrences, depth=depth)
    elif isinstance(block, ListBlock):
        for item in block.items:
            for child in item.blocks:
                _visit_block(child, occurrences, depth=depth + 1)
    elif isinstance(block, BlockQuote):
        for child in block.blocks:
            _visit_block(child, occurrences, depth=depth + 1)


def _visit_inline(
    inline: Inline,
    occurrences: list[_ConsumerOccurrence],
    *,
    depth: int,
) -> None:
    if isinstance(inline, InlineFormat):
        occurrences.append(_ConsumerOccurrence(consumer=inline, block_depth=depth))
        for child in inline.children:
            _visit_inline(child, occurrences, depth=depth)
        return
    if isinstance(inline, _INLINE_CONTAINERS):
        for child in inline.children:
            _visit_inline(child, occurrences, depth=depth)
        return
    if isinstance(inline, _INLINE_LEAVES):
        return
    raise TypeError("Presentation contains an invalid inline node")


def _validate_index(index: ReferenceIndex) -> tuple[Diagnostic, ...]:
    duplicate_ids = {
        ref_id
        for ref_id in index.definitions
        if index.definitions_for(ref_id, kind=ReferenceKind.CONFIGURATION)
        and index.definitions_for(ref_id, kind=ReferenceKind.INLINE_FORMAT)
    }
    duplicates = tuple(
        _duplicate_diagnostic(index, ref_id) for ref_id in sorted(duplicate_ids)
    )

    usage_diagnostics: list[Diagnostic] = []
    mismatch_ids: set[int] = set()
    for ref_id in index.usages:
        for kind in ReferenceKind:
            usages = index.usages_for(ref_id, kind=kind)
            if not usages or ref_id in duplicate_ids:
                continue
            if index.definitions_for(ref_id, kind=kind):
                continue
            opposite = _opposite_kind(kind)
            opposite_definitions = index.definitions_for(ref_id, kind=opposite)
            if opposite_definitions:
                mismatch_ids.add(ref_id)
                usage_diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code="ref-kind-mismatch",
                        message=(
                            f"Reference {ref_id} has no {kind.value} definition; "
                            f"a {opposite.value} definition exists instead."
                        ),
                        source_span=usages[0].source_span,
                        ref_id=ref_id,
                        related_locations=(
                            opposite_definitions[0].config_pointer,
                            *(usage.source_span for usage in usages[1:]),
                        ),
                    )
                )
                continue
            code = (
                "missing-configuration-ref"
                if kind is ReferenceKind.CONFIGURATION
                else "missing-inline-format-ref"
            )
            usage_diagnostics.append(
                Diagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code=code,
                    message=f"Reference {ref_id} has no {kind.value} definition.",
                    source_span=usages[0].source_span,
                    ref_id=ref_id,
                    related_locations=tuple(usage.source_span for usage in usages[1:]),
                )
            )

    usage_diagnostics.sort(
        key=lambda item: (
            item.source_span.start_offset,
            item.source_span.end_offset,
            item.code,
            item.ref_id,
        )
    )

    unused: list[Diagnostic] = []
    suppressed_unused = duplicate_ids | mismatch_ids
    for ref_id in index.definitions:
        if ref_id in suppressed_unused:
            continue
        for definition in sorted(
            index.definitions_for(ref_id),
            key=lambda item: _KIND_ORDER[item.kind],
        ):
            if index.usages_for(ref_id, kind=definition.kind):
                continue
            code = (
                "unused-configuration"
                if definition.kind is ReferenceKind.CONFIGURATION
                else "unused-inline-format"
            )
            unused.append(
                Diagnostic(
                    severity=DiagnosticSeverity.INFO,
                    code=code,
                    message=(
                        f"Reference {ref_id} is a legal persistent definition with "
                        "no current semantic consumer and is a candidate for explicit GC."
                    ),
                    config_pointer=definition.config_pointer,
                    ref_id=ref_id,
                )
            )

    return (*duplicates, *usage_diagnostics, *unused)


def _duplicate_diagnostic(index: ReferenceIndex, ref_id: int) -> Diagnostic:
    configuration = index.definitions_for(
        ref_id,
        kind=ReferenceKind.CONFIGURATION,
    )[0]
    inline_format = index.definitions_for(
        ref_id,
        kind=ReferenceKind.INLINE_FORMAT,
    )[0]
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="duplicate-global-ref",
        message=f"Reference {ref_id} is defined in both configuration namespaces.",
        config_pointer=inline_format.config_pointer,
        ref_id=ref_id,
        related_locations=(configuration.config_pointer,),
    )


_ReferenceT = TypeVar("_ReferenceT", ReferenceDefinition, ReferenceUsage)


def _group_references(
    references: tuple[_ReferenceT, ...],
) -> Mapping[int, tuple[_ReferenceT, ...]]:
    groups: dict[int, list[_ReferenceT]] = {}
    for reference in references:
        groups.setdefault(reference.ref_id, []).append(reference)
    return {ref_id: tuple(groups[ref_id]) for ref_id in sorted(groups)}


def _freeze_groups(
    groups: Mapping[int, tuple[_ReferenceT, ...]],
    expected: type[_ReferenceT],
    name: str,
) -> Mapping[int, tuple[_ReferenceT, ...]]:
    if not isinstance(groups, Mapping):
        raise TypeError(f"Reference {name} must be a mapping")
    copied: dict[int, tuple[_ReferenceT, ...]] = {}
    for ref_id in groups:
        _validate_ref_id(ref_id)
    for ref_id in sorted(groups):
        values = groups[ref_id]
        if not isinstance(values, tuple):
            raise TypeError(f"Reference {name} values must be tuples")
        value_tuple = tuple(values)
        if not value_tuple:
            raise ValueError(f"Reference {name} groups must not be empty")
        if not all(isinstance(item, expected) for item in value_tuple):
            raise TypeError(f"Reference {name} contain an invalid entry")
        if any(item.ref_id != ref_id for item in value_tuple):
            raise ValueError(f"Reference {name} key does not match an entry ID")
        copied[ref_id] = value_tuple
    return MappingProxyType(copied)


def _validate_ref_id(ref_id: int) -> None:
    if not isinstance(ref_id, int) or isinstance(ref_id, bool) or ref_id < 1:
        raise ValueError("Reference ID must be a positive integer")


def _validate_kind(kind: ReferenceKind) -> None:
    if not isinstance(kind, ReferenceKind):
        raise TypeError("Reference kind must be a ReferenceKind")


def _validate_optional_kind(kind: ReferenceKind | None) -> None:
    if kind is not None:
        _validate_kind(kind)


def _opposite_kind(kind: ReferenceKind) -> ReferenceKind:
    return (
        ReferenceKind.INLINE_FORMAT
        if kind is ReferenceKind.CONFIGURATION
        else ReferenceKind.CONFIGURATION
    )


__all__ = [
    "ReferenceDefinition",
    "ReferenceIndex",
    "ReferenceKind",
    "ReferenceUsage",
    "ReferenceValidationResult",
    "validate_references",
]
