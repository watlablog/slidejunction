from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import slidejunction
from slidejunction import references
from slidejunction.document import (
    BlockQuote,
    CodeBlock,
    ConfigPointer,
    Diagnostic,
    DiagnosticSeverity,
    Heading,
    ImageBlock,
    InlineCode,
    InlineFormat,
    InlineMath,
    ListBlock,
    ListItem,
    MathBlock,
    Paragraph,
    Presentation,
    Slide,
    SourceBinding,
    SourceDocument,
    SourceSpan,
    ThematicBreak,
)
from slidejunction.layout import (
    Configuration,
    InlineFormatConfiguration,
    LayoutDocument,
    Theme,
    ThemePreset,
    parse_layout,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import (
    ReferenceDefinition,
    ReferenceIndex,
    ReferenceKind,
    ReferenceUsage,
    ReferenceValidationResult,
    validate_references,
)


def _span(start: int = 0, end: int = 1) -> SourceSpan:
    return SourceSpan(
        start_offset=start,
        end_offset=end,
        start_line=0,
        start_column=start,
        end_line=0,
        end_column=end,
    )


def _binding(
    start: int = 0,
    end: int = 1,
    *,
    marker: SourceSpan | None = None,
) -> SourceBinding:
    return SourceBinding(syntax_span=_span(start, end), config_marker_span=marker)


def _theme() -> Theme:
    return Theme(
        preset=ThemePreset(name="slidejunction-default", version=1),
    )


def _layout(
    *,
    configurations: dict[int, Configuration] | None = None,
    inline_formats: dict[int, InlineFormatConfiguration] | None = None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=_theme(),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _source_document(*blocks, title: Heading | None = None) -> SourceDocument:
    span = _span(0, 100)
    return SourceDocument(
        path=Path("slides.md"),
        text="x" * 100,
        presentation=Presentation(
            items=(Slide(title=title, blocks=tuple(blocks), source_span=span),),
        ),
    )


def _definition(
    ref_id: int = 3,
    kind: ReferenceKind = ReferenceKind.CONFIGURATION,
) -> ReferenceDefinition:
    value = (
        Configuration()
        if kind is ReferenceKind.CONFIGURATION
        else InlineFormatConfiguration()
    )
    namespace = (
        "configurations" if kind is ReferenceKind.CONFIGURATION else "inline_formats"
    )
    return ReferenceDefinition(
        ref_id=ref_id,
        kind=kind,
        value=value,
        config_pointer=ConfigPointer(pointer=f"/{namespace}/{ref_id}"),
    )


def _usage(
    ref_id: int = 3,
    kind: ReferenceKind = ReferenceKind.CONFIGURATION,
) -> ReferenceUsage:
    if kind is ReferenceKind.CONFIGURATION:
        consumer = Paragraph(
            children=(),
            source_binding=_binding(),
            config_ref=ref_id,
        )
    else:
        consumer = InlineFormat(
            config_ref=ref_id,
            children=(),
            source_span=_span(),
        )
    return ReferenceUsage(
        ref_id=ref_id,
        kind=kind,
        consumer=consumer,
        source_span=_span(),
    )


def _codes(result: ReferenceValidationResult) -> list[str]:
    return [diagnostic.code for diagnostic in result.diagnostics]


def test_no_refs_or_definitions_produces_an_empty_index() -> None:
    result = validate_references(parse_markdown(""), _layout())

    assert result.index.definitions == {}
    assert result.index.usages == {}
    assert result.diagnostics == ()


def test_shared_object_and_inline_refs_are_counted_per_kind() -> None:
    source = (
        "<!-- sj:ref=3 -->\n"
        "A <sj-format ref=8>x</sj-format>\n\n"
        "<!-- sj:ref=3 -->\n"
        "B <sj-format ref=8>y</sj-format>\n"
    )
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={3: Configuration()},
            inline_formats={8: InlineFormatConfiguration()},
        ),
    )

    assert result.index.consumer_count(3, ReferenceKind.CONFIGURATION) == 2
    assert result.index.consumer_count(8, ReferenceKind.INLINE_FORMAT) == 2
    assert result.index.is_shared(3, ReferenceKind.CONFIGURATION)
    assert result.index.is_shared(8, ReferenceKind.INLINE_FORMAT)
    assert result.diagnostics == ()


def test_all_object_consumers_and_nested_blocks_are_traversed() -> None:
    binding = _binding()
    nested_list_paragraph = Paragraph(children=(), source_binding=binding, config_ref=3)
    nested_quote_paragraph = Paragraph(
        children=(), source_binding=binding, config_ref=3
    )
    title = Heading(level=2, children=(), source_binding=binding, config_ref=3)
    blocks = (
        Paragraph(children=(), source_binding=binding, config_ref=3),
        ListBlock(
            ordered=False,
            start=None,
            items=(ListItem(blocks=(nested_list_paragraph,), source_span=_span()),),
            source_binding=binding,
            config_ref=3,
        ),
        BlockQuote(
            blocks=(nested_quote_paragraph,),
            source_binding=binding,
            config_ref=3,
        ),
        CodeBlock(
            code="x",
            language=None,
            info=None,
            source_binding=binding,
            config_ref=3,
        ),
        ImageBlock(
            src="image.png",
            alt="image",
            source_binding=binding,
            config_ref=3,
        ),
        ThematicBreak(source_binding=binding, config_ref=3),
        MathBlock(content="x", source_binding=binding, config_ref=3),
    )
    result = validate_references(
        _source_document(*blocks, title=title),
        _layout(configurations={3: Configuration()}),
    )
    usages = result.index.usages_for(3, kind=ReferenceKind.CONFIGURATION)

    assert result.index.consumer_count(3, ReferenceKind.CONFIGURATION) == 10
    assert {type(usage.consumer) for usage in usages} == {
        Heading,
        Paragraph,
        ListBlock,
        BlockQuote,
        CodeBlock,
        ImageBlock,
        ThematicBreak,
        MathBlock,
    }
    assert result.diagnostics == ()


def test_inline_usages_are_found_through_every_recursive_container() -> None:
    source = (
        "**<sj-format ref=8>a</sj-format>** "
        "*<sj-format ref=8>b</sj-format>* "
        "[<sj-format ref=8>c</sj-format>](target) "
        "^{<sj-format ref=8>d</sj-format>} "
        "_{<sj-format ref=8>e</sj-format>}"
    )
    result = validate_references(
        parse_markdown(source),
        _layout(inline_formats={8: InlineFormatConfiguration()}),
    )

    assert result.index.consumer_count(8, ReferenceKind.INLINE_FORMAT) == 5
    assert result.index.is_shared(8, ReferenceKind.INLINE_FORMAT)
    assert result.diagnostics == ()


def test_nested_inline_formats_are_all_indexed_in_source_order() -> None:
    source = "<sj-format ref=8>outer <sj-format ref=9>inner</sj-format></sj-format>"
    result = validate_references(
        parse_markdown(source),
        _layout(
            inline_formats={
                8: InlineFormatConfiguration(),
                9: InlineFormatConfiguration(),
            }
        ),
    )

    outer = result.index.usages_for(8, kind=ReferenceKind.INLINE_FORMAT)[0]
    inner = result.index.usages_for(9, kind=ReferenceKind.INLINE_FORMAT)[0]
    assert outer.source_span.start_offset < inner.source_span.start_offset
    assert (
        source[outer.source_span.start_offset : outer.source_span.end_offset] == source
    )
    assert source[inner.source_span.start_offset : inner.source_span.end_offset] == (
        "<sj-format ref=9>inner</sj-format>"
    )
    assert result.diagnostics == ()


def test_image_alt_inline_format_is_not_a_semantic_consumer() -> None:
    source = "![<sj-format ref=8>x</sj-format>](image.png)"
    result = validate_references(
        parse_markdown(source),
        _layout(inline_formats={8: InlineFormatConfiguration()}),
    )

    assert result.index.usages_for(8) == ()
    assert _codes(result) == ["unused-inline-format"]


def test_inline_code_and_inline_math_refs_are_deferred_from_milestone_3() -> None:
    paragraph = Paragraph(
        children=(
            InlineCode(code="code", source_span=_span(1, 2), config_ref=4),
            InlineMath(content="math", source_span=_span(3, 4), config_ref=5),
        ),
        source_binding=_binding(),
    )
    result = validate_references(_source_document(paragraph), _layout())

    assert result.index.usages == {}
    assert result.diagnostics == ()


def test_definition_lookup_is_numeric_kind_filterable_and_path_aware() -> None:
    result = validate_references(
        parse_markdown(""),
        _layout(
            configurations={10: Configuration(), 2: Configuration()},
            inline_formats={8: InlineFormatConfiguration()},
        ),
        layout_path="missing/layout.json",
    )
    index = result.index

    assert tuple(index.definitions) == (2, 8, 10)
    assert [item.config_pointer.pointer for item in index.definitions_for(2)] == [
        "/configurations/2"
    ]
    assert index.definitions_for(8, kind=ReferenceKind.CONFIGURATION) == ()
    inline = index.definitions_for(8, kind=ReferenceKind.INLINE_FORMAT)[0]
    assert inline.config_pointer.pointer == "/inline_formats/8"
    assert inline.config_pointer.path == Path("missing/layout.json")


def test_global_duplicate_retains_both_definitions_and_suppresses_derivatives() -> None:
    source = "<!-- sj:ref=3 -->\nA <sj-format ref=3>x</sj-format>\n"
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={3: Configuration()},
            inline_formats={3: InlineFormatConfiguration()},
        ),
        layout_path="layout.json",
    )

    assert len(result.index.definitions_for(3)) == 2
    assert result.index.consumer_count(3, ReferenceKind.CONFIGURATION) == 1
    assert result.index.consumer_count(3, ReferenceKind.INLINE_FORMAT) == 1
    assert not result.index.is_shared(3, ReferenceKind.CONFIGURATION)
    assert not result.index.is_shared(3, ReferenceKind.INLINE_FORMAT)
    assert _codes(result) == ["duplicate-global-ref"]
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.ref_id == 3
    assert diagnostic.config_pointer == ConfigPointer(
        path=Path("layout.json"), pointer="/inline_formats/3"
    )
    assert diagnostic.related_locations == (
        ConfigPointer(path=Path("layout.json"), pointer="/configurations/3"),
    )


def test_object_and_inline_missing_refs_use_exact_source_locations() -> None:
    source = "<!-- sj:ref=3 -->\nA <sj-format ref=8>x</sj-format>\n"
    result = validate_references(parse_markdown(source), _layout())

    assert _codes(result) == [
        "missing-configuration-ref",
        "missing-inline-format-ref",
    ]
    assert [diagnostic.ref_id for diagnostic in result.diagnostics] == [3, 8]
    assert [
        source[diagnostic.source_span.start_offset : diagnostic.source_span.end_offset]
        for diagnostic in result.diagnostics
    ] == ["<!-- sj:ref=3 -->", "<sj-format ref=8>x</sj-format>"]


def test_same_id_in_both_usage_kinds_produces_two_missing_diagnostics() -> None:
    source = "<!-- sj:ref=3 -->\nA <sj-format ref=3>x</sj-format>\n"
    result = validate_references(parse_markdown(source), _layout())

    assert _codes(result) == [
        "missing-configuration-ref",
        "missing-inline-format-ref",
    ]
    assert [diagnostic.ref_id for diagnostic in result.diagnostics] == [3, 3]
    assert result.index.consumer_count(3, ReferenceKind.CONFIGURATION) == 1
    assert result.index.consumer_count(3, ReferenceKind.INLINE_FORMAT) == 1
    assert not result.index.is_shared(3, ReferenceKind.CONFIGURATION)
    assert not result.index.is_shared(3, ReferenceKind.INLINE_FORMAT)


def test_wrong_kind_refs_are_aggregated_without_missing_or_unused() -> None:
    source = (
        "<!-- sj:ref=3 -->\nA\n\n"
        "<!-- sj:ref=3 -->\nB\n\n"
        "<sj-format ref=8>x</sj-format> "
        "<sj-format ref=8>y</sj-format>\n"
    )
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={8: Configuration()},
            inline_formats={3: InlineFormatConfiguration()},
        ),
        layout_path="layout.json",
    )

    assert _codes(result) == ["ref-kind-mismatch", "ref-kind-mismatch"]
    first, second = result.diagnostics
    assert [first.ref_id, second.ref_id] == [3, 8]
    assert first.related_locations[0] == ConfigPointer(
        path=Path("layout.json"), pointer="/inline_formats/3"
    )
    assert second.related_locations[0] == ConfigPointer(
        path=Path("layout.json"), pointer="/configurations/8"
    )
    assert len(first.related_locations) == 2
    assert len(second.related_locations) == 2


def test_repeated_missing_usages_are_aggregated_per_ref_and_kind() -> None:
    source = (
        "<!-- sj:ref=3 -->\nA\n\n"
        "<!-- sj:ref=3 -->\nB\n\n"
        "<sj-format ref=8>x</sj-format> "
        "<sj-format ref=8>y</sj-format>\n"
    )
    result = validate_references(parse_markdown(source), _layout())

    assert _codes(result) == [
        "missing-configuration-ref",
        "missing-inline-format-ref",
    ]
    assert all(len(item.related_locations) == 1 for item in result.diagnostics)
    assert all(
        isinstance(item.related_locations[0], SourceSpan) for item in result.diagnostics
    )


def test_unused_definitions_are_info_and_used_shared_refs_are_not_unused() -> None:
    source = "<!-- sj:ref=2 -->\nA\n\n<!-- sj:ref=2 -->\nB\n"
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={10: Configuration(), 2: Configuration()},
            inline_formats={8: InlineFormatConfiguration()},
        ),
        layout_path="layout.json",
    )

    assert _codes(result) == ["unused-inline-format", "unused-configuration"]
    assert [item.ref_id for item in result.diagnostics] == [8, 10]
    assert all(item.severity is DiagnosticSeverity.INFO for item in result.diagnostics)
    assert all("explicit GC" in item.message for item in result.diagnostics)
    assert result.index.is_shared(2, ReferenceKind.CONFIGURATION)


@pytest.mark.parametrize(
    "source",
    [
        "<!-- sj:ref=0 -->\nText\n",
        "<!-- sj:ref=3 -->\n",
        "<sj-format ref=0>x\n",
        "<sj-format ref=8>x\n",
    ],
)
def test_invalid_or_recovered_markdown_refs_are_not_indexed(source: str) -> None:
    document = parse_markdown(source)
    original_diagnostics = document.presentation.diagnostics

    result = validate_references(document, _layout())

    assert result.index.usages == {}
    assert result.diagnostics == ()
    assert document.presentation.diagnostics is original_diagnostics


def test_reference_diagnostic_categories_and_numeric_order_are_deterministic() -> None:
    source = "<sj-format ref=20>first</sj-format>\n\n<!-- sj:ref=30 -->\nlast\n"
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={
                10: Configuration(),
                2: Configuration(),
                5: Configuration(),
            },
            inline_formats={
                10: InlineFormatConfiguration(),
                2: InlineFormatConfiguration(),
                6: InlineFormatConfiguration(),
            },
        ),
    )

    assert _codes(result) == [
        "duplicate-global-ref",
        "duplicate-global-ref",
        "missing-inline-format-ref",
        "missing-configuration-ref",
        "unused-configuration",
        "unused-inline-format",
    ]
    assert [item.ref_id for item in result.diagnostics] == [2, 10, 20, 30, 5, 6]


def test_reference_index_defensively_copies_group_mappings() -> None:
    definition = _definition()
    usage = _usage()
    definitions = {3: (definition,)}
    usages = {3: (usage,)}
    index = ReferenceIndex(definitions=definitions, usages=usages)
    definitions[4] = (_definition(4),)
    usages.clear()

    assert tuple(index.definitions) == (3,)
    assert tuple(index.usages) == (3,)
    with pytest.raises(TypeError):
        index.definitions[4] = (_definition(4),)  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        index.usages = {}  # type: ignore[misc]


@pytest.mark.parametrize("invalid_ref", [0, -1, True])
def test_reference_models_and_lookup_reject_invalid_ref_ids(invalid_ref: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        ReferenceDefinition(
            ref_id=invalid_ref,
            kind=ReferenceKind.CONFIGURATION,
            value=Configuration(),
            config_pointer=ConfigPointer(pointer="/configurations/1"),
        )
    index = ReferenceIndex(definitions={}, usages={})
    with pytest.raises(ValueError, match="positive integer"):
        index.definitions_for(invalid_ref)


def test_reference_definition_validates_kind_value_and_location() -> None:
    with pytest.raises(TypeError, match="ReferenceKind"):
        ReferenceDefinition(
            ref_id=3,
            kind="configuration",  # type: ignore[arg-type]
            value=Configuration(),
            config_pointer=ConfigPointer(pointer="/configurations/3"),
        )
    with pytest.raises(TypeError, match="incompatible value"):
        ReferenceDefinition(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            value=InlineFormatConfiguration(),
            config_pointer=ConfigPointer(pointer="/configurations/3"),
        )
    with pytest.raises(TypeError, match="ConfigPointer"):
        ReferenceDefinition(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            value=Configuration(),
            config_pointer=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("kind", "pointer"),
    [
        (ReferenceKind.CONFIGURATION, "/inline_formats/3"),
        (ReferenceKind.CONFIGURATION, "/configurations/4"),
        (ReferenceKind.INLINE_FORMAT, "/configurations/8"),
        (ReferenceKind.INLINE_FORMAT, "/inline_formats/9"),
    ],
)
def test_reference_definition_rejects_inconsistent_pointer(
    kind: ReferenceKind,
    pointer: str,
) -> None:
    ref_id = 3 if kind is ReferenceKind.CONFIGURATION else 8
    value = (
        Configuration()
        if kind is ReferenceKind.CONFIGURATION
        else InlineFormatConfiguration()
    )

    with pytest.raises(ValueError, match="definition pointer"):
        ReferenceDefinition(
            ref_id=ref_id,
            kind=kind,
            value=value,
            config_pointer=ConfigPointer(pointer=pointer),
        )


@pytest.mark.parametrize("path", [None, Path("missing/layout.json")])
def test_reference_definition_accepts_derived_pointer_with_optional_path(
    path: Path | None,
) -> None:
    configuration = ReferenceDefinition(
        ref_id=3,
        kind=ReferenceKind.CONFIGURATION,
        value=Configuration(),
        config_pointer=ConfigPointer(path=path, pointer="/configurations/3"),
    )
    inline_format = ReferenceDefinition(
        ref_id=8,
        kind=ReferenceKind.INLINE_FORMAT,
        value=InlineFormatConfiguration(),
        config_pointer=ConfigPointer(path=path, pointer="/inline_formats/8"),
    )

    assert configuration.config_pointer.path == path
    assert inline_format.config_pointer.path == path


def test_reference_usage_validates_kind_consumer_and_location() -> None:
    inline = InlineFormat(config_ref=3, children=(), source_span=_span())
    paragraph = Paragraph(children=(), source_binding=_binding(), config_ref=3)

    with pytest.raises(TypeError, match="ReferenceKind"):
        ReferenceUsage(
            ref_id=3,
            kind="configuration",  # type: ignore[arg-type]
            consumer=paragraph,
            source_span=_span(),
        )
    with pytest.raises(TypeError, match="incompatible consumer"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            consumer=inline,
            source_span=_span(),
        )
    with pytest.raises(TypeError, match="incompatible consumer"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.INLINE_FORMAT,
            consumer=paragraph,
            source_span=_span(),
        )
    with pytest.raises(TypeError, match="SourceSpan"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            consumer=paragraph,
            source_span=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("kind", "consumer", "ref_id"),
    [
        (
            ReferenceKind.CONFIGURATION,
            Paragraph(children=(), source_binding=_binding(), config_ref=4),
            3,
        ),
        (
            ReferenceKind.INLINE_FORMAT,
            InlineFormat(config_ref=8, children=(), source_span=_span()),
            9,
        ),
    ],
)
def test_reference_usage_rejects_ref_id_inconsistent_with_consumer(
    kind: ReferenceKind,
    consumer: Paragraph | InlineFormat,
    ref_id: int,
) -> None:
    source_span = (
        consumer.source_binding.syntax_span
        if isinstance(consumer, Paragraph)
        else consumer.source_span
    )

    with pytest.raises(ValueError, match="ID does not match"):
        ReferenceUsage(
            ref_id=ref_id,
            kind=kind,
            consumer=consumer,
            source_span=source_span,
        )


def test_configuration_usage_requires_marker_location_when_present() -> None:
    marker = _span(0, 5)
    consumer = Paragraph(
        children=(),
        source_binding=_binding(6, 12, marker=marker),
        config_ref=3,
    )

    with pytest.raises(ValueError, match="location does not match"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            consumer=consumer,
            source_span=consumer.source_binding.syntax_span,
        )

    usage = ReferenceUsage(
        ref_id=3,
        kind=ReferenceKind.CONFIGURATION,
        consumer=consumer,
        source_span=marker,
    )
    assert usage.source_span is marker


def test_configuration_usage_falls_back_to_syntax_location_without_marker() -> None:
    syntax = _span(2, 8)
    consumer = Paragraph(
        children=(),
        source_binding=SourceBinding(syntax_span=syntax),
        config_ref=3,
    )

    with pytest.raises(ValueError, match="location does not match"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            consumer=consumer,
            source_span=_span(9, 10),
        )

    usage = ReferenceUsage(
        ref_id=3,
        kind=ReferenceKind.CONFIGURATION,
        consumer=consumer,
        source_span=syntax,
    )
    assert usage.source_span is syntax


def test_inline_format_usage_requires_consumer_source_location() -> None:
    syntax = _span(3, 9)
    consumer = InlineFormat(config_ref=8, children=(), source_span=syntax)

    with pytest.raises(ValueError, match="location does not match"):
        ReferenceUsage(
            ref_id=8,
            kind=ReferenceKind.INLINE_FORMAT,
            consumer=consumer,
            source_span=_span(10, 11),
        )

    usage = ReferenceUsage(
        ref_id=8,
        kind=ReferenceKind.INLINE_FORMAT,
        consumer=consumer,
        source_span=syntax,
    )
    assert usage.source_span is syntax


@pytest.mark.parametrize(
    ("definitions", "usages", "message"),
    [
        ([], {}, "must be a mapping"),
        ({3: [_definition()]}, {}, "values must be tuples"),
        ({3: ("invalid",)}, {}, "invalid entry"),
        ({3: (_definition(4),)}, {}, "does not match"),
        ({True: (_definition(),)}, {}, "positive integer"),
        ({3: ()}, {}, "must not be empty"),
        ({}, {3: [_usage()]}, "values must be tuples"),
        ({}, {3: ("invalid",)}, "invalid entry"),
        ({}, {3: ()}, "must not be empty"),
    ],
)
def test_reference_index_validates_mapping_and_tuple_entries(
    definitions,
    usages,
    message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        ReferenceIndex(definitions=definitions, usages=usages)


def test_reference_result_and_kind_filtered_methods_validate_runtime_types() -> None:
    index = ReferenceIndex(definitions={}, usages={})
    with pytest.raises(TypeError, match="ReferenceIndex"):
        ReferenceValidationResult(index=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="tuple"):
        ReferenceValidationResult(index=index, diagnostics=[])
    with pytest.raises(TypeError, match="Diagnostic"):
        ReferenceValidationResult(index=index, diagnostics=("invalid",))
    with pytest.raises(TypeError, match="ReferenceKind"):
        index.usages_for(3, kind="configuration")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ReferenceKind"):
        index.consumer_count(3, "configuration")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        index.consumer_count(3)  # type: ignore[call-arg]


def test_validate_references_checks_inputs_without_merging_existing_diagnostics() -> (
    None
):
    layout_result = parse_layout(
        '{"format_version": 1, "theme": {"preset": {"name": "unknown", "version": 1}}}',
        path="layout.json",
    )
    assert layout_result.document is not None
    layout_diagnostics = layout_result.diagnostics
    source = parse_markdown("<!-- sj:ref=3 -->\n")
    source_diagnostics = source.presentation.diagnostics

    result = validate_references(source, layout_result.document)

    assert result.diagnostics == ()
    assert layout_result.diagnostics is layout_diagnostics
    assert source.presentation.diagnostics is source_diagnostics
    with pytest.raises(TypeError, match="SourceDocument"):
        validate_references(None, layout_result.document)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="LayoutDocument"):
        validate_references(source, None)  # type: ignore[arg-type]


def test_references_module_is_public_without_expanding_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "validate_references")
    assert {
        "ReferenceDefinition",
        "ReferenceIndex",
        "ReferenceKind",
        "ReferenceUsage",
        "ReferenceValidationResult",
        "validate_references",
    } == set(references.__all__)


def test_diagnostic_runtime_model_accepts_cross_source_related_locations() -> None:
    usage = _usage()
    definition = _definition()
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="ref-kind-mismatch",
        message="Wrong reference kind.",
        source_span=usage.source_span,
        ref_id=usage.ref_id,
        related_locations=(definition.config_pointer,),
    )

    assert diagnostic.location is usage.source_span
    assert diagnostic.related_locations == (definition.config_pointer,)
