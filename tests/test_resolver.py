from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import references, resolver
from slidejunction.document import (
    BlockQuote,
    CodeBlock,
    Heading,
    ImageBlock,
    InlineCode,
    InlineFormat,
    InlineImage,
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
    Appearance,
    Border,
    BorderStyle,
    CodeConfig,
    CodeTheme,
    Configuration,
    Crop,
    DirectColor,
    ElementKind,
    Fill,
    FillMode,
    FocalPoint,
    FontFamily,
    FontStyle,
    FontWeight,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    MediaFit,
    Outline,
    Placement,
    PlacementMode,
    Script,
    SemanticRole,
    Shadow,
    ShadowMode,
    Size,
    SlideKind,
    Stacking,
    Strikethrough,
    TextAlign,
    TextEffects,
    Theme,
    ThemeColor,
    ThemePreset,
    ThemeSlide,
    Transform,
    Typography,
    VerticalAlign,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import ReferenceIndex, validate_references
from slidejunction.resolver import (
    ResolvedConfiguration,
    ResolvedInlineStyle,
    ResolvedPlacementMode,
    resolve_presentation,
)

_PALETTE = {
    "background-1": "#FFFFFF",
    "foreground-1": "#1F2328",
    "background-2": "#F6F8FA",
    "foreground-2": "#57606A",
    "accent-1": "#2563EB",
    "accent-2": "#0F766E",
    "accent-3": "#16A34A",
    "accent-4": "#D97706",
    "accent-5": "#DC2626",
    "accent-6": "#7C3AED",
    "link": "#2563EB",
    "visited-link": "#7C3AED",
}


def _span(start: int = 0, end: int = 1) -> SourceSpan:
    return SourceSpan(
        start_offset=start,
        end_offset=end,
        start_line=0,
        start_column=start,
        end_line=0,
        end_column=end,
    )


def _binding(start: int = 0, end: int = 1) -> SourceBinding:
    return SourceBinding(syntax_span=_span(start, end))


def _theme(
    *,
    preset: ThemePreset | None = None,
    colors=None,
    slide=None,
    elements=None,
    roles=None,
    slides=None,
) -> Theme:
    return Theme(
        preset=preset or ThemePreset(name="slidejunction-default", version=1),
        colors={} if colors is None else colors,
        slide=slide,
        elements={} if elements is None else elements,
        roles={} if roles is None else roles,
        slides={} if slides is None else slides,
    )


def _layout(
    *,
    theme: Theme | None = None,
    configurations=None,
    inline_formats=None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=theme or _theme(),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _resolve(source: str, layout: LayoutDocument):
    document = parse_markdown(source)
    index = validate_references(document, layout).index
    return document, index, resolve_presentation(document, layout, index)


def _first_slide(resolved):
    item = resolved.items[0]
    if hasattr(item, "title_slide"):
        return item.title_slide
    return item


def _source_with_blocks(*blocks) -> SourceDocument:
    return SourceDocument(
        path=Path("slides.md"),
        text="x" * 100,
        presentation=Presentation(
            items=(
                Slide(
                    title=None,
                    blocks=tuple(blocks),
                    source_span=_span(0, 100),
                ),
            ),
        ),
    )


def test_built_in_defaults_are_effective_without_inventing_visual_defaults() -> None:
    _, _, resolved = _resolve("## Title\n\nBody", _layout())
    slide = _first_slide(resolved)
    title = slide.title
    paragraph = slide.blocks[0]

    assert slide.kind is SlideKind.H2
    assert slide.configuration == ResolvedConfiguration()
    for block in (title, paragraph):
        assert block.configuration.placement.mode is ResolvedPlacementMode.FLOW
        assert block.configuration.transform.rotation == 0
        assert block.configuration.stacking.z_index == 0
        assert block.configuration.typography.text_align is TextAlign.LEFT
        assert block.configuration.typography.vertical_align is VerticalAlign.TOP
        assert block.configuration.typography.font_size is None
        assert block.configuration.appearance is None
        assert block.configuration.size is None
        assert block.configuration.code is None


def test_image_block_receives_only_its_defined_built_in_defaults() -> None:
    _, _, resolved = _resolve("![image](image.png)", _layout())
    configuration = _first_slide(resolved).blocks[0].configuration

    assert configuration.media == ImageMedia(
        aspect_ratio_locked=True,
        fit=MediaFit.STRETCH,
    )
    assert configuration.typography is None
    assert configuration.text_effects is None


@pytest.mark.parametrize(("token", "expected"), _PALETTE.items())
def test_default_preset_resolves_the_exact_standard_palette(
    token: str,
    expected: str,
) -> None:
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(color=ThemeColor(token))
                )
            }
        )
    )

    _, _, resolved = _resolve("text", layout)

    color = _first_slide(resolved).blocks[0].configuration.typography.color
    assert color == DirectColor(expected)


def test_project_colors_override_preset_and_custom_tokens_are_available() -> None:
    layout = _layout(
        theme=_theme(
            colors={
                "accent-1": DirectColor("#010203"),
                "project-token": DirectColor("#AABBCC"),
            },
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    appearance=Appearance(
                        fill=Fill(color=ThemeColor("accent-1")),
                        border=Border(color=ThemeColor("project-token")),
                    )
                )
            },
        )
    )

    _, _, resolved = _resolve("text", layout)
    appearance = _first_slide(resolved).blocks[0].configuration.appearance

    assert appearance.fill.color == DirectColor("#010203")
    assert appearance.border.color == DirectColor("#AABBCC")


@pytest.mark.parametrize(
    "preset",
    [
        ThemePreset(name="future-preset", version=7),
        ThemePreset(name="slidejunction-default", version=99),
    ],
)
def test_unknown_and_unsupported_presets_fallback_effectively_only(
    preset: ThemePreset,
) -> None:
    layout = _layout(
        theme=_theme(
            preset=preset,
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(color=ThemeColor("accent-2"))
                )
            },
        )
    )

    _, _, resolved = _resolve("text", layout)

    assert layout.theme.preset is preset
    assert _first_slide(resolved).blocks[
        0
    ].configuration.typography.color == DirectColor("#0F766E")


def test_unresolved_upper_theme_color_keeps_the_lower_valid_color() -> None:
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(
                        color=DirectColor("#112233"),
                        font_size=20,
                    )
                )
            },
            slides={
                SlideKind.IMPLICIT: ThemeSlide(
                    elements={
                        ElementKind.PARAGRAPH: Configuration(
                            typography=Typography(
                                color=ThemeColor("missing-token"),
                                font_weight=FontWeight.BOLD,
                            )
                        )
                    }
                )
            },
        )
    )

    _, _, resolved = _resolve("text", layout)
    typography = _first_slide(resolved).blocks[0].configuration.typography

    assert typography.color == DirectColor("#112233")
    assert typography.font_size == 20
    assert typography.font_weight is FontWeight.BOLD


def test_slide_kinds_element_kinds_and_title_roles_are_derived_from_structure() -> None:
    _, _, implicit = _resolve("preamble", _layout())
    _, _, h2 = _resolve("## H2\n\n### Body", _layout())
    _, _, section = _resolve("# H1\n\nBody\n\n## H2", _layout())

    assert _first_slide(implicit).kind is SlideKind.IMPLICIT
    assert _first_slide(implicit).title is None
    assert _first_slide(h2).kind is SlideKind.H2
    assert _first_slide(h2).title.semantic_role is SemanticRole.SLIDE_TITLE
    assert h2.items[0].blocks[0].element_kind is ElementKind.HEADING
    assert h2.items[0].blocks[0].semantic_role is None
    assert section.items[0].title_slide.kind is SlideKind.H1
    assert section.items[0].slides[0].kind is SlideKind.H2


def test_every_block_type_maps_to_its_capability_filtered_configuration() -> None:
    configuration = Configuration(
        placement=Placement(mode=PlacementMode.FREE, x=1, y=2),
        size=Size(width=30, height=20),
        transform=Transform(rotation=15),
        typography=Typography(
            font_family=FontFamily(latin="latin", japanese="japanese"),
            font_size=24,
            font_weight=FontWeight.BOLD,
            font_style=FontStyle.ITALIC,
            color=DirectColor("#123456"),
            underline=True,
            strikethrough=Strikethrough.DOUBLE,
            script=Script.SUPERSCRIPT,
            text_align=TextAlign.RIGHT,
            vertical_align=VerticalAlign.BOTTOM,
        ),
        text_effects=TextEffects(
            outline=Outline(color=DirectColor("#654321"), width=2)
        ),
        appearance=Appearance(opacity=0.5),
        media=ImageMedia(
            aspect_ratio_locked=False,
            crop=Crop(x=5, width=90),
            fit=MediaFit.COVER,
            focal_point=FocalPoint(x=30, y=40),
        ),
        stacking=Stacking(z_index=4),
        code=CodeConfig(theme=CodeTheme.DARK),
    )
    blocks = (
        Heading(level=3, children=(), source_binding=_binding(1, 2), config_ref=3),
        Paragraph(children=(), source_binding=_binding(3, 4), config_ref=3),
        ListBlock(
            ordered=False,
            start=None,
            items=(),
            source_binding=_binding(5, 6),
            config_ref=3,
        ),
        BlockQuote(blocks=(), source_binding=_binding(7, 8), config_ref=3),
        CodeBlock(
            code="x",
            language=None,
            info=None,
            source_binding=_binding(9, 10),
            config_ref=3,
        ),
        ImageBlock(
            src="image.png",
            alt="image",
            source_binding=_binding(11, 12),
            config_ref=3,
        ),
        MathBlock(content="x", source_binding=_binding(13, 14), config_ref=3),
        ThematicBreak(source_binding=_binding(15, 16), config_ref=3),
    )
    source = _source_with_blocks(*blocks)
    layout = _layout(configurations={3: configuration})
    index = validate_references(source, layout).index

    resolved_blocks = resolve_presentation(source, layout, index).items[0].blocks
    by_kind = {block.element_kind: block.configuration for block in resolved_blocks}

    assert set(by_kind) == set(ElementKind)
    for kind in ElementKind:
        assert by_kind[kind].placement.mode is ResolvedPlacementMode.FREE
        assert by_kind[kind].transform.rotation == 15
        assert by_kind[kind].stacking.z_index == 4
        assert by_kind[kind].appearance.opacity == 0.5
    for kind in (
        ElementKind.HEADING,
        ElementKind.PARAGRAPH,
        ElementKind.LIST,
        ElementKind.BLOCK_QUOTE,
    ):
        assert by_kind[kind].typography.font_family.latin == "latin"
        assert by_kind[kind].text_effects.outline.width == 2
        assert by_kind[kind].media is None
        assert by_kind[kind].code is None
    code = by_kind[ElementKind.CODE_BLOCK]
    assert code.typography == Typography(font_size=24)
    assert code.code == CodeConfig(theme=CodeTheme.DARK)
    assert code.text_effects is None
    image = by_kind[ElementKind.IMAGE_BLOCK]
    assert image.media.crop == Crop(x=5, width=90)
    assert image.typography is None
    math = by_kind[ElementKind.MATH_BLOCK]
    assert math.typography == Typography(
        font_size=24,
        color=DirectColor("#123456"),
    )
    assert math.text_effects.outline.width == 2
    thematic = by_kind[ElementKind.THEMATIC_BREAK]
    assert thematic.typography is None
    assert thematic.text_effects is None


@pytest.mark.parametrize("container_kind", ["list", "quote"])
def test_container_text_inheritance_uses_the_approved_leaf_matrix(
    container_kind: str,
) -> None:
    child = Paragraph(children=(), source_binding=_binding(20, 21))
    if container_kind == "list":
        container = ListBlock(
            ordered=False,
            start=None,
            items=(ListItem(blocks=(child,), source_span=_span(10, 30)),),
            source_binding=_binding(1, 30),
            config_ref=3,
        )
    else:
        container = BlockQuote(
            blocks=(child,),
            source_binding=_binding(1, 30),
            config_ref=3,
        )
    parent_typography = Typography(
        font_family=FontFamily(latin="latin", japanese="japanese"),
        font_size=22,
        font_weight=FontWeight.BOLD,
        font_style=FontStyle.ITALIC,
        color=DirectColor("#123456"),
        underline=True,
        strikethrough=Strikethrough.SINGLE,
        script=Script.SUBSCRIPT,
        text_align=TextAlign.RIGHT,
        vertical_align=VerticalAlign.BOTTOM,
    )
    layout = _layout(
        configurations={
            3: Configuration(
                typography=parent_typography,
                text_effects=TextEffects(
                    outline=Outline(color=DirectColor("#654321"), width=2)
                ),
                appearance=Appearance(opacity=0.25),
            )
        }
    )
    source = _source_with_blocks(container)
    index = validate_references(source, layout).index

    resolved_container = resolve_presentation(source, layout, index).items[0].blocks[0]
    resolved_child = (
        resolved_container.list_items[0].blocks[0]
        if container_kind == "list"
        else resolved_container.blocks[0]
    )
    typography = resolved_child.configuration.typography

    assert typography.font_family == parent_typography.font_family
    assert typography.font_size == 22
    assert typography.font_weight is FontWeight.BOLD
    assert typography.font_style is FontStyle.ITALIC
    assert typography.color == DirectColor("#123456")
    assert typography.underline is True
    assert typography.strikethrough is Strikethrough.SINGLE
    assert typography.script is Script.SUBSCRIPT
    assert typography.text_align is TextAlign.RIGHT
    assert typography.vertical_align is VerticalAlign.TOP
    assert resolved_child.configuration.text_effects.outline.width == 2
    assert resolved_child.configuration.appearance is None


def test_child_specific_theme_values_override_inherited_text_values() -> None:
    child = Paragraph(children=(), source_binding=_binding(5, 6))
    quote = BlockQuote(
        blocks=(child,),
        source_binding=_binding(1, 10),
        config_ref=3,
    )
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(
                        font_size=30,
                        font_weight=FontWeight.REGULAR,
                    )
                )
            }
        ),
        configurations={
            3: Configuration(
                typography=Typography(
                    font_size=20,
                    font_weight=FontWeight.BOLD,
                )
            )
        },
    )
    source = _source_with_blocks(quote)
    index = validate_references(source, layout).index

    child_config = (
        resolve_presentation(source, layout, index)
        .items[0]
        .blocks[0]
        .blocks[0]
        .configuration
    )

    assert child_config.typography.font_size == 30
    assert child_config.typography.font_weight is FontWeight.REGULAR


def test_complete_theme_and_source_cascade_is_property_wise() -> None:
    source_text = "<!-- sj:ref=3 -->\n## Title"
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.HEADING: Configuration(
                    typography=Typography(
                        font_family=FontFamily(latin="element-font"),
                        font_size=30,
                    )
                )
            },
            roles={
                SemanticRole.SLIDE_TITLE: Configuration(
                    typography=Typography(
                        font_size=40,
                        font_weight=FontWeight.BOLD,
                    )
                )
            },
            slides={
                SlideKind.H2: ThemeSlide(
                    elements={
                        ElementKind.HEADING: Configuration(
                            typography=Typography(
                                font_size=50,
                                font_style=FontStyle.ITALIC,
                            )
                        )
                    },
                    roles={
                        SemanticRole.SLIDE_TITLE: Configuration(
                            typography=Typography(
                                font_size=60,
                                underline=True,
                            )
                        )
                    },
                )
            },
        ),
        configurations={
            3: Configuration(
                typography=Typography(
                    font_size=70,
                    strikethrough=Strikethrough.DOUBLE,
                )
            )
        },
    )

    _, _, resolved = _resolve(source_text, layout)
    typography = _first_slide(resolved).title.configuration.typography

    assert typography.font_family == FontFamily(latin="element-font")
    assert typography.font_size == 70
    assert typography.font_weight is FontWeight.BOLD
    assert typography.font_style is FontStyle.ITALIC
    assert typography.underline is True
    assert typography.strikethrough is Strikethrough.DOUBLE


def test_explicit_false_zero_and_none_enum_survive_sparse_merge() -> None:
    source = "<!-- sj:ref=3 -->\ntext"
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(underline=True),
                    appearance=Appearance(fill=Fill(mode=FillMode.SOLID, opacity=0.75)),
                    stacking=Stacking(z_index=5),
                )
            },
            slides={
                SlideKind.IMPLICIT: ThemeSlide(
                    elements={ElementKind.PARAGRAPH: Configuration()}
                )
            },
        ),
        configurations={
            3: Configuration(
                typography=Typography(underline=False),
                appearance=Appearance(fill=Fill(mode=FillMode.NONE, opacity=0)),
                stacking=Stacking(z_index=0),
            )
        },
    )

    _, _, resolved = _resolve(source, layout)
    configuration = _first_slide(resolved).blocks[0].configuration

    assert configuration.typography.underline is False
    assert configuration.appearance.fill.mode is FillMode.NONE
    assert configuration.appearance.fill.opacity == 0
    assert configuration.stacking.z_index == 0


def test_slide_self_cascade_is_deep_and_capability_filtered() -> None:
    layout = _layout(
        theme=_theme(
            slide=Configuration(
                appearance=Appearance(
                    fill=Fill(
                        mode=FillMode.SOLID,
                        color=ThemeColor("background-1"),
                    ),
                    border=Border(style=BorderStyle.SOLID),
                ),
                placement=Placement(mode=PlacementMode.FREE, x=1),
            ),
            slides={
                SlideKind.H2: ThemeSlide(
                    self_config=Configuration(
                        appearance=Appearance(
                            fill=Fill(opacity=0.5),
                            border=Border(width=2),
                        ),
                        stacking=Stacking(z_index=9),
                    )
                )
            },
        )
    )

    _, _, resolved = _resolve("## Title", layout)
    configuration = _first_slide(resolved).configuration

    assert configuration.appearance.fill.mode is FillMode.SOLID
    assert configuration.appearance.fill.color == DirectColor("#FFFFFF")
    assert configuration.appearance.fill.opacity == 0.5
    assert configuration.appearance.border.style is BorderStyle.SOLID
    assert configuration.appearance.border.width == 2
    assert configuration.placement is None
    assert configuration.stacking is None


def test_crop_cross_layer_failure_rolls_back_only_the_upper_crop() -> None:
    source = "<!-- sj:ref=3 -->\n![image](image.png)"
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.IMAGE_BLOCK: Configuration(
                    media=ImageMedia(
                        crop=Crop(x=80, y=1, width=20, height=90),
                        fit=MediaFit.CONTAIN,
                    )
                )
            },
            slides={
                SlideKind.IMPLICIT: ThemeSlide(
                    elements={
                        ElementKind.IMAGE_BLOCK: Configuration(
                            media=ImageMedia(
                                crop=Crop(y=10, width=30),
                                fit=MediaFit.COVER,
                            )
                        )
                    }
                )
            },
        ),
        configurations={3: Configuration(media=ImageMedia(crop=Crop(x=70)))},
    )

    _, _, resolved = _resolve(source, layout)
    media = _first_slide(resolved).blocks[0].configuration.media

    assert media.crop == Crop(x=70, y=1, width=20, height=90)
    assert media.fit is MediaFit.COVER


@pytest.mark.parametrize("graph", ["missing", "mismatch", "duplicate"])
def test_m3_invalid_graph_skips_only_the_affected_source_override(
    graph: str,
) -> None:
    configurations = {}
    inline_formats = {}
    if graph in {"mismatch", "duplicate"}:
        inline_formats[3] = InlineFormatConfiguration(
            typography=InlineTypography(font_size=90)
        )
    if graph == "duplicate":
        configurations[3] = Configuration(typography=Typography(font_size=90))
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(font_size=20)
                )
            }
        ),
        configurations=configurations,
        inline_formats=inline_formats,
    )
    document = parse_markdown("<!-- sj:ref=3 -->\ntext")
    validation = validate_references(document, layout)

    resolved = resolve_presentation(document, layout, validation.index)

    assert _first_slide(resolved).blocks[0].configuration.typography.font_size == 20
    assert validation.diagnostics


@pytest.mark.parametrize("graph", ["missing", "mismatch", "duplicate"])
def test_m3_invalid_inline_graph_skips_only_the_inline_override(graph: str) -> None:
    configurations = {}
    inline_formats = {}
    if graph in {"mismatch", "duplicate"}:
        configurations[8] = Configuration(typography=Typography(font_size=90))
    if graph == "duplicate":
        inline_formats[8] = InlineFormatConfiguration(
            typography=InlineTypography(font_size=90)
        )
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(font_size=20)
                )
            }
        ),
        configurations=configurations,
        inline_formats=inline_formats,
    )
    document = parse_markdown("<sj-format ref=8>text</sj-format>")
    validation = validate_references(document, layout)

    resolved = resolve_presentation(document, layout, validation.index)
    formatted = _first_slide(resolved).blocks[0].inlines[0]

    assert formatted.style.typography.font_size == 20
    assert validation.diagnostics


def test_foreign_or_stale_reference_index_fails_before_resolution() -> None:
    first_source = parse_markdown("<!-- sj:ref=3 -->\ntext")
    second_source = parse_markdown("<!-- sj:ref=3 -->\ntext")
    first_layout = _layout(
        configurations={3: Configuration(typography=Typography(font_size=20))}
    )
    second_layout = _layout(
        configurations={3: Configuration(typography=Typography(font_size=30))}
    )
    index = validate_references(first_source, first_layout).index

    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(second_source, first_layout, index)
    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(first_source, second_layout, index)
    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(
            first_source,
            first_layout,
            ReferenceIndex(definitions=index.definitions, usages={}),
        )


def test_reference_index_with_extra_or_missing_entries_fails_fast() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\ntext")
    shared = Configuration(typography=Typography(font_size=20))
    layout = _layout(configurations={3: shared})
    index = validate_references(document, layout).index
    expanded_layout = _layout(configurations={3: shared, 4: Configuration()})
    index_with_extra_definition = validate_references(
        document,
        expanded_layout,
    ).index

    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(document, layout, index_with_extra_definition)
    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(
            document,
            layout,
            ReferenceIndex(definitions={}, usages=index.usages),
        )


def test_resolver_rejects_wrong_public_argument_types() -> None:
    document = parse_markdown("text")
    layout = _layout()
    index = validate_references(document, layout).index

    with pytest.raises(TypeError, match="SourceDocument"):
        resolve_presentation(None, layout, index)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="LayoutDocument"):
        resolve_presentation(document, None, index)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ReferenceIndex"):
        resolve_presentation(document, layout, None)  # type: ignore[arg-type]


def test_reference_index_provenance_path_does_not_make_it_stale() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\ntext")
    layout = _layout(configurations={3: Configuration()})
    index = validate_references(
        document,
        layout,
        layout_path="missing/layout.json",
    ).index

    resolved = resolve_presentation(document, layout, index)

    assert _first_slide(resolved).blocks[0].node.config_ref == 3


def test_resolver_does_not_call_public_reference_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = parse_markdown("text")
    layout = _layout()
    index = validate_references(document, layout).index

    def fail(*args, **kwargs):
        raise AssertionError("public validation must not be called")

    monkeypatch.setattr(references, "validate_references", fail)
    monkeypatch.setattr(references, "_validate_index", fail)

    assert resolve_presentation(document, layout, index).items


def test_inline_semantics_and_inline_format_follow_outer_to_inner_order() -> None:
    layout = _layout(
        inline_formats={
            8: InlineFormatConfiguration(
                typography=InlineTypography(
                    font_weight=FontWeight.REGULAR,
                    font_style=FontStyle.NORMAL,
                )
            )
        }
    )
    _, _, outer_format = _resolve(
        "<sj-format ref=8>**bold** *italic*</sj-format>",
        layout,
    )
    formatted = _first_slide(outer_format).blocks[0].inlines[0]
    strong = formatted.children[0]
    emphasis = formatted.children[2]

    assert isinstance(formatted.node, InlineFormat)
    assert formatted.style.typography.font_weight is FontWeight.REGULAR
    assert strong.style.typography.font_weight is FontWeight.BOLD
    assert emphasis.style.typography.font_style is FontStyle.ITALIC

    _, _, inner_format = _resolve("**<sj-format ref=8>x</sj-format>**", layout)
    strong_outer = _first_slide(inner_format).blocks[0].inlines[0]
    formatted_inner = strong_outer.children[0]
    assert strong_outer.style.typography.font_weight is FontWeight.BOLD
    assert formatted_inner.style.typography.font_weight is FontWeight.REGULAR


def test_script_nesting_is_scoped_and_inner_semantics_win() -> None:
    _, _, resolved = _resolve("^{outer _{inner} tail} plain", _layout())
    inlines = _first_slide(resolved).blocks[0].inlines
    superscript = inlines[0]
    subscript = superscript.children[1]

    assert superscript.style.typography.script is Script.SUPERSCRIPT
    assert subscript.style.typography.script is Script.SUBSCRIPT
    assert superscript.children[2].style.typography.script is Script.SUPERSCRIPT
    assert inlines[1].style.typography.script is None


def test_inline_code_math_and_image_apply_their_approved_capabilities() -> None:
    layout = _layout(
        inline_formats={
            8: InlineFormatConfiguration(
                typography=InlineTypography(
                    font_family=FontFamily(latin="body"),
                    font_size=18,
                    font_weight=FontWeight.BOLD,
                    color=DirectColor("#123456"),
                    underline=True,
                ),
                text_effects=TextEffects(
                    outline=Outline(color=DirectColor("#654321"), width=2)
                ),
            )
        }
    )
    source = "<sj-format ref=8>`code` \\(math\\) ![image](image.png)</sj-format>"

    _, _, resolved = _resolve(source, layout)
    formatted = _first_slide(resolved).blocks[0].inlines[0]
    code = next(
        child for child in formatted.children if isinstance(child.node, InlineCode)
    )
    math = next(
        child for child in formatted.children if isinstance(child.node, InlineMath)
    )
    image = next(
        child for child in formatted.children if isinstance(child.node, InlineImage)
    )

    assert code.style.typography == InlineTypography(font_size=18)
    assert code.style.text_effects is None
    assert math.style.typography == InlineTypography(
        font_size=18,
        color=DirectColor("#123456"),
    )
    assert math.style.text_effects.outline.width == 2
    assert image.style == ResolvedInlineStyle()


def test_resolved_models_reject_unresolved_colors_recursively() -> None:
    with pytest.raises(ValueError, match="ThemeColor"):
        ResolvedConfiguration(typography=Typography(color=ThemeColor("accent-1")))
    with pytest.raises(ValueError, match="ThemeColor"):
        ResolvedConfiguration(
            text_effects=TextEffects(
                outline=Outline(color=ThemeColor("accent-1"), width=1)
            )
        )
    with pytest.raises(ValueError, match="ThemeColor"):
        ResolvedConfiguration(
            appearance=Appearance(
                shadow=Shadow(
                    mode=ShadowMode.DROP,
                    color=ThemeColor("accent-1"),
                )
            )
        )
    assert ResolvedConfiguration(typography=Typography(color=DirectColor("#123456")))


def test_resolved_tree_constructors_reject_context_inconsistency() -> None:
    _, _, resolved = _resolve("## Title\n\n### Body\n\n`code`", _layout())
    slide = _first_slide(resolved)
    body_heading = slide.blocks[0]
    paragraph = slide.blocks[1]
    inline_code = paragraph.inlines[0]

    with pytest.raises(ValueError, match="element kind"):
        replace(body_heading, element_kind=ElementKind.PARAGRAPH)
    with pytest.raises(ValueError, match="actual Slide.title"):
        replace(
            slide,
            blocks=(
                replace(body_heading, semantic_role=SemanticRole.SLIDE_TITLE),
                paragraph,
            ),
        )
    with pytest.raises(ValueError, match="implicit"):
        replace(slide, kind=SlideKind.IMPLICIT)
    with pytest.raises(ValueError, match="InlineCode"):
        replace(
            inline_code,
            style=ResolvedInlineStyle(
                typography=InlineTypography(color=DirectColor("#123456"))
            ),
        )
    with pytest.raises(ValueError, match="unsupported configuration"):
        replace(
            body_heading,
            configuration=replace(
                body_heading.configuration,
                media=ImageMedia(aspect_ratio_locked=True, fit=MediaFit.STRETCH),
            ),
        )


def test_container_and_presentation_constructors_reject_source_mismatches() -> None:
    _, _, resolved = _resolve("# Section\n\nBody\n\n## Next", _layout())
    section = resolved.items[0]

    with pytest.raises(ValueError, match="source children"):
        replace(section.title_slide.title, inlines=())
    with pytest.raises(ValueError, match="title slide must be H1"):
        replace(section, title_slide=replace(section.title_slide, kind=SlideKind.H2))
    with pytest.raises(ValueError, match="do not match source items"):
        replace(resolved, items=())


def test_resolved_list_item_requires_the_corresponding_source_item() -> None:
    _, _, first = _resolve("- one", _layout())
    _, _, second = _resolve("- one", _layout())
    first_item = _first_slide(first).blocks[0].list_items[0]
    second_source_item = _first_slide(second).blocks[0].node.items[0]

    with pytest.raises(ValueError, match="do not match"):
        replace(first_item, node=second_source_item)


def test_resolution_is_deterministic_and_does_not_mutate_inputs() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\ntext")
    configuration = Configuration(
        typography=Typography(color=ThemeColor("accent-1"), underline=False),
        stacking=Stacking(z_index=0),
    )
    layout = _layout(configurations={3: configuration})
    index = validate_references(document, layout).index

    first = resolve_presentation(document, layout, index)
    second = resolve_presentation(document, layout, index)

    assert first == second
    assert layout.configurations[3] is configuration
    assert layout.configurations[3].typography.color == ThemeColor("accent-1")
    assert document.presentation.items[0].blocks[0].config_ref == 3
    with pytest.raises(FrozenInstanceError):
        first.items = ()  # type: ignore[misc]


def test_resolver_module_is_public_without_expanding_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "resolve_presentation")
    assert {
        "ResolvedBlock",
        "ResolvedConfiguration",
        "ResolvedInline",
        "ResolvedInlineStyle",
        "ResolvedListItem",
        "ResolvedPlacement",
        "ResolvedPlacementMode",
        "ResolvedPresentation",
        "ResolvedPresentationItem",
        "ResolvedSection",
        "ResolvedSlide",
        "resolve_presentation",
    } == set(resolver.__all__)
