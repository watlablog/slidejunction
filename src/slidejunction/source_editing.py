"""Apply one validated reference edit to exact Markdown source text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from ._reference_syntax import (
    _INLINE_FORMAT_CLOSE,
    _INLINE_FORMAT_OPEN,
    _format_config_ref_marker,
)
from .document import Block, InlineFormat, SourceBinding, SourceDocument, SourceSpan
from .markdown import parse_markdown
from .reference_editing import ReferenceEditResult, SourceReferenceChange
from .references import ReferenceKind

_OPERATIONS = frozenset(
    {
        "block-attach",
        "block-retarget",
        "block-detach",
        "inline-retarget",
        "inline-unwrap",
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class _TextEdit:
    """One replacement expressed in offsets from the original source."""

    start: int
    end: int
    replacement: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(offset, int) or isinstance(offset, bool)
            for offset in (self.start, self.end)
        ):
            raise TypeError("Text edit offsets must be integers")
        if self.start < 0 or self.start > self.end:
            raise ValueError("Text edit offsets must form a non-negative range")
        if not isinstance(self.replacement, str):
            raise TypeError("Text edit replacement must be a string")


def apply_reference_edit_to_source(
    edit_result: ReferenceEditResult,
) -> SourceDocument:
    """Apply an M6 source-change plan and freshly parse the resulting Markdown.

    A definition-only edit returns the original ``SourceDocument`` by identity.
    An actual source change patches only the validated original syntax ranges and
    reparses with the original logical path. This function performs no filesystem
    I/O and does not build a reference index or resolved presentation.
    """
    if not isinstance(edit_result, ReferenceEditResult):
        raise TypeError("edit_result must be a ReferenceEditResult")

    changes = edit_result.source_changes
    if changes == ():
        return edit_result.source_document
    if not isinstance(changes, tuple) or not all(
        isinstance(change, SourceReferenceChange) for change in changes
    ):
        raise TypeError("source_changes must be a tuple of SourceReferenceChange")
    if len(changes) != 1:
        raise ValueError("A source edit must contain exactly one source change")

    source_document = edit_result.source_document
    if not isinstance(source_document, SourceDocument):
        raise TypeError("Result source_document must be a SourceDocument")
    if not isinstance(source_document.text, str):
        raise TypeError("Source document text must be a string")

    change = changes[0]
    edits = _edits_for_change(edit_result, change, source_document.text)
    updated_text = _apply_text_edits(source_document.text, edits)
    return parse_markdown(updated_text, path=source_document.path)


def _edits_for_change(
    edit_result: ReferenceEditResult,
    change: SourceReferenceChange,
    text: str,
) -> tuple[_TextEdit, ...]:
    consumer = change.consumer
    if consumer is not edit_result.selected_consumer:
        raise ValueError("Source change must target the selected consumer identity")
    if change.new_ref_id != edit_result.selected_ref_id:
        raise ValueError("Selected ref must match the pending source change")

    if isinstance(consumer, InlineFormat):
        expected_kind = ReferenceKind.INLINE_FORMAT
        expected_span = consumer.source_span
    elif isinstance(consumer, Block):
        expected_kind = ReferenceKind.CONFIGURATION
        binding = consumer.source_binding
        if not isinstance(binding, SourceBinding):
            raise TypeError("Block source binding must be a SourceBinding")
        expected_span = (
            binding.syntax_span
            if consumer.config_ref is None
            else binding.config_marker_span
        )
    else:
        raise TypeError("Source change consumer has an unsupported type")

    if change.kind is not expected_kind:
        raise ValueError("Source change kind does not match its consumer")
    if change.old_ref_id != consumer.config_ref:
        raise ValueError("Source change old ref does not match its consumer")
    if change.source_span != expected_span:
        raise ValueError("Source change span does not match its consumer")

    old_ref_id = consumer.config_ref
    new_ref_id = change.new_ref_id
    _optional_positive_ref_id(old_ref_id, "old ref ID")
    _optional_positive_ref_id(new_ref_id, "new ref ID")
    expected_operation = _expected_operation(consumer, old_ref_id, new_ref_id)
    operation = change.operation
    if operation not in _OPERATIONS or operation != expected_operation:
        raise ValueError("Source change operation is unknown or inconsistent")

    if operation == "block-attach":
        return _block_attach_edits(consumer, new_ref_id, text)
    if operation == "block-retarget":
        return _block_retarget_edits(consumer, old_ref_id, new_ref_id, text)
    if operation == "block-detach":
        return _block_detach_edits(consumer, old_ref_id, text)
    if operation == "inline-retarget":
        return _inline_retarget_edits(consumer, old_ref_id, new_ref_id, text)
    if operation == "inline-unwrap":
        return _inline_unwrap_edits(consumer, old_ref_id, text)
    raise ValueError("Source change operation is unknown")  # pragma: no cover


def _expected_operation(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    new_ref_id: int | None,
) -> str:
    if isinstance(consumer, InlineFormat):
        if old_ref_id is None:
            raise ValueError("Inline source changes require an existing reference")
        return "inline-unwrap" if new_ref_id is None else "inline-retarget"
    if old_ref_id is None:
        if new_ref_id is None:
            raise ValueError("Block attach requires a new reference")
        return "block-attach"
    return "block-detach" if new_ref_id is None else "block-retarget"


def _block_attach_edits(
    consumer: Block | InlineFormat,
    new_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    block = _require_block(consumer)
    ref_id = _require_positive_ref_id(new_ref_id, "new ref ID")
    syntax_span = block.source_binding.syntax_span
    _validate_span(syntax_span, text)
    anchor = syntax_span.start_offset
    line_ending = (
        _line_ending_before(text, anchor)
        if anchor > 0
        else _first_line_ending(text, syntax_span.start_offset, syntax_span.end_offset)
        or _first_line_ending(text, 0, len(text))
        or "\n"
    )
    return (
        _TextEdit(
            start=anchor,
            end=anchor,
            replacement=_format_config_ref_marker(ref_id) + line_ending,
        ),
    )


def _block_retarget_edits(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    new_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    block = _require_block(consumer)
    old_id = _require_positive_ref_id(old_ref_id, "old ref ID")
    new_id = _require_positive_ref_id(new_ref_id, "new ref ID")
    marker = _block_marker_span(block)
    _require_exact_marker(text, marker, old_id)
    return (
        _TextEdit(
            start=marker.start_offset,
            end=marker.end_offset,
            replacement=_format_config_ref_marker(new_id),
        ),
    )


def _block_detach_edits(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    block = _require_block(consumer)
    old_id = _require_positive_ref_id(old_ref_id, "old ref ID")
    marker = _block_marker_span(block)
    _require_exact_marker(text, marker, old_id)
    syntax_span = block.source_binding.syntax_span
    _validate_span(syntax_span, text)
    line_ending = _line_ending_at(text, marker.end_offset)
    if (
        line_ending is None
        or marker.end_offset + len(line_ending) != syntax_span.start_offset
    ):
        raise ValueError("Block marker must be directly adjacent to its block")
    return (
        _TextEdit(
            start=marker.start_offset,
            end=marker.end_offset,
            replacement="",
        ),
    )


def _inline_retarget_edits(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    new_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    inline = _require_inline(consumer)
    old_id = _require_positive_ref_id(old_ref_id, "old ref ID")
    new_id = _require_positive_ref_id(new_ref_id, "new ref ID")
    span, opening, _ = _inline_wrapper_parts(inline, old_id, text)
    digit_start, digit_end = opening.span(1)
    return (
        _TextEdit(
            start=span.start_offset + digit_start,
            end=span.start_offset + digit_end,
            replacement=str(new_id),
        ),
    )


def _inline_unwrap_edits(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    inline = _require_inline(consumer)
    old_id = _require_positive_ref_id(old_ref_id, "old ref ID")
    span, opening, closing_start = _inline_wrapper_parts(inline, old_id, text)
    return (
        _TextEdit(
            start=span.start_offset,
            end=span.start_offset + opening.end(),
            replacement="",
        ),
        _TextEdit(
            start=span.start_offset + closing_start,
            end=span.end_offset,
            replacement="",
        ),
    )


def _block_marker_span(block: Block) -> SourceSpan:
    marker = block.source_binding.config_marker_span
    if not isinstance(marker, SourceSpan):
        raise TypeError("Block source change requires an existing marker span")
    return marker


def _require_exact_marker(text: str, marker: SourceSpan, ref_id: int) -> None:
    _validate_span(marker, text)
    if text[marker.start_offset : marker.end_offset] != _format_config_ref_marker(
        ref_id
    ):
        raise ValueError("Block source anchor must match the existing ref marker")


def _inline_wrapper_parts(
    inline: InlineFormat,
    old_ref_id: int,
    text: str,
) -> tuple[SourceSpan, re.Match[str], int]:
    span = inline.source_span
    _validate_span(span, text)
    wrapper = text[span.start_offset : span.end_offset]
    opening = _INLINE_FORMAT_OPEN.match(wrapper)
    closing_start = len(wrapper) - len(_INLINE_FORMAT_CLOSE)
    if (
        opening is None
        or int(opening.group(1)) != old_ref_id
        or closing_start < opening.end()
        or not wrapper.endswith(_INLINE_FORMAT_CLOSE)
    ):
        raise ValueError("Inline source anchor must match the existing ref wrapper")
    return span, opening, closing_start


def _apply_text_edits(text: str, edits: tuple[_TextEdit, ...]) -> str:
    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end))
    for edit in ordered:
        if edit.end > len(text):
            raise ValueError("Text edit offsets must be within the original source")
    for left, right in pairwise(ordered):
        if left.end > right.start:
            raise ValueError("Text edits must not overlap")

    updated = text
    for edit in reversed(ordered):
        updated = updated[: edit.start] + edit.replacement + updated[edit.end :]
    return updated


def _validate_span(span: SourceSpan, text: str) -> None:
    if not isinstance(span, SourceSpan):
        raise TypeError("Source edit anchor must be a SourceSpan")
    if any(
        not isinstance(offset, int) or isinstance(offset, bool)
        for offset in (span.start_offset, span.end_offset)
    ):
        raise TypeError("Source edit anchor offsets must be integers")
    if not 0 <= span.start_offset <= span.end_offset <= len(text):
        raise ValueError("Source edit anchor must be within the original text")


def _line_ending_before(text: str, anchor: int) -> str:
    if text[anchor - 1] == "\n":
        return "\r\n" if anchor >= 2 and text[anchor - 2] == "\r" else "\n"
    if text[anchor - 1] == "\r":
        if anchor < len(text) and text[anchor] == "\n":
            raise ValueError("Block attach anchor cannot split a CRLF line ending")
        return "\r"
    raise ValueError("Block attach anchor must be at a logical line start")


def _line_ending_at(text: str, offset: int) -> str | None:
    if text.startswith("\r\n", offset):
        return "\r\n"
    if offset < len(text) and text[offset] in {"\r", "\n"}:
        return text[offset]
    return None


def _first_line_ending(text: str, start: int, end: int) -> str | None:
    position = start
    while position < end:
        character = text[position]
        if character == "\r":
            if position + 1 < len(text) and text[position + 1] == "\n":
                if position + 1 < end:
                    return "\r\n"
                return None
            return "\r"
        if character == "\n" and (position == 0 or text[position - 1] != "\r"):
            return "\n"
        position += 1
    return None


def _require_block(consumer: Block | InlineFormat) -> Block:
    if isinstance(consumer, InlineFormat) or not isinstance(consumer, Block):
        raise TypeError("Block source operation requires a block consumer")
    return consumer


def _require_inline(consumer: Block | InlineFormat) -> InlineFormat:
    if not isinstance(consumer, InlineFormat):
        raise TypeError("Inline source operation requires an InlineFormat consumer")
    return consumer


def _require_positive_ref_id(ref_id: int | None, name: str) -> int:
    _optional_positive_ref_id(ref_id, name)
    if ref_id is None:
        raise ValueError(f"{name} is required")
    return ref_id


def _optional_positive_ref_id(ref_id: int | None, name: str) -> None:
    if ref_id is None:
        return
    if not isinstance(ref_id, int) or isinstance(ref_id, bool):
        raise TypeError(f"{name} must be an integer")
    if ref_id < 1:
        raise ValueError(f"{name} must be positive")


__all__ = ["apply_reference_edit_to_source"]
