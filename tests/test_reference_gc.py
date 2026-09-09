from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import reference_gc
from slidejunction.document import Diagnostic, DiagnosticSeverity, SourceSpan
from slidejunction.layout import (
    Configuration,
    InlineFormatConfiguration,
    LayoutDocument,
    Stacking,
    Theme,
    ThemePreset,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.reference_gc import (
    ReferenceGCPlan,
    apply_reference_gc,
    plan_reference_gc,
)
from slidejunction.references import ReferenceIndex, validate_references

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
)


def _state(source="", *, configurations=None, inline_formats=None):
    source_document = parse_markdown(source)
    layout_document = LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )
    reference_index = validate_references(source_document, layout_document).index
    return source_document, layout_document, reference_index


def _with_diagnostic(source, code, severity):
    diagnostic = Diagnostic(
        severity=severity,
        code=code,
        message="Test source reliability",
        source_span=SourceSpan(
            start_offset=0,
            end_offset=0,
            start_line=0,
            end_line=0,
            start_column=0,
            end_column=0,
        ),
    )
    return replace(
        source,
        presentation=replace(source.presentation, diagnostics=(diagnostic,)),
    )


def test_public_surface() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert reference_gc.__all__ == [
        "ReferenceGCPlan",
        "apply_reference_gc",
        "plan_reference_gc",
    ]


def test_plan_is_frozen_slotted_keyword_only_and_derives_candidate_fields() -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    plan = ReferenceGCPlan(
        source_document=source, layout_document=layout, reference_index=index
    )
    assert plan.source_document is source
    assert plan.layout_document is layout
    assert plan.reference_index is index
    assert plan.configuration_ids == (8,)
    assert plan.inline_format_ids == ()
    assert {field.name for field in fields(plan) if not field.init} == {
        "configuration_ids",
        "inline_format_ids",
    }
    assert not hasattr(plan, "__dict__")
    with pytest.raises(FrozenInstanceError):
        plan.configuration_ids = ()
    with pytest.raises(TypeError):
        ReferenceGCPlan(source, layout, index)
    with pytest.raises(TypeError):
        ReferenceGCPlan(
            source_document=source,
            layout_document=layout,
            reference_index=index,
            configuration_ids=(1,),
        )


@pytest.mark.parametrize(
    ("source", "config_ids", "inline_ids", "expected_config", "expected_inline"),
    [
        ("", (), (), (), ()),
        ("", (8,), (), (8,), ()),
        ("", (), (8,), (), (8,)),
        ("<!-- sj:ref=8 -->\nLive", (8,), (), (), ()),
        ("<sj-format ref=8>Live</sj-format>", (), (8,), (), ()),
        ("", (50, 3, 10), (6, 1, 20), (3, 10, 50), (1, 6, 20)),
        (
            "<!-- sj:ref=8 -->\n<sj-format ref=3>Live</sj-format>",
            (50, 8, 1),
            (20, 3, 2),
            (1, 50),
            (2, 20),
        ),
        ("", (10**400, 1), (), (1, 10**400), ()),
    ],
)
def test_dry_run_candidates_are_numeric_sorted_and_kind_specific(
    source, config_ids, inline_ids, expected_config, expected_inline
) -> None:
    state = _state(
        source,
        configurations={ref_id: Configuration() for ref_id in config_ids},
        inline_formats={ref_id: InlineFormatConfiguration() for ref_id in inline_ids},
    )
    source_document, layout, index = state
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == expected_config
    assert plan.inline_format_ids == expected_inline
    assert plan_reference_gc(*state) == plan
    assert set(layout.configurations) == set(config_ids)
    assert set(layout.inline_formats) == set(inline_ids)
    assert source_document.text == source
    assert plan.reference_index is index


@pytest.mark.parametrize(
    ("source", "configurations", "inline_formats"),
    [
        ("<!-- sj:ref=8 -->\nWrong kind", {}, {8: InlineFormatConfiguration()}),
        ("<sj-format ref=8>Wrong kind</sj-format>", {8: Configuration()}, {}),
    ],
)
def test_wrong_kind_usage_keeps_definition_live_in_global_namespace(
    source, configurations, inline_formats
) -> None:
    state = _state(source, configurations=configurations, inline_formats=inline_formats)
    document, layout, _ = state
    assert "ref-kind-mismatch" in {
        diagnostic.code
        for diagnostic in validate_references(document, layout).diagnostics
    }
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == ()
    assert plan.inline_format_ids == ()
    assert apply_reference_gc(*state, plan) is layout


@pytest.mark.parametrize(
    "source",
    ["<!-- sj:ref=99 -->\nMissing", "<sj-format ref=99>Missing</sj-format>"],
)
def test_missing_references_do_not_hide_unrelated_unused_definitions(source) -> None:
    state = _state(source, configurations={8: Configuration()})
    document, layout, index = state
    assert any(
        diagnostic.code.startswith("missing-")
        for diagnostic in validate_references(document, layout).diagnostics
    )
    assert 99 in index.usages
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == (8,)
    assert apply_reference_gc(*state, plan).configurations == {}


@pytest.mark.parametrize("source", ["", "<!-- sj:ref=8 -->\nLive"])
def test_global_duplicate_definitions_block_plan_even_when_unused(source) -> None:
    state = _state(
        source,
        configurations={8: Configuration()},
        inline_formats={8: InlineFormatConfiguration()},
    )
    with pytest.raises(ValueError, match="unambiguous"):
        plan_reference_gc(*state)
    with pytest.raises(ValueError, match="unambiguous"):
        ReferenceGCPlan(
            source_document=state[0], layout_document=state[1], reference_index=state[2]
        )


@pytest.mark.parametrize("code", _BLOCKING_SOURCE_CODES)
@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_source_recovery_diagnostic_blocks_independent_of_severity(
    code, severity
) -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    source = _with_diagnostic(source, code, severity)
    with pytest.raises(ValueError):
        plan_reference_gc(source, layout, index)


@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_unexpected_inline_close_is_the_explicit_nonblocking_source_diagnostic(
    severity,
) -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    source = _with_diagnostic(source, "unexpected-inline-format-close", severity)
    plan = plan_reference_gc(source, layout, index)
    assert plan.configuration_ids == (8,)
    assert apply_reference_gc(source, layout, index, plan).configurations == {}


@pytest.mark.parametrize(
    "code", ["future-markdown-recovery", "", "unknown-resource-error"]
)
@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_unknown_source_diagnostic_fails_closed_at_every_severity(
    code, severity
) -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    source = _with_diagnostic(source, code, severity)
    with pytest.raises(ValueError):
        plan_reference_gc(source, layout, index)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("<!-- sj:ref=8 -->", "unused-config-ref"),
        ("<!-- sj:ref=0 -->\nText", "invalid-config-ref-marker"),
        ("<sj-format ref=8>Text", "unterminated-inline-format"),
        ("> <!-- sj:ref=8 -->\n> Text", "unsupported-nested-config-ref"),
    ],
)
def test_real_parser_recovery_prevents_gc(text, code) -> None:
    state = _state(text, configurations={8: Configuration()})
    assert code in {diagnostic.code for diagnostic in state[0].presentation.diagnostics}
    with pytest.raises(ValueError):
        plan_reference_gc(*state)


def test_real_unexpected_inline_close_does_not_prevent_gc() -> None:
    state = _state("Text </sj-format>", configurations={8: Configuration()})
    assert {diagnostic.code for diagnostic in state[0].presentation.diagnostics} == {
        "unexpected-inline-format-close"
    }
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == (8,)
    assert apply_reference_gc(*state, plan).configurations == {}


@pytest.mark.parametrize(
    "argument", ["source_document", "layout_document", "reference_index"]
)
@pytest.mark.parametrize("value", [None, {}, 1])
def test_plan_and_apply_validate_runtime_input_types(argument, value) -> None:
    state = _state()
    plan = plan_reference_gc(*state)
    kwargs = dict(zip(("source_document", "layout_document", "reference_index"), state))
    kwargs[argument] = value
    with pytest.raises(TypeError):
        plan_reference_gc(**kwargs)
    with pytest.raises(TypeError):
        ReferenceGCPlan(**kwargs)
    with pytest.raises(TypeError):
        apply_reference_gc(**kwargs, plan=plan)


@pytest.mark.parametrize("plan", [None, {}, 1])
def test_apply_rejects_wrong_plan_type(plan) -> None:
    with pytest.raises(TypeError):
        apply_reference_gc(*_state(), plan)


@pytest.mark.parametrize(
    "alteration", ["missing-definition", "missing-usage", "extra-definition"]
)
def test_stale_index_is_rejected_before_dry_run(alteration) -> None:
    source, layout, index = _state(
        "<!-- sj:ref=8 -->\nLive", configurations={8: Configuration()}
    )
    if alteration == "missing-definition":
        index = replace(index, definitions={})
    elif alteration == "missing-usage":
        index = replace(index, usages={})
    else:
        extra_layout = replace(
            layout, configurations={**layout.configurations, 9: Configuration()}
        )
        index = validate_references(source, extra_layout).index
    with pytest.raises(ValueError):
        plan_reference_gc(source, layout, index)


@pytest.mark.parametrize("foreign", ["source", "definition-value"])
def test_foreign_value_or_consumer_identity_is_rejected(foreign) -> None:
    source, layout, index = _state(
        "<!-- sj:ref=8 -->\nLive", configurations={8: Configuration()}
    )
    if foreign == "source":
        source = parse_markdown(source.text)
    else:
        layout = replace(layout, configurations={8: Configuration()})
    with pytest.raises(ValueError):
        plan_reference_gc(source, layout, index)


def test_definition_pointer_provenance_path_is_accepted() -> None:
    source, layout, _ = _state(configurations={8: Configuration()})
    index = validate_references(
        source, layout, layout_path=Path("elsewhere/layout.json")
    ).index
    plan = plan_reference_gc(source, layout, index)
    assert plan.configuration_ids == (8,)
    assert apply_reference_gc(source, layout, index, plan).configurations == {}


def test_apply_deletes_exact_candidates_and_preserves_live_definition_and_theme_identity() -> (
    None
):
    live_config = Configuration(
        stacking=Stacking(z_index=12), typography=Typography(font_size=20)
    )
    live_inline = InlineFormatConfiguration()
    unused_config = Configuration()
    unused_inline = InlineFormatConfiguration()
    state = _state(
        "<!-- sj:ref=8 -->\n<sj-format ref=3>Live</sj-format>\n\n"
        "<!-- sj:ref=8 -->\nRepeated use",
        configurations={50: unused_config, 8: live_config, 1: Configuration()},
        inline_formats={20: unused_inline, 3: live_inline},
    )
    source, layout, index = state
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == (1, 50)
    assert plan.inline_format_ids == (20,)
    updated = apply_reference_gc(*state, plan)
    assert updated is not layout
    assert set(updated.configurations) == {8}
    assert set(updated.inline_formats) == {3}
    assert updated.configurations[8] is live_config
    assert updated.inline_formats[3] is live_inline
    assert updated.theme is layout.theme
    assert updated.format_version == layout.format_version
    assert layout.configurations[50] is unused_config
    assert layout.inline_formats[20] is unused_inline
    assert plan.source_document is source
    assert plan.reference_index is index
    assert apply_reference_gc(*state, plan) == updated
    with pytest.raises(TypeError):
        updated.configurations[8] = Configuration()
    with pytest.raises(FrozenInstanceError):
        updated.theme = Theme(
            preset=ThemePreset(name="slidejunction-default", version=1)
        )


@pytest.mark.parametrize("source", ["", "<!-- sj:ref=8 -->\nLive"])
def test_no_candidates_is_layout_identity_no_op(source) -> None:
    state = _state(source, configurations={} if not source else {8: Configuration()})
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == ()
    assert apply_reference_gc(*state, plan) is state[1]


@pytest.mark.parametrize("changed", ["source", "layout", "index"])
@pytest.mark.parametrize("has_candidates", [False, True])
def test_gc_plan_rejects_different_snapshot_identity_even_when_equal(
    changed, has_candidates
) -> None:
    source, layout, index = _state(
        configurations={8: Configuration()} if has_candidates else {}
    )
    plan = plan_reference_gc(source, layout, index)
    if changed == "source":
        source = replace(source)
    elif changed == "layout":
        layout = replace(layout)
    else:
        index = ReferenceIndex(definitions=index.definitions, usages=index.usages)
    with pytest.raises(ValueError):
        apply_reference_gc(source, layout, index, plan)


def test_plan_cannot_delete_formerly_unused_ref_that_became_live() -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    plan = plan_reference_gc(source, layout, index)
    live_source = parse_markdown("<!-- sj:ref=8 -->\nNow live")
    live_index = validate_references(live_source, layout).index
    with pytest.raises(ValueError):
        apply_reference_gc(live_source, layout, live_index, plan)
    assert layout.configurations[8] is plan.layout_document.configurations[8]


def test_plan_cannot_be_reused_against_the_result_of_apply() -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    plan = plan_reference_gc(source, layout, index)
    updated = apply_reference_gc(source, layout, index, plan)
    updated_index = validate_references(source, updated).index
    with pytest.raises(ValueError):
        apply_reference_gc(source, updated, updated_index, plan)


def test_reliability_is_checked_by_the_plan_constructor_without_creating_diagnostics(
    monkeypatch,
) -> None:
    state = _state(configurations={8: Configuration()})

    def forbidden(*args, **kwargs):
        pytest.fail("GC performed I/O or created a Diagnostic")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("pathlib.Path.open", forbidden)
    monkeypatch.setattr(Diagnostic, "__init__", forbidden)
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == (8,)
    updated = apply_reference_gc(*state, plan)
    assert updated.configurations == {}
    assert state[1].configurations[8] is plan.layout_document.configurations[8]
