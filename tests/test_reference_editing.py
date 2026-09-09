from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import _reference_syntax, markdown, reference_editing
from slidejunction.document import (
    BlockQuote,
    Diagnostic,
    DiagnosticSeverity,
    InlineCode,
    InlineFormat,
    InlineMath,
)
from slidejunction.image_editing import set_image_crop
from slidejunction.image_geometry import (
    ImageTargetBox,
    IntrinsicImageMetadata,
    NormalizedRect,
    resolve_image_geometry,
)
from slidejunction.layout import (
    Appearance,
    CodeConfig,
    Configuration,
    Crop,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    MediaFit,
    Placement,
    Size,
    Stacking,
    TextEffects,
    Theme,
    ThemePreset,
    Transform,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.reference_editing import (
    ReferenceEditResult,
    SourceReferenceChange,
    allocate_reference_id,
    delete_reference_definition,
    detach_reference,
    edit_consumer_locally,
    edit_shared_definition,
    set_consumer_reference,
)
from slidejunction.reference_gc import apply_reference_gc, plan_reference_gc
from slidejunction.references import ReferenceIndex, ReferenceKind, validate_references
from slidejunction.resolver import resolve_presentation

_OPERATIONS = (
    allocate_reference_id,
    edit_consumer_locally,
    edit_shared_definition,
    set_consumer_reference,
    detach_reference,
    delete_reference_definition,
)
_BLOCKING_SOURCE_CODES = (
    "invalid-config-ref-marker",
    "unused-config-ref",
    "unsupported-nested-config-ref",
    "unterminated-inline-format",
    "invalid-inline-format-tag",
    "unsupported-setext-heading",
    "unsupported-raw-html",
    "unterminated-inline-math",
    "unterminated-block-math",
    "future-reference-diagnostic",
)


def _layout(*, configurations=None, inline_formats=None):
    return LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _index(source, layout):
    return validate_references(source, layout).index


def _context(kind="block", count=1, ref_id=3, value=None):
    if kind == "block":
        marker = "" if ref_id is None else f"<!-- sj:ref={ref_id} -->\n"
        text = "\n\n".join(f"{marker}Item {i}" for i in range(count))
        value = Configuration() if value is None else value
        layout = _layout(configurations={} if ref_id is None else {ref_id: value})
    else:
        text = "\n\n".join(
            f"<sj-format ref={ref_id}>Item {i}</sj-format>" for i in range(count)
        )
        value = InlineFormatConfiguration() if value is None else value
        layout = _layout(inline_formats={ref_id: value})
    source = parse_markdown(text)
    block = source.presentation.items[0].blocks[0]
    consumer = block if kind == "block" else block.children[0]
    return source, layout, _index(source, layout), consumer


def _changed(value):
    if isinstance(value, Configuration):
        return replace(value, stacking=Stacking(z_index=7))
    return replace(value, typography=InlineTypography(font_size=24))


def _values(layout, kind):
    return layout.configurations if kind == "block" else layout.inline_formats


def _kind(kind):
    return (
        ReferenceKind.CONFIGURATION if kind == "block" else ReferenceKind.INLINE_FORMAT
    )


def _with_target(layout, kind, ref_id=8):
    if kind == "block":
        return replace(
            layout, configurations={**layout.configurations, ref_id: Configuration()}
        )
    return replace(
        layout,
        inline_formats={**layout.inline_formats, ref_id: InlineFormatConfiguration()},
    )


def _result(source, layout, consumer, *, changes=(), selected=None):
    return ReferenceEditResult(
        source_document=source,
        layout_document=layout,
        selected_consumer=consumer,
        source_changes=changes,
        selected_ref_id=selected,
    )


def _with_diagnostic(source, code, severity=DiagnosticSeverity.ERROR):
    span = source.presentation.items[0].source_span
    diagnostic = Diagnostic(
        code=code, severity=severity, message="fixture", source_span=span
    )
    return replace(
        source,
        presentation=replace(source.presentation, diagnostics=(diagnostic,)),
    )


def _with_consumer(source, consumer):
    slide = source.presentation.items[0]
    if isinstance(consumer, InlineFormat):
        block = replace(slide.blocks[0], children=(consumer,))
    else:
        block = consumer
    return replace(
        source,
        presentation=replace(
            source.presentation, items=(replace(slide, blocks=(block,)),)
        ),
    )


def _invoke(operation, source, layout, index, consumer):
    if operation is allocate_reference_id:
        return operation(source, layout, index)
    if operation is delete_reference_definition:
        return operation(
            source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=3
        )
    if operation in (edit_consumer_locally, edit_shared_definition):
        return operation(source, layout, index, consumer, editor=lambda value: value)
    if operation is set_consumer_reference:
        return operation(source, layout, index, consumer, ref_id=3)
    return operation(source, layout, index, consumer)


def test_public_exports_are_limited_to_the_editing_contract() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert set(reference_editing.__all__) == {
        "ReferenceEditResult",
        "SourceReferenceChange",
        *(operation.__name__ for operation in _OPERATIONS),
    }
    assert len(reference_editing.__all__) == 8


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
def test_equal_editor_result_is_identity_noop_before_fork(kind, count, operation):
    source, layout, index, consumer = _context(kind, count)
    calls = []

    def editor(value):
        calls.append(value)
        return replace(value)

    result = operation(source, layout, index, consumer, editor=editor)

    assert calls == [_values(layout, kind)[3]]
    assert calls[0] is _values(layout, kind)[3]
    assert result.source_document is source
    assert result.layout_document is layout
    assert result.selected_consumer is consumer
    assert result.selected_ref_id == 3
    assert result.source_changes == ()


def test_no_ref_equal_editor_result_keeps_empty_definition_unallocated():
    source, layout, index, consumer = _context(ref_id=None)
    calls = []

    def editor(value):
        calls.append(value)
        return Configuration()

    result = edit_consumer_locally(source, layout, index, consumer, editor=editor)

    assert calls == [Configuration()]
    assert result.layout_document is layout
    assert result.selected_ref_id is None
    assert result.source_changes == ()


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
def test_actual_editor_updates_single_or_forks_only_local_shared(
    kind, count, operation
):
    source, layout, index, consumer = _context(kind, count)
    original = _values(layout, kind)[3]
    replacement = _changed(original)
    calls = []

    def editor(value):
        calls.append(value)
        return replacement

    result = operation(source, layout, index, consumer, editor=editor)
    fork = operation is edit_consumer_locally and count == 2
    selected = 4 if fork else 3

    assert calls == [original]
    assert calls[0] is original
    assert result.layout_document is not layout
    assert result.layout_document.theme is layout.theme
    assert result.source_document is source
    assert result.selected_consumer is consumer
    assert result.selected_ref_id == selected
    assert _values(result.layout_document, kind)[selected] is replacement
    assert _values(layout, kind)[3] is original
    assert consumer.config_ref == 3
    assert index.consumer_count(3, _kind(kind)) == count
    if fork:
        assert _values(result.layout_document, kind)[3] is original
        assert len(result.source_changes) == 1
        change = result.source_changes[0]
        assert change.consumer is consumer
        assert change.old_ref_id == 3
        assert change.new_ref_id == 4
        assert change.operation == f"{kind}-retarget"
    else:
        assert result.source_changes == ()
        assert set(_values(result.layout_document, kind)) == {3}


def test_no_ref_actual_edit_adds_definition_and_marker_attach_plan():
    source, layout, index, consumer = _context(ref_id=None)
    replacement = Configuration(size=Size(width=40))
    result = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: replacement
    )

    assert result.selected_ref_id == 1
    assert result.layout_document.configurations[1] is replacement
    assert result.source_document is source
    assert consumer.config_ref is None
    assert not layout.configurations
    change = result.source_changes[0]
    assert change.old_ref_id is None
    assert change.new_ref_id == 1
    assert change.operation == "block-attach"
    assert change.source_span is consumer.source_binding.syntax_span


def test_local_fork_preserves_all_stored_sparse_properties_and_sibling_identities():
    original = Configuration(
        placement=Placement(x=10),
        size=Size(height=20),
        transform=Transform(rotation=30),
        appearance=Appearance(opacity=0.7),
        typography=Typography(font_size=29),
        text_effects=TextEffects(),
        media=ImageMedia(fit=MediaFit.CONTAIN, crop=Crop(x=10)),
        code=CodeConfig(),
    )
    source, layout, index, consumer = _context(count=2, value=original)
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    fork = result.layout_document.configurations[4]

    assert result.layout_document.configurations[3] is original
    for field in fields(original):
        if field.name != "stacking":
            assert getattr(fork, field.name) is getattr(original, field.name)
    assert fork.stacking == Stacking(z_index=7)


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
@pytest.mark.parametrize("wrong", [None, 4, "configuration", object()])
def test_editor_wrong_return_type_is_rejected_after_one_call(kind, operation, wrong):
    source, layout, index, consumer = _context(kind)
    calls = []

    def editor(value):
        calls.append(value)
        return wrong

    with pytest.raises(TypeError):
        operation(source, layout, index, consumer, editor=editor)
    assert len(calls) == 1
    assert _values(layout, kind)[3] is calls[0]


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_editor_cannot_cross_configuration_namespaces(kind):
    source, layout, index, consumer = _context(kind)
    wrong = InlineFormatConfiguration() if kind == "block" else Configuration()
    with pytest.raises(TypeError):
        edit_consumer_locally(
            source, layout, index, consumer, editor=lambda value: wrong
        )


@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
def test_editor_exception_is_propagated_once_without_partial_mutation(operation):
    source, layout, index, consumer = _context(count=2)
    failure = RuntimeError("editor failure")
    calls = []

    def editor(value):
        calls.append(value)
        raise failure

    with pytest.raises(RuntimeError) as error:
        operation(source, layout, index, consumer, editor=editor)
    assert error.value is failure
    assert len(calls) == 1
    assert set(layout.configurations) == {3}
    assert consumer.config_ref == 3


@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
@pytest.mark.parametrize("editor", [None, 1, Configuration()])
def test_editor_must_be_callable(operation, editor):
    source, layout, index, consumer = _context()
    with pytest.raises(TypeError):
        operation(source, layout, index, consumer, editor=editor)


@pytest.mark.parametrize("code", _BLOCKING_SOURCE_CODES)
@pytest.mark.parametrize("count,ref_id", [(1, None), (1, 3), (2, 3)])
def test_all_actual_local_branches_check_reliability_after_editor_noop(
    code, count, ref_id
):
    source, layout, _, consumer = _context(count=count, ref_id=ref_id)
    source = _with_diagnostic(source, code, DiagnosticSeverity.INFO)
    index = _index(source, layout)
    calls = []

    def editor(value):
        calls.append(value)
        return _changed(value)

    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=editor)
    assert len(calls) == 1

    noop = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: replace(value)
    )
    assert noop.layout_document is layout
    assert noop.selected_ref_id == ref_id
    assert noop.source_changes == ()


def test_hidden_unterminated_ref_blocks_even_single_local_edit_but_not_explicit_shared():
    source = parse_markdown("<!-- sj:ref=1 -->\nVisible <sj-format ref=8>hidden")
    layout = _layout(configurations={1: Configuration()})
    index = _index(source, layout)
    consumer = source.presentation.items[0].blocks[0]
    assert set(index.usages) == {1}
    assert [item.code for item in source.presentation.diagnostics] == [
        "unterminated-inline-format"
    ]

    with pytest.raises(ValueError):
        allocate_reference_id(source, layout, index)
    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    noop = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: value
    )
    assert noop.layout_document is layout
    assert noop.selected_ref_id == 1
    shared = edit_shared_definition(source, layout, index, consumer, editor=_changed)
    assert shared.selected_ref_id == 1
    assert shared.source_changes == ()
    assert shared.layout_document.configurations[1].stacking == Stacking(z_index=7)


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_explicit_shared_retarget_and_detach_do_not_use_discovery_gate(kind):
    source, layout, _, consumer = _context(kind)
    source = _with_diagnostic(source, "unknown-resource-code")
    layout = _with_target(layout, kind)
    index = _index(source, layout)

    shared = edit_shared_definition(source, layout, index, consumer, editor=_changed)
    retarget = set_consumer_reference(source, layout, index, consumer, ref_id=8)
    detached = detach_reference(source, layout, index, consumer)

    assert shared.selected_ref_id == 3
    assert retarget.selected_ref_id == 8
    assert detached.selected_ref_id is None
    assert retarget.layout_document is layout
    assert detached.layout_document is layout


@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_known_nonblocking_source_code_allows_edit_allocation_and_deletion(severity):
    source, layout, _, consumer = _context()
    source = _with_diagnostic(source, "unexpected-inline-format-close", severity)
    layout = _with_target(layout, "block")
    index = _index(source, layout)
    assert allocate_reference_id(source, layout, index) == 9
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.layout_document.configurations[3].stacking == Stacking(z_index=7)
    deleted = delete_reference_definition(
        source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=8
    )
    assert set(deleted.configurations) == {3}


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_set_reference_retargets_without_editing_or_deleting_definitions(kind):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    index = _index(source, layout)
    result = set_consumer_reference(source, layout, index, consumer, ref_id=8)

    assert result.source_document is source
    assert result.layout_document is layout
    assert result.selected_consumer is consumer
    assert result.selected_ref_id == 8
    assert consumer.config_ref == 3
    change = result.source_changes[0]
    assert change.kind is _kind(kind)
    assert change.old_ref_id == 3
    assert change.new_ref_id == 8
    assert change.operation == f"{kind}-retarget"
    expected_span = (
        consumer.source_binding.config_marker_span
        if kind == "block"
        else consumer.source_span
    )
    assert change.source_span is expected_span


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_same_reference_is_noop_and_detach_keeps_definition(kind):
    source, layout, index, consumer = _context(kind)
    noop = set_consumer_reference(source, layout, index, consumer, ref_id=3)
    assert noop.layout_document is layout
    assert noop.source_changes == ()
    assert noop.selected_ref_id == 3

    detached = detach_reference(source, layout, index, consumer)
    assert detached.layout_document is layout
    assert detached.source_document is source
    assert detached.selected_ref_id is None
    change = detached.source_changes[0]
    assert change.new_ref_id is None
    assert change.old_ref_id == 3
    assert change.operation == ("block-detach" if kind == "block" else "inline-unwrap")
    assert 3 in _values(detached.layout_document, kind)


def test_no_ref_attach_to_existing_definition_and_detach_noop():
    source, layout, _, consumer = _context(ref_id=None)
    layout = _with_target(layout, "block")
    index = _index(source, layout)
    attached = set_consumer_reference(source, layout, index, consumer, ref_id=8)
    assert attached.selected_ref_id == 8
    assert attached.layout_document is layout
    assert attached.source_changes[0].operation == "block-attach"
    detached = detach_reference(source, layout, index, consumer)
    assert detached.selected_ref_id is None
    assert detached.source_changes == ()
    assert detached.layout_document is layout
    with pytest.raises(ValueError):
        edit_shared_definition(source, layout, index, consumer, editor=_changed)


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("new_ref_id", [None, 8])
def test_change_and_result_models_are_frozen_slotted_and_keyword_only(kind, new_ref_id):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=new_ref_id)
    result = _result(source, layout, consumer, changes=(change,), selected=new_ref_id)

    assert [field.name for field in fields(change)] == ["consumer", "new_ref_id"]
    assert {field.name for field in fields(result)} == {
        "source_document",
        "layout_document",
        "selected_consumer",
        "source_changes",
        "selected_ref_id",
    }
    assert not hasattr(change, "__dict__")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        change.new_ref_id = 99
    with pytest.raises(FrozenInstanceError):
        result.selected_ref_id = 99
    with pytest.raises(TypeError):
        SourceReferenceChange(consumer, new_ref_id)
    with pytest.raises(TypeError):
        ReferenceEditResult(source, layout, consumer, (change,), new_ref_id)


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_change_rejects_old_equals_new(kind):
    _, _, _, consumer = _context(kind)
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=consumer, new_ref_id=3)


def test_change_rejects_no_ref_to_no_ref_and_marker_ref_inconsistency():
    _, _, _, consumer = _context(ref_id=None)
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=consumer, new_ref_id=None)
    ref_without_marker = replace(consumer, config_ref=3)
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=ref_without_marker, new_ref_id=8)
    marker_without_ref = replace(
        consumer,
        source_binding=replace(
            consumer.source_binding,
            config_marker_span=consumer.source_binding.syntax_span,
        ),
    )
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=marker_without_ref, new_ref_id=8)


@pytest.mark.parametrize(
    "value,error",
    [
        (True, TypeError),
        (False, TypeError),
        (1.0, TypeError),
        ("8", TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_change_and_set_reject_invalid_reference_ids(value, error):
    source, layout, index, consumer = _context()
    with pytest.raises(error):
        SourceReferenceChange(consumer=consumer, new_ref_id=value)
    with pytest.raises(error):
        set_consumer_reference(source, layout, index, consumer, ref_id=value)
    with pytest.raises(error):
        delete_reference_definition(
            source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=value
        )


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("new_ref_id,missing_id", [(None, 3), (8, 3), (8, 8)])
def test_result_requires_old_and_new_definitions_for_source_changes(
    kind, new_ref_id, missing_id
):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=new_ref_id)
    values = dict(_values(layout, kind))
    del values[missing_id]
    layout = replace(
        layout, **{"configurations" if kind == "block" else "inline_formats": values}
    )
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change,), selected=new_ref_id)


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("ref_id", [3, 8])
@pytest.mark.parametrize("wrong_kind_only", [False, True])
def test_result_rejects_wrong_kind_or_globally_duplicate_old_and_new_definitions(
    kind, ref_id, wrong_kind_only
):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=8)
    layout = _with_target(layout, "inline" if kind == "block" else "block", ref_id)
    if wrong_kind_only:
        values = dict(_values(layout, kind))
        del values[ref_id]
        layout = replace(
            layout,
            **{"configurations" if kind == "block" else "inline_formats": values},
        )
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change,), selected=8)


def test_result_selection_and_change_consumer_must_agree_by_identity():
    source, layout, _, consumer = _context(count=2)
    layout = _with_target(layout, "block")
    other = source.presentation.items[0].blocks[1]
    change = SourceReferenceChange(consumer=consumer, new_ref_id=8)
    with pytest.raises(ValueError):
        _result(source, layout, other, changes=(change,), selected=8)
    for selected in (None, 3, 99):
        with pytest.raises(ValueError):
            _result(source, layout, consumer, changes=(change,), selected=selected)
    for selected in (None, 8, 99):
        with pytest.raises(ValueError):
            _result(source, layout, consumer, selected=selected)
    with pytest.raises(ValueError):
        _result(source, layout, replace(consumer), selected=3)
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change, change), selected=8)


@pytest.mark.parametrize(
    "field,wrong",
    [
        ("source_document", None),
        ("layout_document", None),
        ("selected_consumer", object()),
        ("source_changes", []),
        ("source_changes", (object(),)),
        ("selected_ref_id", True),
        ("selected_ref_id", "3"),
    ],
)
def test_result_rejects_wrong_public_field_types(field, wrong):
    source, layout, _, consumer = _context()
    arguments = {
        "source_document": source,
        "layout_document": layout,
        "selected_consumer": consumer,
        "source_changes": (),
        "selected_ref_id": 3,
    }
    arguments[field] = wrong
    with pytest.raises(TypeError):
        ReferenceEditResult(**arguments)


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("new_ref_id", [None, 8])
def test_actual_source_slice_mismatch_is_rejected_with_matching_graph(kind, new_ref_id):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    source = replace(source, text="x" * len(source.text))
    index = _index(source, layout)
    assert index.usages[3][0].consumer is consumer
    change = SourceReferenceChange(consumer=consumer, new_ref_id=new_ref_id)
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change,), selected=new_ref_id)
    with pytest.raises(ValueError):
        if new_ref_id is None:
            detach_reference(source, layout, index, consumer)
        else:
            set_consumer_reference(source, layout, index, consumer, ref_id=new_ref_id)

    # A definition-only transaction does not require source syntax validation.
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.source_changes == ()
    assert result.selected_ref_id == 3


@pytest.mark.parametrize(
    "replacement",
    ["<!-- sj:ref=8 -->", "<!-- sj:ref=03 -->", "<!--sj:ref=3 -->", "<!-- sj:ref=3-->"],
)
def test_block_anchor_requires_exact_old_canonical_marker(replacement):
    source, layout, _, consumer = _context()
    marker = consumer.source_binding.config_marker_span
    text = replacement + source.text[marker.end_offset :]
    marker = replace(marker, end_offset=len(replacement), end_column=len(replacement))
    consumer = replace(
        consumer,
        source_binding=replace(consumer.source_binding, config_marker_span=marker),
    )
    source = replace(_with_consumer(source, consumer), text=text)
    index = _index(source, layout)
    with pytest.raises(ValueError):
        detach_reference(source, layout, index, consumer)


@pytest.mark.parametrize(
    "text",
    [
        "<sj-format ref=8>Item 0</sj-format>",
        "<sj-format ref='3'>Item 0</sj-format>",
        "<sj-format ref=03>Item 0</sj-format>",
        "<sj-format ref=3 >Item 0</sj-format>",
        "<sj-format ref=3>Item 0</sj-format >",
        "x<sj-format ref=3>Item 0</sj-format>",
        "<sj-format ref=3>Item 0</sj-format>x",
    ],
)
def test_inline_anchor_requires_valid_old_opener_and_exact_final_closer(text):
    source, layout, _, consumer = _context("inline")
    consumer = replace(
        consumer,
        source_span=replace(
            consumer.source_span, end_offset=len(text), end_column=len(text)
        ),
    )
    source = replace(_with_consumer(source, consumer), text=text)
    with pytest.raises(ValueError):
        detach_reference(source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize(
    "opening",
    [
        "<sj-format ref=3>",
        "<sj-format ref =3>",
        "<sj-format ref= 3>",
        "<sj-format ref \t=\t3>",
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        "",
        "日本語",
        "first\nsecond",
        "first\r\nsecond",
        "<sj-format ref=3>inner</sj-format>",
    ],
)
def test_inline_anchor_accepts_existing_horizontal_space_and_multiline_grammar(
    opening, body
):
    source = parse_markdown(f"{opening}{body}</sj-format>")
    consumer = source.presentation.items[0].blocks[0].children[0]
    layout = _layout(inline_formats={3: InlineFormatConfiguration()})
    result = detach_reference(source, layout, _index(source, layout), consumer)
    assert result.source_changes[0].operation == "inline-unwrap"
    assert result.selected_ref_id is None


@pytest.mark.parametrize("kind", ["attach", "block", "inline"])
@pytest.mark.parametrize("offset", ["start_offset", "end_offset"])
@pytest.mark.parametrize("invalid", [True, 10000])
def test_source_change_anchor_offsets_reject_bool_and_out_of_bounds(
    kind, offset, invalid
):
    source, layout, _, consumer = _context(
        "inline" if kind == "inline" else "block",
        ref_id=None if kind == "attach" else 3,
    )
    layout = _with_target(layout, "inline" if kind == "inline" else "block")
    span = (
        consumer.source_span
        if kind == "inline"
        else consumer.source_binding.syntax_span
        if kind == "attach"
        else consumer.source_binding.config_marker_span
    )
    # Keep SourceSpan's ordering constraints valid while forging an invalid anchor.
    updates = {offset: invalid}
    if offset == "start_offset" and invalid == 10000:
        updates["end_offset"] = 10001
    if offset == "end_offset" and invalid is True:
        updates["start_offset"] = 0
    span = replace(span, **updates)
    if kind == "inline":
        consumer = replace(consumer, source_span=span)
    else:
        field = "syntax_span" if kind == "attach" else "config_marker_span"
        consumer = replace(
            consumer, source_binding=replace(consumer.source_binding, **{field: span})
        )
    source = _with_consumer(source, consumer)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=8)
    with pytest.raises(TypeError if invalid is True else ValueError):
        _result(source, layout, consumer, changes=(change,), selected=8)


@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize("argument", ["source", "layout", "index"])
def test_all_operations_validate_snapshot_input_types(operation, argument):
    source, layout, index, consumer = _context()
    arguments = {"source": source, "layout": layout, "index": index}
    arguments[argument] = None
    with pytest.raises(TypeError):
        _invoke(operation, **arguments, consumer=consumer)


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_all_operations_reject_stale_index_definition_identity(operation):
    source, layout, index, consumer = _context()
    layout = replace(layout, configurations={3: replace(layout.configurations[3])})
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, index, consumer)


@pytest.mark.parametrize(
    "operation",
    [
        edit_consumer_locally,
        edit_shared_definition,
        set_consumer_reference,
        detach_reference,
    ],
)
def test_consumers_require_unique_identity_membership(operation):
    source, layout, index, consumer = _context()
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, index, replace(consumer))
    slide = source.presentation.items[0]
    source = replace(
        source,
        presentation=replace(
            source.presentation, items=(replace(slide, blocks=(consumer, consumer)),)
        ),
    )
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize("state", ["missing", "wrong-kind", "duplicate"])
@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize(
    "operation",
    [
        edit_consumer_locally,
        edit_shared_definition,
        set_consumer_reference,
        detach_reference,
    ],
)
def test_selected_invalid_graph_is_rejected_even_for_semantic_noop(
    state, kind, operation
):
    source, layout, _, consumer = _context(kind)
    if state in ("missing", "wrong-kind"):
        layout = _layout()
    if state in ("wrong-kind", "duplicate"):
        layout = _with_target(layout, "inline" if kind == "block" else "block", 3)
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "foreign"])
def test_index_usage_mismatch_is_rejected_before_editor(mutation):
    source, layout, index, consumer = _context()
    usage = index.usages[3][0]
    if mutation == "missing":
        usages = {}
    elif mutation == "extra":
        usages = {
            **index.usages,
            8: (replace(usage, ref_id=8, consumer=replace(consumer, config_ref=8)),),
        }
    elif mutation == "duplicate":
        usages = {3: (usage, usage)}
    else:
        usages = {3: (replace(usage, consumer=replace(consumer)),)}
    stale = ReferenceIndex(definitions=index.definitions, usages=usages)
    calls = []
    with pytest.raises(ValueError):
        edit_consumer_locally(
            source, layout, stale, consumer, editor=lambda value: calls.append(value)
        )
    assert calls == []


def test_definition_pointer_path_only_difference_is_allowed():
    source, layout, index, consumer = _context()
    definition = index.definitions[3][0]
    altered = replace(
        definition,
        config_pointer=replace(
            definition.config_pointer, path=Path("another/layout.json")
        ),
    )
    index = ReferenceIndex(definitions={3: (altered,)}, usages=index.usages)
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.selected_ref_id == 3


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_unrelated_invalid_graph_does_not_block_selected_edit_or_allocator(kind):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(_with_target(layout, "block", 8), "inline", 8)
    index = _index(source, layout)
    assert len(index.definitions[8]) == 2
    assert allocate_reference_id(source, layout, index) == 9
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.selected_ref_id == 3
    assert result.layout_document.configurations[8] is layout.configurations[8]
    assert result.layout_document.inline_formats[8] is layout.inline_formats[8]


@pytest.mark.parametrize("consumer_type", [InlineCode, InlineMath])
def test_inline_code_and_math_are_not_editable_reference_consumers(consumer_type):
    source, layout, index, consumer = _context()
    span = consumer.source_binding.syntax_span
    invalid = consumer_type(
        **{"code" if consumer_type is InlineCode else "content": "x"}, source_span=span
    )
    with pytest.raises(TypeError):
        SourceReferenceChange(consumer=invalid, new_ref_id=8)
    for operation in (
        edit_consumer_locally,
        edit_shared_definition,
        set_consumer_reference,
        detach_reference,
    ):
        with pytest.raises(TypeError):
            _invoke(operation, source, layout, index, invalid)


def test_programmatic_no_ref_inline_format_is_rejected():
    source, layout, _, consumer = _context("inline")
    consumer = replace(consumer, config_ref=None)
    source = _with_consumer(source, consumer)
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=consumer, new_ref_id=8)
    # A plain index is enough to assert the unsupported consumer is rejected.
    index = ReferenceIndex(definitions={}, usages={})
    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=_changed)


@pytest.mark.parametrize("text", ["> nested", "- nested"])
def test_nested_no_ref_block_allows_noop_but_rejects_source_changes(text):
    source = parse_markdown(text)
    outer = source.presentation.items[0].blocks[0]
    consumer = (
        outer.blocks[0] if isinstance(outer, BlockQuote) else outer.items[0].blocks[0]
    )
    layout = _layout(configurations={8: Configuration()})
    index = _index(source, layout)
    noop = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: value
    )
    assert noop.layout_document is layout
    assert noop.selected_ref_id is None
    assert detach_reference(source, layout, index, consumer).source_changes == ()
    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    with pytest.raises(ValueError):
        set_consumer_reference(source, layout, index, consumer, ref_id=8)


def test_programmatic_nested_ref_allows_definition_edit_but_rejects_retarget_detach():
    source = parse_markdown("> nested")
    slide = source.presentation.items[0]
    outer = slide.blocks[0]
    consumer = replace(
        outer.blocks[0],
        config_ref=3,
        source_binding=replace(
            outer.blocks[0].source_binding,
            config_marker_span=outer.blocks[0].source_binding.syntax_span,
        ),
    )
    outer = replace(outer, blocks=(consumer,))
    source = replace(
        source,
        presentation=replace(
            source.presentation, items=(replace(slide, blocks=(outer,)),)
        ),
    )
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    index = _index(source, layout)
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.source_changes == ()
    assert result.selected_ref_id == 3
    assert (
        set_consumer_reference(source, layout, index, consumer, ref_id=3).source_changes
        == ()
    )
    with pytest.raises(ValueError):
        set_consumer_reference(source, layout, index, consumer, ref_id=8)
    with pytest.raises(ValueError):
        detach_reference(source, layout, index, consumer)


@pytest.mark.parametrize(
    "text", ["> <sj-format ref=3>a</sj-format>", "- <sj-format ref=3>a</sj-format>"]
)
def test_nested_inline_format_remains_retargetable(text):
    source = parse_markdown(text)
    layout = _layout(
        inline_formats={3: InlineFormatConfiguration(), 8: InlineFormatConfiguration()}
    )
    index = _index(source, layout)
    consumer = index.usages[3][0].consumer
    result = set_consumer_reference(source, layout, index, consumer, ref_id=8)
    assert result.selected_ref_id == 8
    assert result.source_changes[0].operation == "inline-retarget"


@pytest.mark.parametrize(
    "source_text,configuration_ids,inline_ids,expected",
    [
        ("", (), (), 1),
        ("", (1, 8), (3,), 9),
        ("<!-- sj:ref=20 -->\nMissing", (1, 8), (3,), 21),
        ("<sj-format ref=30>missing</sj-format>", (20,), (2,), 31),
        ("", (3,), (3,), 4),
    ],
)
def test_allocator_uses_global_max_including_dangling_usages_and_never_fills_gaps(
    source_text, configuration_ids, inline_ids, expected
):
    source = parse_markdown(source_text)
    layout = _layout(
        configurations={key: Configuration() for key in configuration_ids},
        inline_formats={key: InlineFormatConfiguration() for key in inline_ids},
    )
    index = _index(source, layout)
    assert allocate_reference_id(source, layout, index) == expected
    assert allocate_reference_id(source, layout, index) == expected
    assert tuple(layout.configurations) == configuration_ids
    assert tuple(layout.inline_formats) == inline_ids


@pytest.mark.parametrize("code", _BLOCKING_SOURCE_CODES)
def test_allocator_and_definition_deletion_reject_unsafe_source_discovery(code):
    source, layout, _, _ = _context()
    source = _with_diagnostic(source, code)
    layout = _with_target(layout, "block")
    index = _index(source, layout)
    with pytest.raises(ValueError):
        allocate_reference_id(source, layout, index)
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=8
        )


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_delete_unused_definition_preserves_other_ids_and_identity(kind):
    source, layout, _, _ = _context(kind)
    layout = _with_target(layout, kind)
    layout = _with_target(layout, kind, 20)
    index = _index(source, layout)
    result = delete_reference_definition(
        source, layout, index, kind=_kind(kind), ref_id=8
    )
    assert result is not layout
    assert set(_values(result, kind)) == {3, 20}
    assert _values(result, kind)[3] is _values(layout, kind)[3]
    assert _values(result, kind)[20] is _values(layout, kind)[20]
    assert result.theme is layout.theme
    assert set(_values(layout, kind)) == {3, 8, 20}


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("wrong_kind", [False, True])
def test_any_live_global_usage_prevents_definition_deletion(kind, count, wrong_kind):
    source, layout, _, _ = _context(kind, count)
    if wrong_kind:
        layout = _with_target(_layout(), "inline" if kind == "block" else "block", 3)
    delete_kind = (
        _kind("inline" if kind == "block" else "block") if wrong_kind else _kind(kind)
    )
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, _index(source, layout), kind=delete_kind, ref_id=3
        )


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_missing_or_globally_duplicate_definition_cannot_be_deleted(kind):
    source = parse_markdown("")
    layout = _layout()
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, _index(source, layout), kind=_kind(kind), ref_id=3
        )
    layout = _with_target(_with_target(layout, "block", 3), "inline", 3)
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, _index(source, layout), kind=_kind(kind), ref_id=3
        )


@pytest.mark.parametrize("kind", [None, "configuration", 1])
def test_deletion_requires_reference_kind_enum(kind):
    source, layout, index, _ = _context()
    with pytest.raises(TypeError):
        delete_reference_definition(source, layout, index, kind=kind, ref_id=3)


@pytest.mark.parametrize("count,ref_id", [(2, 3), (1, 3), (1, None)])
def test_m5b_image_crop_transaction_integrates_with_m3_m4_and_geometry(count, ref_id):
    marker = "" if ref_id is None else "<!-- sj:ref=3 -->\n"
    original_text = "\n\n".join(
        f"{marker}![image {i}](image{i}.png)" for i in range(count)
    )
    source = parse_markdown(original_text)
    original = Configuration(
        size=Size(width=40),
        typography=Typography(font_size=27),
        code=CodeConfig(),
        media=ImageMedia(fit=MediaFit.COVER),
    )
    layout = _layout(configurations={} if ref_id is None else {3: original})
    index = _index(source, layout)
    resolved = resolve_presentation(source, layout, index)
    image = resolved.items[0].blocks[0]
    consumer = source.presentation.items[0].blocks[0]
    requested = NormalizedRect(x=0.1, y=0.2, width=0.5, height=0.6)
    result = edit_consumer_locally(
        source,
        layout,
        index,
        consumer,
        editor=lambda local: set_image_crop(local, image, requested),
    )
    selected_id = 4 if count == 2 else 1 if ref_id is None else 3
    assert result.selected_ref_id == selected_id
    assert result.source_document is source
    assert source.text == original_text
    updated = result.layout_document.configurations[selected_id]
    assert updated.media.crop == Crop(x=10, y=20, width=50, height=60)
    if ref_id is not None:
        assert updated.typography is original.typography
        assert updated.code is original.code
        assert updated.size is original.size
    if count == 2:
        assert result.layout_document.configurations[3] is original
        expected_text = "<!-- sj:ref=4 -->\n![image 0](image0.png)\n\n<!-- sj:ref=3 -->\n![image 1](image1.png)"
    elif ref_id is None:
        expected_text = "<!-- sj:ref=1 -->\n![image 0](image0.png)"
    else:
        expected_text = original_text
        assert result.source_changes == ()
    # The fixture supplies explicit future source text; production never writes it.
    fresh_source = parse_markdown(expected_text)
    fresh_index = _index(fresh_source, result.layout_document)
    fresh = resolve_presentation(fresh_source, result.layout_document, fresh_index)
    geometry = resolve_image_geometry(
        fresh.items[0].blocks[0],
        IntrinsicImageMetadata(width=4, height=3),
        ImageTargetBox(width=4, height=3),
    )
    assert geometry.source_crop == requested
    if count == 2:
        assert fresh_source.presentation.items[0].blocks[1].config_ref == 3
        assert fresh.items[0].blocks[1].configuration.media.crop is None


def test_repeated_edit_is_deterministic_without_io_diagnostics_or_reparse(monkeypatch):
    source, layout, index, consumer = _context(count=2)

    def forbidden(*args, **kwargs):
        raise AssertionError("An in-memory transaction must not do I/O or reparse")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr("slidejunction.markdown.parse_markdown", forbidden)
    monkeypatch.setattr(Diagnostic, "__post_init__", forbidden)
    first = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    second = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert first == second
    assert first is not second
    assert first.layout_document is not second.layout_document
    assert first.source_document is second.source_document is source
    assert index.usages[3][0].consumer is consumer
    assert set(layout.configurations) == {3}


@pytest.mark.parametrize("ref_id,count", [(None, 1), (3, 2)])
def test_real_unused_marker_prevents_hidden_id_collision_on_attach_or_fork(
    ref_id, count
):
    source, layout, _, consumer = _context(ref_id=ref_id, count=count)
    layout = replace(layout, configurations={3: Configuration()})
    source = parse_markdown(source.text + "\n\n<!-- sj:ref=4 -->\n")
    consumer = source.presentation.items[0].blocks[0]
    index = _index(source, layout)
    assert set(index.definitions) == {3}
    assert 4 not in index.usages
    assert [item.code for item in source.presentation.diagnostics] == [
        "unused-config-ref"
    ]
    calls = []

    def editor(value):
        calls.append(value)
        return _changed(value)

    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=editor)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        allocate_reference_id(source, layout, index)
    noop = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: replace(value)
    )
    assert noop.layout_document is layout
    assert noop.source_changes == ()
    assert noop.selected_ref_id == ref_id


@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_unknown_discovery_code_rejects_local_allocation_and_delete_at_every_severity(
    severity,
):
    source, layout, _, consumer = _context()
    source = _with_diagnostic(source, "future-resource-diagnostic", severity)
    layout = _with_target(layout, "block")
    index = _index(source, layout)
    with pytest.raises(ValueError):
        allocate_reference_id(source, layout, index)
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=8
        )
    calls = []

    def editor(value):
        calls.append(value)
        return _changed(value)

    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=editor)
    assert len(calls) == 1


@pytest.mark.parametrize("kind,after_text", [("block", "Item 0"), ("inline", "Item 0")])
def test_detach_then_explicit_reparse_then_gc_deletes_retained_definition(
    kind, after_text
):
    source, layout, index, consumer = _context(kind)
    detached = detach_reference(source, layout, index, consumer)
    assert detached.layout_document is layout
    assert _values(detached.layout_document, kind)[3] is _values(layout, kind)[3]
    assert detached.selected_ref_id is None
    # Only this explicitly supplied fixture text simulates future writer output.
    after = parse_markdown(after_text)
    fresh_index = _index(after, detached.layout_document)
    plan = plan_reference_gc(after, detached.layout_document, fresh_index)
    assert plan.configuration_ids == ((3,) if kind == "block" else ())
    assert plan.inline_format_ids == ((3,) if kind == "inline" else ())
    collected = apply_reference_gc(after, detached.layout_document, fresh_index, plan)
    assert not _values(collected, kind)
    assert collected.theme is layout.theme
    assert 3 in _values(layout, kind)
    assert source.text != after.text


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_opposite_kind_usage_of_same_id_does_not_inflate_local_sharing(kind):
    source = parse_markdown(
        "<!-- sj:ref=3 -->\nBlock\n\n<sj-format ref=3>Inline</sj-format>"
    )
    layout = _with_target(_layout(), kind, 3)
    index = _index(source, layout)
    consumer = next(
        usage.consumer for usage in index.usages[3] if usage.kind is _kind(kind)
    )
    assert len(index.usages[3]) == 2
    assert index.consumer_count(3, _kind(kind)) == 1
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.selected_ref_id == 3
    assert result.source_changes == ()
    assert set(_values(result.layout_document, kind)) == {3}


@pytest.mark.parametrize("invalid", [True, 10000])
def test_block_change_validates_syntax_span_even_with_exact_valid_marker(invalid):
    source, layout, _, consumer = _context()
    span = replace(
        consumer.source_binding.syntax_span,
        end_offset=invalid,
        start_offset=0
        if invalid is True
        else consumer.source_binding.syntax_span.start_offset,
    )
    consumer = replace(
        consumer, source_binding=replace(consumer.source_binding, syntax_span=span)
    )
    source = _with_consumer(source, consumer)
    with pytest.raises(TypeError if invalid is True else ValueError):
        detach_reference(source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_foreign_source_with_equal_semantics_is_rejected_by_index_membership(operation):
    source, layout, index, _ = _context()
    source = parse_markdown(source.text)
    consumer = source.presentation.items[0].blocks[0]
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, index, consumer)


@pytest.mark.parametrize("target_state", ["missing", "wrong-kind", "duplicate"])
def test_result_attach_requires_unique_correct_kind_new_definition(target_state):
    source, layout, _, consumer = _context(ref_id=None)
    if target_state == "duplicate":
        layout = _with_target(layout, "block")
    if target_state in ("wrong-kind", "duplicate"):
        layout = _with_target(layout, "inline")
    change = SourceReferenceChange(consumer=consumer, new_ref_id=8)
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change,), selected=8)


def test_no_ref_noop_result_cannot_claim_an_existing_selection_id():
    source, layout, _, consumer = _context(ref_id=None)
    layout = _with_target(layout, "block")
    with pytest.raises(ValueError):
        _result(source, layout, consumer, selected=8)


def test_parser_and_anchor_validation_share_canonical_block_syntax():
    assert markdown._VALID_CONFIG_REF is _reference_syntax._VALID_CONFIG_REF
    assert (
        reference_editing._format_config_ref_marker
        is _reference_syntax._format_config_ref_marker
    )
    marker = _reference_syntax._format_config_ref_marker(37)
    assert marker == "<!-- sj:ref=37 -->"
    assert _reference_syntax._VALID_CONFIG_REF.fullmatch(marker).group(1) == "37"
    source = parse_markdown(marker + "\nBody")
    consumer = source.presentation.items[0].blocks[0]
    layout = _layout(configurations={37: Configuration()})
    assert consumer.config_ref == 37
    assert source.presentation.diagnostics == ()
    result = detach_reference(source, layout, _index(source, layout), consumer)
    assert result.source_changes[0].operation == "block-detach"


@pytest.mark.parametrize(
    "marker", ["<!--sj:ref=3 -->", "<!-- sj:ref=03 -->", "<!-- sj:ref=3-->"]
)
def test_malformed_block_syntax_is_rejected_by_parser_and_anchor_validator(marker):
    malformed = parse_markdown(marker + "\nBody")
    assert [diagnostic.code for diagnostic in malformed.presentation.diagnostics] == [
        "invalid-config-ref-marker"
    ]
    assert _reference_syntax._VALID_CONFIG_REF.fullmatch(marker) is None

    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    consumer = source.presentation.items[0].blocks[0]
    binding = consumer.source_binding
    binding = replace(
        binding,
        config_marker_span=replace(
            binding.config_marker_span, end_offset=len(marker), end_column=len(marker)
        ),
        syntax_span=replace(
            binding.syntax_span,
            start_offset=len(marker) + 1,
            end_offset=len(marker) + 5,
        ),
    )
    consumer = replace(consumer, source_binding=binding)
    source = replace(_with_consumer(source, consumer), text=marker + "\nBody")
    layout = _layout(configurations={3: Configuration()})
    with pytest.raises(ValueError):
        detach_reference(source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize(
    "body,type_name",
    [
        ("### Heading", "Heading"),
        ("Paragraph", "Paragraph"),
        ("- Item", "ListBlock"),
        ("> Quote", "BlockQuote"),
        ("```python\nx\n```", "CodeBlock"),
        ("![alt](image.png)", "ImageBlock"),
        ("***", "ThematicBreak"),
        ("\\[\nx\n\\]", "MathBlock"),
    ],
)
def test_all_eight_block_types_support_existing_marker_changes(body, type_name):
    source = parse_markdown("<!-- sj:ref=3 -->\n" + body)
    consumer = source.presentation.items[0].blocks[0]
    assert type(consumer).__name__ == type_name
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), consumer, ref_id=8
    )
    assert result.selected_ref_id == 8
    assert result.source_changes[0].operation == "block-retarget"


@pytest.mark.parametrize("level", [1, 2])
def test_section_and_slide_title_are_top_level_attach_consumers(level):
    source = parse_markdown("#" * level + " Title")
    item = source.presentation.items[0]
    consumer = item.title_slide.title if level == 1 else item.title
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), consumer, ref_id=8
    )
    assert result.selected_ref_id == 8
    assert result.source_changes[0].operation == "block-attach"
