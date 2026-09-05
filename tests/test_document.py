from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import slidejunction
from slidejunction import document
from slidejunction.document import (
    BlockQuote,
    CodeBlock,
    ConfigPointer,
    Diagnostic,
    DiagnosticSeverity,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    InlineCode,
    InlineFormat,
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
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)


def test_source_span_uses_zero_based_half_open_character_offsets() -> None:
    source = "α\nbeta"
    span = SourceSpan(
        start_offset=2,
        end_offset=6,
        start_line=1,
        start_column=0,
        end_line=1,
        end_column=4,
    )

    assert source[span.start_offset : span.end_offset] == "beta"


def test_source_span_allows_zero_width_range() -> None:
    span = SourceSpan(
        start_offset=0,
        end_offset=0,
        start_line=0,
        start_column=0,
        end_line=0,
        end_column=0,
    )

    assert span.start_offset == span.end_offset


@pytest.mark.parametrize(
    "values",
    [
        {
            "start_offset": -1,
            "end_offset": 0,
            "start_line": 0,
            "start_column": 0,
            "end_line": 0,
            "end_column": 0,
        },
        {
            "start_offset": 2,
            "end_offset": 1,
            "start_line": 0,
            "start_column": 0,
            "end_line": 0,
            "end_column": 1,
        },
        {
            "start_offset": 0,
            "end_offset": 1,
            "start_line": 2,
            "start_column": 0,
            "end_line": 1,
            "end_column": 0,
        },
    ],
)
def test_source_span_rejects_invalid_ranges(values: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        SourceSpan(**values)


def test_source_binding_separates_syntax_and_config_marker() -> None:
    marker_span = _span(0, 20, end_line=1)
    syntax_span = _span(20, 30, start_line=1, end_line=1, end_column=10)

    binding = SourceBinding(
        syntax_span=syntax_span,
        config_marker_span=marker_span,
    )

    assert binding.syntax_span is syntax_span
    assert binding.config_marker_span is marker_span


def test_slide_source_span_holds_complete_half_open_source_range() -> None:
    source = "<!-- sj:ref=3 -->\n## FFT\n\nParagraph A.\n\n<!-- sj:ref=4 -->\n## STFT\n"
    next_slide_start = source.index("<!-- sj:ref=4 -->")
    slide = Slide(
        title=None,
        blocks=(),
        source_span=SourceSpan(
            start_offset=0,
            end_offset=next_slide_start,
            start_line=0,
            start_column=0,
            end_line=5,
            end_column=0,
        ),
    )

    assert source[slide.source_span.start_offset : slide.source_span.end_offset] == (
        "<!-- sj:ref=3 -->\n## FFT\n\nParagraph A.\n\n"
    )
    assert source[slide.source_span.end_offset :].startswith("<!-- sj:ref=4 -->")


def test_document_nodes_are_immutable() -> None:
    paragraph = Paragraph(
        children=(Text(value="Immutable", source_span=_span(0, 9)),),
        source_binding=_binding(0, 9),
    )

    with pytest.raises(FrozenInstanceError):
        paragraph.config_ref = 3  # type: ignore[misc]

    assert isinstance(paragraph.children, tuple)


def test_inline_model_preserves_nested_semantics() -> None:
    span = _span(0, 80)
    nested = Strong(
        children=(
            Emphasis(
                children=(Text(value="nested", source_span=span),),
                source_span=span,
            ),
        ),
        source_span=span,
    )
    link = Link(
        destination="https://example.com",
        title="Example",
        children=(Text(value="link", source_span=span),),
        source_span=span,
    )
    paragraph = Paragraph(
        children=(
            Text(value="Text", source_span=span),
            nested,
            InlineCode(code="value", source_span=span),
            link,
            InlineImage(src="assets/image.png", alt="Image", source_span=span),
            SoftBreak(source_span=span),
            HardBreak(source_span=span),
            InlineMath(content="x^2", source_span=span),
        ),
        source_binding=SourceBinding(syntax_span=span),
    )

    assert paragraph.children[1] is nested
    assert nested.children[0].children[0].value == "nested"
    assert paragraph.children[3] is link


def test_native_inline_extension_nodes_preserve_nested_semantics() -> None:
    span = _span(0, 20)
    superscript = Superscript(
        children=(Text(value="2", source_span=span),),
        source_span=span,
    )
    subscript = Subscript(
        children=(Text(value="i", source_span=span),),
        source_span=span,
    )
    formatted = InlineFormat(
        config_ref=8,
        children=(superscript, subscript),
        source_span=span,
    )

    assert formatted.children == (superscript, subscript)
    assert formatted.config_ref == 8
    with pytest.raises(FrozenInstanceError):
        formatted.config_ref = 9  # type: ignore[misc]


@pytest.mark.parametrize("invalid_ref", [0, -1, True])
def test_inline_format_reference_must_be_a_positive_integer(
    invalid_ref: int,
) -> None:
    with pytest.raises(ValueError):
        InlineFormat(config_ref=invalid_ref, children=(), source_span=_span(0, 1))


def test_block_model_represents_recursive_structure() -> None:
    span = _span(0, 100)
    binding = SourceBinding(syntax_span=span)
    paragraph = Paragraph(
        children=(Text(value="Item", source_span=span),),
        source_binding=binding,
    )
    list_item = ListItem(blocks=(paragraph,), source_span=span)
    list_block = ListBlock(
        ordered=True,
        start=3,
        items=(list_item,),
        source_binding=binding,
    )
    quote = BlockQuote(blocks=(paragraph, list_block), source_binding=binding)
    slide = Slide(
        title=None,
        blocks=(
            Heading(
                level=3,
                children=(Text(value="Detail", source_span=span),),
                source_binding=binding,
            ),
            paragraph,
            list_block,
            quote,
            CodeBlock(
                code="print('hello')\n",
                language="python",
                info="python",
                source_binding=binding,
            ),
            ImageBlock(
                src="assets/image.png",
                alt="Image",
                source_binding=binding,
            ),
            ThematicBreak(source_binding=binding),
            MathBlock(content="x^2", source_binding=binding),
        ),
        source_span=span,
    )

    assert list_block.items[0].blocks == (paragraph,)
    assert quote.blocks == (paragraph, list_block)
    assert len(slide.blocks) == 8


def test_presentation_preserves_unsectioned_slides_and_sections() -> None:
    span = _span(0, 20)
    binding = SourceBinding(syntax_span=span)
    unsectioned_title = Heading(
        level=2,
        children=(Text(value="Before", source_span=span),),
        source_binding=binding,
    )
    unsectioned_slide = Slide(title=unsectioned_title, blocks=(), source_span=span)
    section_title = Heading(
        level=1,
        children=(Text(value="Section", source_span=span),),
        source_binding=binding,
    )
    title_slide = Slide(title=section_title, blocks=(), source_span=span)
    regular_slide = Slide(
        title=Heading(
            level=2,
            children=(Text(value="Inside", source_span=span),),
            source_binding=binding,
        ),
        blocks=(),
        source_span=span,
    )
    section = Section(title_slide=title_slide, slides=(regular_slide,))
    presentation = Presentation(items=(unsectioned_slide, section))

    assert presentation.items == (unsectioned_slide, section)
    assert section.title_slide is title_slide
    assert section.slides == (regular_slide,)
    assert title_slide not in section.slides
    assert isinstance(section.title_slide.title, Heading)


def test_configuration_references_are_optional_and_shareable() -> None:
    binding = _binding(0, 10)
    first = Paragraph(children=(), source_binding=binding, config_ref=3)
    second = Paragraph(children=(), source_binding=binding, config_ref=3)
    plain = Paragraph(children=(), source_binding=binding)
    inline_code = InlineCode(code="x", source_span=_span(0, 1), config_ref=4)
    inline_math = InlineMath(content="x", source_span=_span(0, 1), config_ref=5)

    assert first.config_ref == second.config_ref == 3
    assert plain.config_ref is None
    assert inline_code.config_ref == 4
    assert inline_math.config_ref == 5


@pytest.mark.parametrize("invalid_ref", [0, -1, True])
def test_configuration_references_must_be_positive_integers(
    invalid_ref: int,
) -> None:
    with pytest.raises(ValueError):
        Paragraph(
            children=(),
            source_binding=_binding(0, 1),
            config_ref=invalid_ref,
        )


@pytest.mark.parametrize("level", [0, 7])
def test_heading_level_must_be_commonmark_level(level: int) -> None:
    with pytest.raises(ValueError):
        Heading(
            level=level,
            children=(),
            source_binding=_binding(0, 1),
        )


def test_source_document_retains_original_text_path_and_diagnostics() -> None:
    source = "<!-- sj:ref=3 -->\n"
    span = SourceSpan(
        start_offset=0,
        end_offset=len(source),
        start_line=0,
        start_column=0,
        end_line=1,
        end_column=0,
    )
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="unused-config-ref",
        message="Configuration reference 3 is not bound to a block.",
        source_span=span,
    )
    slide = Slide(title=None, blocks=(), source_span=span)
    presentation = Presentation(items=(slide,), diagnostics=(diagnostic,))
    source_document = SourceDocument(
        path=Path("slides.md"),
        text=source,
        presentation=presentation,
    )

    assert source_document.text == source
    assert source_document.path == Path("slides.md")
    assert source_document.presentation.diagnostics == (diagnostic,)
    assert diagnostic.severity == "warning"
    assert diagnostic.location is span


def test_configuration_diagnostic_uses_derived_json_pointer_location() -> None:
    pointer = ConfigPointer(path=Path("layout.json"), pointer="/theme/colors/accent-1")
    related = ConfigPointer(path=Path("layout.json"), pointer="/theme/preset")
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="missing-theme-color-token",
        message="The referenced theme color token is unavailable.",
        config_pointer=pointer,
        ref_id=3,
        related_locations=(related,),
        hint="Define the token or remove the override.",
    )

    assert diagnostic.source_span is None
    assert diagnostic.config_pointer is pointer
    assert diagnostic.location is pointer
    assert diagnostic.ref_id == 3
    assert diagnostic.related_locations == (related,)


@pytest.mark.parametrize(
    "both_locations",
    [False, True],
)
def test_diagnostic_requires_exactly_one_stored_location(
    both_locations: bool,
) -> None:
    locations = (
        {
            "source_span": _span(0, 1),
            "config_pointer": ConfigPointer(pointer="/theme"),
        }
        if both_locations
        else {}
    )
    with pytest.raises(ValueError, match="exactly one"):
        Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code="example",
            message="Example diagnostic.",
            **locations,
        )


@pytest.mark.parametrize(
    "pointer, message",
    [
        ("theme", "must start with"),
        ("configurations/3", "must start with"),
        ("/theme/~2", "invalid escape"),
    ],
)
def test_config_pointer_requires_rfc_6901_syntax(pointer: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ConfigPointer(pointer=pointer)


def test_diagnostic_location_is_derived_not_stored() -> None:
    assert "location" not in Diagnostic.__dataclass_fields__


def test_document_module_is_public_without_expanding_top_level_api() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert "Presentation" not in slidejunction.__all__
    assert "Presentation" in document.__all__
    assert document.Presentation is Presentation
    assert {"InlineFormat", "Superscript", "Subscript"} <= set(document.__all__)


def _span(
    start_offset: int,
    end_offset: int,
    *,
    start_line: int = 0,
    start_column: int = 0,
    end_line: int = 0,
    end_column: int | None = None,
) -> SourceSpan:
    return SourceSpan(
        start_offset=start_offset,
        end_offset=end_offset,
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_offset if end_column is None else end_column,
    )


def _binding(start_offset: int, end_offset: int) -> SourceBinding:
    return SourceBinding(syntax_span=_span(start_offset, end_offset))
