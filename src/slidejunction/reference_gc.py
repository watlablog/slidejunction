"""Explicit, snapshot-bound collection of unused reference definitions.

Source inputs must come from ``parse_markdown`` or preserve equivalent consistency
between text, semantic nodes, spans, and diagnostics. GC validates the reference
snapshot and discovery reliability; it does not reparse the source to prove them.
"""

from dataclasses import dataclass, field, replace

from .document import SourceDocument
from .layout import LayoutDocument
from .references import (
    ReferenceIndex,
    _require_reliable_reference_discovery,
    _validate_reference_snapshot,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceGCPlan:
    """A reliable dry-run plan tied to its original immutable snapshots.

    The source must be parser-produced or equivalently consistent as described
    above; construction validates discovery diagnostics, not root provenance.
    """

    source_document: SourceDocument
    layout_document: LayoutDocument
    reference_index: ReferenceIndex
    configuration_ids: tuple[int, ...] = field(init=False)
    inline_format_ids: tuple[int, ...] = field(init=False)

    def __post_init__(self) -> None:
        _validate_gc_inputs(
            self.source_document, self.layout_document, self.reference_index
        )
        live_ids = self.reference_index.usages.keys()
        object.__setattr__(
            self,
            "configuration_ids",
            tuple(sorted(self.layout_document.configurations.keys() - live_ids)),
        )
        object.__setattr__(
            self,
            "inline_format_ids",
            tuple(sorted(self.layout_document.inline_formats.keys() - live_ids)),
        )


def plan_reference_gc(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> ReferenceGCPlan:
    """Find unused definitions without changing source, layout, or live IDs.

    Requires a parse_markdown() result or an equivalently consistent snapshot.
    Source diagnostics gate discovery; source is not reparsed to prove provenance.
    """
    return ReferenceGCPlan(
        source_document=source_document,
        layout_document=layout_document,
        reference_index=reference_index,
    )


def apply_reference_gc(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    plan: ReferenceGCPlan,
) -> LayoutDocument:
    """Delete only planned definitions from the exact snapshots used to plan.

    Rechecks discovery reliability under the same consistent-source assumption as
    plan_reference_gc(), without reparsing source or proving root provenance.
    """
    if not isinstance(plan, ReferenceGCPlan):
        raise TypeError("plan must be a ReferenceGCPlan")
    _validate_gc_inputs(source_document, layout_document, reference_index)
    if (
        source_document is not plan.source_document
        or layout_document is not plan.layout_document
        or reference_index is not plan.reference_index
    ):
        raise ValueError("Reference GC plan does not match the input snapshots")
    if not plan.configuration_ids and not plan.inline_format_ids:
        return layout_document
    removed_configurations = set(plan.configuration_ids)
    removed_inline_formats = set(plan.inline_format_ids)
    return replace(
        layout_document,
        configurations={
            ref_id: value
            for ref_id, value in layout_document.configurations.items()
            if ref_id not in removed_configurations
        },
        inline_formats={
            ref_id: value
            for ref_id, value in layout_document.inline_formats.items()
            if ref_id not in removed_inline_formats
        },
    )


def _validate_gc_inputs(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> None:
    _validate_reference_snapshot(source_document, layout_document, reference_index)
    _require_reliable_reference_discovery(source_document)
    if any(len(group) > 1 for group in reference_index.definitions.values()):
        raise ValueError("Reference GC requires globally unambiguous definitions")


__all__ = ["ReferenceGCPlan", "apply_reference_gc", "plan_reference_gc"]
