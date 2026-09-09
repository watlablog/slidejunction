"""Pure reference edits and semantic source-change plans for immutable snapshots.

Source inputs must be consistent semantic snapshots such as those returned by
``parse_markdown``. This module checks graph membership and local change anchors;
it does not reparse text or prove source provenance. Returned source documents
remain unchanged. A future source writer must apply pending changes and reparse
before resolving the updated source/layout pair.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal, TypeAlias, overload

from ._reference_syntax import (
    _INLINE_FORMAT_CLOSE,
    _INLINE_FORMAT_OPEN,
    _format_config_ref_marker,
)
from .document import Block, InlineFormat, SourceBinding, SourceDocument, SourceSpan
from .layout import Configuration, InlineFormatConfiguration, LayoutDocument
from .references import (
    ReferenceConsumer,
    ReferenceIndex,
    ReferenceKind,
    ReferenceValue,
    _collect_consumer_occurrences,
    _require_reliable_reference_discovery,
    _validate_reference_snapshot,
)

_Operation: TypeAlias = Literal[
    "block-attach",
    "block-retarget",
    "block-detach",
    "inline-retarget",
    "inline-unwrap",
]
_ConfigurationEditor: TypeAlias = Callable[[Configuration], Configuration]
_InlineFormatEditor: TypeAlias = Callable[
    [InlineFormatConfiguration], InlineFormatConfiguration
]
_Editor: TypeAlias = _ConfigurationEditor | _InlineFormatEditor


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceReferenceChange:
    """One semantic reference change, retaining the original consumer identity.

    A block attach anchors immediately before ``source_span.start_offset``.
    Other block operations identify the exact existing marker; inline operations
    identify the whole existing wrapper. No replacement text is generated.
    """

    consumer: ReferenceConsumer
    new_ref_id: int | None

    def __post_init__(self) -> None:
        _consumer_kind(self.consumer)
        _optional_ref_id(self.new_ref_id, "new_ref_id")
        if self.old_ref_id == self.new_ref_id:
            raise ValueError("Source reference change must change the reference")
        if not isinstance(self.consumer, InlineFormat):
            binding = self.consumer.source_binding
            if not isinstance(binding, SourceBinding):
                raise TypeError("Block source binding must be a SourceBinding")
            if self.old_ref_id is None and binding.config_marker_span is not None:
                raise ValueError("A block without a ref cannot have a marker binding")
            if self.old_ref_id is not None and binding.config_marker_span is None:
                raise ValueError("An existing block ref requires an exact marker span")
            if not isinstance(binding.syntax_span, SourceSpan):
                raise TypeError("Block syntax location must be a SourceSpan")
        if not isinstance(self.source_span, SourceSpan):
            raise TypeError("Source reference change location must be a SourceSpan")

    @property
    def kind(self) -> ReferenceKind:
        """The namespace required by the original semantic consumer."""
        return _consumer_kind(self.consumer)

    @property
    def old_ref_id(self) -> int | None:
        """The reference still present in the original source snapshot."""
        return self.consumer.config_ref

    @property
    def source_span(self) -> SourceSpan:
        """The syntax anchor, existing marker, or complete inline wrapper."""
        if isinstance(self.consumer, InlineFormat):
            return self.consumer.source_span
        binding = self.consumer.source_binding
        if self.old_ref_id is None:
            return binding.syntax_span
        return binding.config_marker_span

    @property
    def operation(self) -> _Operation:
        """The operation derived from consumer kind and old/new references."""
        if isinstance(self.consumer, InlineFormat):
            return "inline-unwrap" if self.new_ref_id is None else "inline-retarget"
        if self.old_ref_id is None:
            return "block-attach"
        return "block-detach" if self.new_ref_id is None else "block-retarget"


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceEditResult:
    """An updated layout paired with at most one pending semantic source change.

    The original source is retained, with no derived index for the pending pair.
    The constructor validates selection, anchors and required definitions. Edit
    functions additionally guarantee the exact layout delta and preserve old
    definitions when a source ref is changed or detached.

    ``selected_ref_id`` is the selection's ref after the planned operation: the
    new ID for attach/retarget, None for detach, or its current ID without a change.
    """

    source_document: SourceDocument
    layout_document: LayoutDocument
    selected_consumer: ReferenceConsumer
    source_changes: tuple[SourceReferenceChange, ...]
    selected_ref_id: int | None

    def __post_init__(self) -> None:
        _require_instance(self.source_document, SourceDocument, "source_document")
        _require_instance(self.layout_document, LayoutDocument, "layout_document")
        kind = _consumer_kind(self.selected_consumer)
        _optional_ref_id(self.selected_ref_id, "selected_ref_id")
        if not isinstance(self.source_changes, tuple) or not all(
            isinstance(change, SourceReferenceChange) for change in self.source_changes
        ):
            raise TypeError("source_changes must be a tuple of SourceReferenceChange")
        if len(self.source_changes) > 1:
            raise ValueError("A reference edit result can change only one consumer")
        depth = _consumer_depth(self.source_document, self.selected_consumer)
        old_ref_id = self.selected_consumer.config_ref
        if old_ref_id is not None:
            _definition_value(self.layout_document, kind, old_ref_id)
        if not self.source_changes:
            if self.selected_ref_id != old_ref_id:
                raise ValueError("Unchanged selection must retain its current ref")
            return

        change = self.source_changes[0]
        if change.consumer is not self.selected_consumer:
            raise ValueError("Source change must target the selected consumer identity")
        if self.selected_ref_id != change.new_ref_id:
            raise ValueError("Selected ref must match the pending source change")
        if change.new_ref_id is not None:
            _definition_value(self.layout_document, kind, change.new_ref_id)
        _validate_change_anchor(self.source_document, change, depth)


def allocate_reference_id(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> int:
    """Allocate max known global ID + 1 from a reliable, matching snapshot graph.

    Source must come from parse_markdown() or an equivalently consistent snapshot.
    The checks neither reparse full text nor prove source/root provenance.
    """
    _validate_reference_snapshot(source_document, layout_document, reference_index)
    _require_reliable_reference_discovery(source_document)
    return _next_reference_id(reference_index)


@overload
def edit_consumer_locally(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: Block,
    *,
    editor: _ConfigurationEditor,
) -> ReferenceEditResult: ...


@overload
def edit_consumer_locally(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: InlineFormat,
    *,
    editor: _InlineFormatEditor,
) -> ReferenceEditResult: ...


def edit_consumer_locally(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
    *,
    editor: _Editor,
) -> ReferenceEditResult:
    """Edit a full stored sparse value, allocating or forking only on change.

    The callback runs once. Equal results return before the reliability gate;
    every actual local edit requires reliable discovery, including edits under
    an existing single-consumer ID.

    Source must come from parse_markdown() or an equivalently consistent snapshot.
    The checks neither reparse full text nor prove source/root provenance.
    """
    if not callable(editor):
        raise TypeError("editor must be callable")
    kind, base = _prepare_selection(
        source_document, layout_document, reference_index, consumer
    )
    if base is None:
        base = Configuration()
    edited = _apply_editor(editor, base, kind)
    if edited == base:
        return _result(source_document, layout_document, consumer)

    _require_reliable_reference_discovery(source_document)
    old_ref_id = consumer.config_ref
    if old_ref_id is not None and reference_index.consumer_count(old_ref_id, kind) == 1:
        updated = _store_definition(layout_document, kind, old_ref_id, edited)
        return _result(source_document, updated, consumer)

    _require_source_change_context(consumer, _consumer_depth(source_document, consumer))
    new_ref_id = _next_reference_id(reference_index)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=new_ref_id)
    updated = _store_definition(layout_document, kind, new_ref_id, edited)
    return _result(source_document, updated, consumer, change)


@overload
def edit_shared_definition(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: Block,
    *,
    editor: _ConfigurationEditor,
) -> ReferenceEditResult: ...


@overload
def edit_shared_definition(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: InlineFormat,
    *,
    editor: _InlineFormatEditor,
) -> ReferenceEditResult: ...


def edit_shared_definition(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
    *,
    editor: _Editor,
) -> ReferenceEditResult:
    """Explicitly edit one existing definition for all its consumers, without fork."""
    if not callable(editor):
        raise TypeError("editor must be callable")
    kind, base = _prepare_selection(
        source_document, layout_document, reference_index, consumer
    )
    if base is None:
        raise ValueError("Shared definition editing requires an existing reference")
    edited = _apply_editor(editor, base, kind)
    if edited == base:
        return _result(source_document, layout_document, consumer)
    updated = _store_definition(layout_document, kind, consumer.config_ref, edited)
    return _result(source_document, updated, consumer)


def set_consumer_reference(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
    *,
    ref_id: int,
) -> ReferenceEditResult:
    """Plan attachment or retargeting to an existing, unambiguous definition."""
    _positive_ref_id(ref_id, "ref_id")
    kind, _ = _prepare_selection(
        source_document, layout_document, reference_index, consumer
    )
    _definition_value(layout_document, kind, ref_id)
    if consumer.config_ref == ref_id:
        return _result(source_document, layout_document, consumer)
    return _result(
        source_document,
        layout_document,
        consumer,
        SourceReferenceChange(consumer=consumer, new_ref_id=ref_id),
    )


def detach_reference(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
) -> ReferenceEditResult:
    """Plan marker removal or inline unwrapping, retaining the definition."""
    _prepare_selection(source_document, layout_document, reference_index, consumer)
    if consumer.config_ref is None:
        return _result(source_document, layout_document, consumer)
    return _result(
        source_document,
        layout_document,
        consumer,
        SourceReferenceChange(consumer=consumer, new_ref_id=None),
    )


def delete_reference_definition(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    *,
    kind: ReferenceKind,
    ref_id: int,
) -> LayoutDocument:
    """Delete an unused definition only when source reference discovery is reliable.

    Source must come from parse_markdown() or an equivalently consistent snapshot.
    The checks neither reparse full text nor prove source/root provenance.
    """
    _require_instance(kind, ReferenceKind, "kind")
    _positive_ref_id(ref_id, "ref_id")
    _validate_reference_snapshot(source_document, layout_document, reference_index)
    _definition_value(layout_document, kind, ref_id)
    _require_reliable_reference_discovery(source_document)
    if reference_index.usages_for(ref_id):
        raise ValueError("Cannot delete a definition with a live global reference")
    field = _definition_field(kind)
    definitions = dict(getattr(layout_document, field))
    del definitions[ref_id]
    return replace(layout_document, **{field: definitions})


def _prepare_selection(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
) -> tuple[ReferenceKind, ReferenceValue | None]:
    _validate_reference_snapshot(source_document, layout_document, reference_index)
    kind = _consumer_kind(consumer)
    _consumer_depth(source_document, consumer)
    if consumer.config_ref is None:
        return kind, None
    value = _definition_value(layout_document, kind, consumer.config_ref)
    usages = tuple(
        usage
        for usage in reference_index.usages_for(consumer.config_ref)
        if usage.consumer is consumer
    )
    if len(usages) != 1 or usages[0].kind is not kind:
        raise ValueError("Selected consumer must have exactly one matching usage")
    return kind, value


def _consumer_kind(consumer: ReferenceConsumer) -> ReferenceKind:
    if isinstance(consumer, InlineFormat):
        if consumer.config_ref is None:
            raise ValueError("An InlineFormat consumer requires an existing reference")
        _positive_ref_id(consumer.config_ref, "consumer.config_ref")
        return ReferenceKind.INLINE_FORMAT
    if not isinstance(consumer, Block):
        raise TypeError("consumer must be a reference-capable block or InlineFormat")
    _optional_ref_id(consumer.config_ref, "consumer.config_ref")
    return ReferenceKind.CONFIGURATION


def _consumer_depth(
    source_document: SourceDocument, consumer: ReferenceConsumer
) -> int:
    matches = tuple(
        occurrence
        for occurrence in _collect_consumer_occurrences(source_document)
        if occurrence.consumer is consumer
    )
    if len(matches) != 1:
        raise ValueError("Selected consumer must occur exactly once in the source")
    return matches[0].block_depth


def _definition_value(
    layout_document: LayoutDocument, kind: ReferenceKind, ref_id: int
) -> ReferenceValue:
    configuration = layout_document.configurations.get(ref_id)
    inline_format = layout_document.inline_formats.get(ref_id)
    if configuration is not None and inline_format is not None:
        raise ValueError("Selected reference has duplicate global definitions")
    value = configuration if kind is ReferenceKind.CONFIGURATION else inline_format
    if value is None:
        raise ValueError("Selected reference has no unique definition of its kind")
    return value


def _apply_editor(
    editor: _Editor, base: ReferenceValue, kind: ReferenceKind
) -> ReferenceValue:
    edited = editor(base)
    expected = (
        Configuration
        if kind is ReferenceKind.CONFIGURATION
        else InlineFormatConfiguration
    )
    if not isinstance(edited, expected):
        raise TypeError(f"editor must return a {expected.__name__}")
    return edited


def _definition_field(kind: ReferenceKind) -> str:
    return "configurations" if kind is ReferenceKind.CONFIGURATION else "inline_formats"


def _store_definition(
    layout_document: LayoutDocument,
    kind: ReferenceKind,
    ref_id: int,
    value: ReferenceValue,
) -> LayoutDocument:
    field = _definition_field(kind)
    definitions = dict(getattr(layout_document, field))
    definitions[ref_id] = value
    return replace(layout_document, **{field: definitions})


def _next_reference_id(reference_index: ReferenceIndex) -> int:
    return max((*reference_index.definitions, *reference_index.usages), default=0) + 1


def _result(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    consumer: ReferenceConsumer,
    change: SourceReferenceChange | None = None,
) -> ReferenceEditResult:
    return ReferenceEditResult(
        source_document=source_document,
        layout_document=layout_document,
        selected_consumer=consumer,
        source_changes=() if change is None else (change,),
        selected_ref_id=consumer.config_ref if change is None else change.new_ref_id,
    )


def _validate_change_anchor(
    source_document: SourceDocument,
    change: SourceReferenceChange,
    block_depth: int,
) -> None:
    _require_source_change_context(change.consumer, block_depth)
    if not isinstance(source_document.text, str):
        raise TypeError("Source document text must be a string")
    consumer = change.consumer
    text = source_document.text
    if isinstance(consumer, InlineFormat):
        _validate_span_bounds(consumer.source_span, text)
        wrapper = text[
            consumer.source_span.start_offset : consumer.source_span.end_offset
        ]
        opening = _INLINE_FORMAT_OPEN.match(wrapper)
        if (
            opening is None
            or int(opening.group(1)) != change.old_ref_id
            or not wrapper.endswith(_INLINE_FORMAT_CLOSE)
        ):
            raise ValueError("Inline source anchor must match the existing ref wrapper")
        return
    _validate_span_bounds(consumer.source_binding.syntax_span, text)
    if change.old_ref_id is not None:
        marker = consumer.source_binding.config_marker_span
        _validate_span_bounds(marker, text)
        if text[marker.start_offset : marker.end_offset] != _format_config_ref_marker(
            change.old_ref_id
        ):
            raise ValueError("Block source anchor must match the existing ref marker")


def _require_source_change_context(
    consumer: ReferenceConsumer, block_depth: int
) -> None:
    if not isinstance(consumer, InlineFormat) and block_depth != 0:
        raise ValueError("Nested block reference source changes are unsupported")


def _validate_span_bounds(span: SourceSpan, text: str) -> None:
    if not isinstance(span, SourceSpan):
        raise TypeError("Source anchor must be a SourceSpan")
    if any(
        not isinstance(offset, int) or isinstance(offset, bool)
        for offset in (span.start_offset, span.end_offset)
    ):
        raise TypeError("Source anchor offsets must be integers")
    if not 0 <= span.start_offset <= span.end_offset <= len(text):
        raise ValueError("Source anchor offsets must be within the original text")


def _positive_ref_id(ref_id: int, name: str) -> None:
    if not isinstance(ref_id, int) or isinstance(ref_id, bool):
        raise TypeError(f"{name} must be an integer")
    if ref_id < 1:
        raise ValueError(f"{name} must be positive")


def _optional_ref_id(ref_id: int | None, name: str) -> None:
    if ref_id is not None:
        _positive_ref_id(ref_id, name)


def _require_instance(value: object, expected: type, name: str) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{name} must be a {expected.__name__}")


__all__ = [
    "ReferenceEditResult",
    "SourceReferenceChange",
    "allocate_reference_id",
    "delete_reference_definition",
    "detach_reference",
    "edit_consumer_locally",
    "edit_shared_definition",
    "set_consumer_reference",
]
