"""Pure configuration resolution for semantic SlideJunction documents."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from ._presets import _effective_preset
from .document import (
    Block,
    BlockQuote,
    CodeBlock,
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
    ListItem,
    MathBlock,
    Paragraph,
    Section,
    Slide,
    SoftBreak,
    SourceDocument,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)
from .layout import (
    Appearance,
    Border,
    CodeConfig,
    Configuration,
    Crop,
    DirectColor,
    ElementKind,
    Fill,
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
    Size,
    SlideKind,
    Stacking,
    TextAlign,
    TextEffects,
    Theme,
    ThemeColor,
    Transform,
    Typography,
    VerticalAlign,
)
from .references import (
    ReferenceIndex,
    ReferenceKind,
    _build_reference_index,
)


class ResolvedPlacementMode(StrEnum):
    """Effective placement modes, including implicit Flow placement."""

    FLOW = "flow"
    FREE = "free"


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedPlacement:
    """Effective placement state for one semantic block."""

    mode: ResolvedPlacementMode
    x: int | float | None = None
    y: int | float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ResolvedPlacementMode):
            raise TypeError("Resolved placement mode must be a ResolvedPlacementMode")
        _validate_optional_number("resolved placement x", self.x)
        _validate_optional_number("resolved placement y", self.y)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedConfiguration:
    """Capability-filtered effective configuration for a block or Slide."""

    placement: ResolvedPlacement | None = None
    size: Size | None = None
    transform: Transform | None = None
    typography: Typography | None = None
    text_effects: TextEffects | None = None
    appearance: Appearance | None = None
    media: ImageMedia | None = None
    stacking: Stacking | None = None
    code: CodeConfig | None = None

    def __post_init__(self) -> None:
        _validate_optional_instance("placement", self.placement, ResolvedPlacement)
        _validate_optional_instance("size", self.size, Size)
        _validate_optional_instance("transform", self.transform, Transform)
        _validate_optional_instance("typography", self.typography, Typography)
        _validate_optional_instance("text_effects", self.text_effects, TextEffects)
        _validate_optional_instance("appearance", self.appearance, Appearance)
        _validate_optional_instance("media", self.media, ImageMedia)
        _validate_optional_instance("stacking", self.stacking, Stacking)
        _validate_optional_instance("code", self.code, CodeConfig)
        _validate_resolved_colors(
            self.typography,
            self.text_effects,
            self.appearance,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedInlineStyle:
    """Effective formatting at one inline-tree position."""

    typography: InlineTypography = field(default_factory=InlineTypography)
    text_effects: TextEffects | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.typography, InlineTypography):
            raise TypeError("Resolved inline typography must be InlineTypography")
        _validate_optional_instance("text_effects", self.text_effects, TextEffects)
        _validate_resolved_colors(self.typography, self.text_effects, None)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedInline:
    """One source inline node with its effective style and resolved children."""

    node: Inline
    style: ResolvedInlineStyle
    children: tuple[ResolvedInline, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.node, _INLINE_TYPES):
            raise TypeError("Resolved inline node must be an Inline node")
        if not isinstance(self.style, ResolvedInlineStyle):
            raise TypeError("Resolved inline style must be ResolvedInlineStyle")
        _validate_tuple("resolved inline children", self.children, ResolvedInline)
        _validate_inline_capability(self.node, self.style)
        if isinstance(self.node, _INLINE_CONTAINER_TYPES):
            if not _nodes_match(self.node.children, self.children):
                raise ValueError(
                    "Resolved inline children do not match source children"
                )
        elif self.children:
            raise ValueError("A resolved inline leaf cannot have children")
        if isinstance(self.node, Strong):
            if self.style.typography.font_weight is not FontWeight.BOLD:
                raise ValueError("Resolved Strong must apply bold font weight")
        elif isinstance(self.node, Emphasis):
            if self.style.typography.font_style is not FontStyle.ITALIC:
                raise ValueError("Resolved Emphasis must apply italic font style")
        elif isinstance(self.node, Superscript):
            if self.style.typography.script is not Script.SUPERSCRIPT:
                raise ValueError("Resolved Superscript must apply superscript")
        elif (
            isinstance(self.node, Subscript)
            and self.style.typography.script is not Script.SUBSCRIPT
        ):
            raise ValueError("Resolved Subscript must apply subscript")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedListItem:
    """A source ListItem and its resolved block children."""

    node: ListItem
    blocks: tuple[ResolvedBlock, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.node, ListItem):
            raise TypeError("Resolved list item node must be a ListItem")
        _validate_tuple("resolved list item blocks", self.blocks, ResolvedBlock)
        if not _nodes_match(self.node.blocks, self.blocks):
            raise ValueError("Resolved list item blocks do not match source blocks")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedBlock:
    """One source block with derived context and effective configuration."""

    node: Block
    element_kind: ElementKind
    semantic_role: SemanticRole | None
    configuration: ResolvedConfiguration
    inlines: tuple[ResolvedInline, ...] = ()
    list_items: tuple[ResolvedListItem, ...] = ()
    blocks: tuple[ResolvedBlock, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.node, _BLOCK_TYPES):
            raise TypeError("Resolved block node must be a Block node")
        if not isinstance(self.element_kind, ElementKind):
            raise TypeError("Resolved block element_kind must be an ElementKind")
        if self.semantic_role is not None and not isinstance(
            self.semantic_role, SemanticRole
        ):
            raise TypeError("Resolved block role must be a SemanticRole or None")
        if not isinstance(self.configuration, ResolvedConfiguration):
            raise TypeError("Resolved block configuration is invalid")
        _validate_tuple("resolved block inlines", self.inlines, ResolvedInline)
        _validate_tuple("resolved block list items", self.list_items, ResolvedListItem)
        _validate_tuple("resolved nested blocks", self.blocks, ResolvedBlock)
        expected_kind = _element_kind(self.node)
        if self.element_kind is not expected_kind:
            raise ValueError("Resolved block element kind does not match its node")
        if self.semantic_role is not None and not isinstance(self.node, Heading):
            raise ValueError("Only a Heading can have the slide-title role")
        _validate_block_capability(self.element_kind, self.configuration)
        if isinstance(self.node, Heading | Paragraph):
            if not _nodes_match(self.node.children, self.inlines):
                raise ValueError("Resolved block inlines do not match source children")
            if self.list_items or self.blocks:
                raise ValueError("A resolved text block has invalid block children")
        elif isinstance(self.node, ListBlock):
            if not _nodes_match(self.node.items, self.list_items):
                raise ValueError("Resolved list items do not match the source list")
            if self.inlines or self.blocks:
                raise ValueError("A resolved ListBlock has invalid children")
        elif isinstance(self.node, BlockQuote):
            if not _nodes_match(self.node.blocks, self.blocks):
                raise ValueError("Resolved quote blocks do not match source blocks")
            if self.inlines or self.list_items:
                raise ValueError("A resolved BlockQuote has invalid children")
        elif self.inlines or self.list_items or self.blocks:
            raise ValueError("A resolved leaf block cannot have children")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedSlide:
    """One source Slide with its derived kind and fully resolved contents."""

    node: Slide
    kind: SlideKind
    configuration: ResolvedConfiguration
    title: ResolvedBlock | None
    blocks: tuple[ResolvedBlock, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.node, Slide):
            raise TypeError("Resolved slide node must be a Slide")
        if not isinstance(self.kind, SlideKind):
            raise TypeError("Resolved slide kind must be a SlideKind")
        if not isinstance(self.configuration, ResolvedConfiguration):
            raise TypeError("Resolved slide configuration is invalid")
        if self.title is not None and not isinstance(self.title, ResolvedBlock):
            raise TypeError("Resolved slide title must be a ResolvedBlock or None")
        _validate_tuple("resolved slide blocks", self.blocks, ResolvedBlock)
        _validate_slide_capability(self.configuration)
        if self.kind is SlideKind.IMPLICIT:
            if self.node.title is not None or self.title is not None:
                raise ValueError("An implicit resolved slide cannot have a title")
        else:
            if self.node.title is None or self.title is None:
                raise ValueError("A titled resolved slide must have a title")
            if self.title.node is not self.node.title:
                raise ValueError("Resolved slide title does not match source title")
            if (
                self.title.element_kind is not ElementKind.HEADING
                or self.title.semantic_role is not SemanticRole.SLIDE_TITLE
            ):
                raise ValueError("Resolved slide title context is inconsistent")
        if not _nodes_match(self.node.blocks, self.blocks):
            raise ValueError("Resolved slide blocks do not match source blocks")
        for block in self.blocks:
            _reject_title_role(block)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedSection:
    """A source Section and its structurally corresponding resolved slides."""

    node: Section
    title_slide: ResolvedSlide
    slides: tuple[ResolvedSlide, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.node, Section):
            raise TypeError("Resolved section node must be a Section")
        if not isinstance(self.title_slide, ResolvedSlide):
            raise TypeError("Resolved section title_slide must be a ResolvedSlide")
        _validate_tuple("resolved section slides", self.slides, ResolvedSlide)
        if self.title_slide.node is not self.node.title_slide:
            raise ValueError("Resolved section title slide does not match its source")
        if self.title_slide.kind is not SlideKind.H1:
            raise ValueError("A resolved Section title slide must be H1")
        if not _nodes_match(self.node.slides, self.slides):
            raise ValueError("Resolved section slides do not match source slides")
        if any(slide.kind is SlideKind.H1 for slide in self.slides):
            raise ValueError("A resolved Section child slide cannot be H1")


ResolvedPresentationItem: TypeAlias = ResolvedSlide | ResolvedSection


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedPresentation:
    """A source presentation paired with a complete effective-state tree."""

    source_document: SourceDocument
    items: tuple[ResolvedPresentationItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_document, SourceDocument):
            raise TypeError("Resolved presentation requires a SourceDocument")
        _validate_tuple(
            "resolved presentation items",
            self.items,
            (ResolvedSlide, ResolvedSection),
        )
        if not _nodes_match(self.source_document.presentation.items, self.items):
            raise ValueError("Resolved presentation items do not match source items")
        if any(
            isinstance(item, ResolvedSlide) and item.kind is SlideKind.H1
            for item in self.items
        ):
            raise ValueError("A top-level resolved Slide cannot be H1")


_BLOCK_KIND_BY_TYPE = {
    Heading: ElementKind.HEADING,
    Paragraph: ElementKind.PARAGRAPH,
    ListBlock: ElementKind.LIST,
    BlockQuote: ElementKind.BLOCK_QUOTE,
    CodeBlock: ElementKind.CODE_BLOCK,
    ImageBlock: ElementKind.IMAGE_BLOCK,
    MathBlock: ElementKind.MATH_BLOCK,
    ThematicBreak: ElementKind.THEMATIC_BREAK,
}
_BLOCK_TYPES = tuple(_BLOCK_KIND_BY_TYPE)
_TEXT_BLOCK_KINDS = {
    ElementKind.HEADING,
    ElementKind.PARAGRAPH,
    ElementKind.LIST,
    ElementKind.BLOCK_QUOTE,
}
_INLINE_CONTAINER_TYPES = (
    Strong,
    Emphasis,
    Link,
    InlineFormat,
    Superscript,
    Subscript,
)
_INLINE_FULL_TYPES = (
    Text,
    Strong,
    Emphasis,
    Link,
    InlineFormat,
    Superscript,
    Subscript,
    SoftBreak,
    HardBreak,
)
_INLINE_TYPES = _INLINE_FULL_TYPES + (InlineCode, InlineMath, InlineImage)

_BUILTIN_CONFIGURATION = Configuration(
    transform=Transform(rotation=0),
    typography=Typography(
        text_align=TextAlign.LEFT,
        vertical_align=VerticalAlign.TOP,
    ),
    media=ImageMedia(
        aspect_ratio_locked=True,
        fit=MediaFit.STRETCH,
    ),
    stacking=Stacking(z_index=0),
)


def resolve_presentation(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> ResolvedPresentation:
    """Resolve one immutable semantic/configuration snapshot in memory."""
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

    preset = _effective_preset(layout_document.theme.preset)
    palette = dict(preset.colors)
    palette.update(layout_document.theme.colors)
    items: list[ResolvedPresentationItem] = []
    for item in source_document.presentation.items:
        if isinstance(item, Slide):
            kind = SlideKind.IMPLICIT if item.title is None else SlideKind.H2
            items.append(
                _resolve_slide(
                    item,
                    kind,
                    layout_document,
                    reference_index,
                    preset,
                    palette,
                )
            )
        elif isinstance(item, Section):
            title_slide = _resolve_slide(
                item.title_slide,
                SlideKind.H1,
                layout_document,
                reference_index,
                preset,
                palette,
            )
            section_slides = tuple(
                _resolve_slide(
                    slide,
                    SlideKind.IMPLICIT if slide.title is None else SlideKind.H2,
                    layout_document,
                    reference_index,
                    preset,
                    palette,
                )
                for slide in item.slides
            )
            items.append(
                ResolvedSection(
                    node=item,
                    title_slide=title_slide,
                    slides=section_slides,
                )
            )
        else:  # pragma: no cover - SourceDocument model contract
            raise TypeError("Presentation contains an invalid item")
    return ResolvedPresentation(source_document=source_document, items=tuple(items))


def _resolve_slide(
    slide: Slide,
    kind: SlideKind,
    layout: LayoutDocument,
    references: ReferenceIndex,
    preset: Theme,
    palette: dict[str, DirectColor],
) -> ResolvedSlide:
    configuration = _resolve_slide_configuration(
        kind,
        layout.theme,
        preset,
        palette,
    )
    title = (
        None
        if slide.title is None
        else _resolve_block(
            slide.title,
            kind,
            SemanticRole.SLIDE_TITLE,
            layout,
            references,
            preset,
            palette,
            inherited=None,
        )
    )
    blocks = tuple(
        _resolve_block(
            block,
            kind,
            None,
            layout,
            references,
            preset,
            palette,
            inherited=None,
        )
        for block in slide.blocks
    )
    return ResolvedSlide(
        node=slide,
        kind=kind,
        configuration=configuration,
        title=title,
        blocks=blocks,
    )


def _resolve_block(
    block: Block,
    slide_kind: SlideKind,
    role: SemanticRole | None,
    layout: LayoutDocument,
    references: ReferenceIndex,
    preset: Theme,
    palette: dict[str, DirectColor],
    *,
    inherited: Configuration | None,
) -> ResolvedBlock:
    element_kind = _element_kind(block)
    configuration = _resolve_block_configuration(
        block,
        element_kind,
        slide_kind,
        role,
        layout,
        references,
        preset,
        palette,
        inherited,
    )
    inlines: tuple[ResolvedInline, ...] = ()
    list_items: tuple[ResolvedListItem, ...] = ()
    blocks: tuple[ResolvedBlock, ...] = ()
    if isinstance(block, Heading | Paragraph):
        base_style = _inline_base_style(configuration)
        inlines = _resolve_inlines(block.children, base_style, references, palette)
    elif isinstance(block, ListBlock):
        child_inheritance = _inherited_text_configuration(configuration)
        list_items = tuple(
            ResolvedListItem(
                node=item,
                blocks=tuple(
                    _resolve_block(
                        child,
                        slide_kind,
                        None,
                        layout,
                        references,
                        preset,
                        palette,
                        inherited=child_inheritance,
                    )
                    for child in item.blocks
                ),
            )
            for item in block.items
        )
    elif isinstance(block, BlockQuote):
        child_inheritance = _inherited_text_configuration(configuration)
        blocks = tuple(
            _resolve_block(
                child,
                slide_kind,
                None,
                layout,
                references,
                preset,
                palette,
                inherited=child_inheritance,
            )
            for child in block.blocks
        )
    return ResolvedBlock(
        node=block,
        element_kind=element_kind,
        semantic_role=role,
        configuration=configuration,
        inlines=inlines,
        list_items=list_items,
        blocks=blocks,
    )


def _resolve_slide_configuration(
    kind: SlideKind,
    theme: Theme,
    preset: Theme,
    palette: dict[str, DirectColor],
) -> ResolvedConfiguration:
    effective = Configuration()
    preset_slide = preset.slides.get(kind)
    project_slide = theme.slides.get(kind)
    layers = (
        preset.slide,
        None if preset_slide is None else preset_slide.self_config,
        theme.slide,
        None if project_slide is None else project_slide.self_config,
    )
    for layer in layers:
        if layer is not None:
            effective = _merge_configuration(
                effective,
                _resolve_configuration_colors(layer, palette),
            )
    return ResolvedConfiguration(appearance=effective.appearance)


def _resolve_block_configuration(
    block: Block,
    element_kind: ElementKind,
    slide_kind: SlideKind,
    role: SemanticRole | None,
    layout: LayoutDocument,
    references: ReferenceIndex,
    preset: Theme,
    palette: dict[str, DirectColor],
    inherited: Configuration | None,
) -> ResolvedConfiguration:
    effective = _BUILTIN_CONFIGURATION
    layers: list[Configuration | None] = [inherited]
    layers.extend(_theme_layers(preset, slide_kind, element_kind, role))
    layers.extend(_theme_layers(layout.theme, slide_kind, element_kind, role))
    layers.append(_configuration_definition(block, references))
    for layer in layers:
        if layer is not None:
            effective = _merge_configuration(
                effective,
                _resolve_configuration_colors(layer, palette),
            )
    return _filter_block_configuration(effective, element_kind)


def _theme_layers(
    theme: Theme,
    slide_kind: SlideKind,
    element_kind: ElementKind,
    role: SemanticRole | None,
) -> tuple[Configuration | None, ...]:
    slide = theme.slides.get(slide_kind)
    return (
        theme.elements.get(element_kind),
        None if role is None else theme.roles.get(role),
        None if slide is None else slide.elements.get(element_kind),
        None if slide is None or role is None else slide.roles.get(role),
    )


def _configuration_definition(
    block: Block,
    index: ReferenceIndex,
) -> Configuration | None:
    if block.config_ref is None:
        return None
    definition = _usable_definition(
        block.config_ref,
        ReferenceKind.CONFIGURATION,
        block,
        index,
    )
    if definition is None:
        return None
    if not isinstance(definition, Configuration):  # pragma: no cover - invariant
        raise TypeError("Configuration reference has an invalid value")
    return definition


def _inline_definition(
    inline: InlineFormat,
    index: ReferenceIndex,
) -> InlineFormatConfiguration | None:
    definition = _usable_definition(
        inline.config_ref,
        ReferenceKind.INLINE_FORMAT,
        inline,
        index,
    )
    if definition is None:
        return None
    if not isinstance(definition, InlineFormatConfiguration):  # pragma: no cover
        raise TypeError("Inline-format reference has an invalid value")
    return definition


def _usable_definition(ref_id, kind, consumer, index):
    usages = index.usages_for(ref_id, kind=kind)
    if not any(usage.consumer is consumer for usage in usages):
        return None
    definitions = index.definitions_for(ref_id)
    if len(definitions) != 1 or definitions[0].kind is not kind:
        return None
    return definitions[0].value


def _resolve_inlines(
    nodes: tuple[Inline, ...],
    parent_style: ResolvedInlineStyle,
    references: ReferenceIndex,
    palette: dict[str, DirectColor],
) -> tuple[ResolvedInline, ...]:
    return tuple(
        _resolve_inline(node, parent_style, references, palette) for node in nodes
    )


def _resolve_inline(
    node: Inline,
    parent_style: ResolvedInlineStyle,
    references: ReferenceIndex,
    palette: dict[str, DirectColor],
) -> ResolvedInline:
    style = parent_style
    semantic: InlineFormatConfiguration | None = None
    if isinstance(node, Strong):
        semantic = InlineFormatConfiguration(
            typography=InlineTypography(font_weight=FontWeight.BOLD)
        )
    elif isinstance(node, Emphasis):
        semantic = InlineFormatConfiguration(
            typography=InlineTypography(font_style=FontStyle.ITALIC)
        )
    elif isinstance(node, Superscript):
        semantic = InlineFormatConfiguration(
            typography=InlineTypography(script=Script.SUPERSCRIPT)
        )
    elif isinstance(node, Subscript):
        semantic = InlineFormatConfiguration(
            typography=InlineTypography(script=Script.SUBSCRIPT)
        )
    elif isinstance(node, InlineFormat):
        semantic = _inline_definition(node, references)
    if semantic is not None:
        style = _merge_inline_style(
            style,
            _resolve_inline_configuration_colors(semantic, palette),
        )
    node_style = _filter_inline_style(style, node)
    children = (
        _resolve_inlines(node.children, node_style, references, palette)
        if isinstance(node, _INLINE_CONTAINER_TYPES)
        else ()
    )
    return ResolvedInline(node=node, style=node_style, children=children)


def _inline_base_style(configuration: ResolvedConfiguration) -> ResolvedInlineStyle:
    typography = configuration.typography
    return ResolvedInlineStyle(
        typography=InlineTypography(
            font_family=None if typography is None else typography.font_family,
            font_size=None if typography is None else typography.font_size,
            font_weight=None if typography is None else typography.font_weight,
            font_style=None if typography is None else typography.font_style,
            color=None if typography is None else typography.color,
            underline=None if typography is None else typography.underline,
            strikethrough=None if typography is None else typography.strikethrough,
            script=None if typography is None else typography.script,
        ),
        text_effects=configuration.text_effects,
    )


def _inherited_text_configuration(
    configuration: ResolvedConfiguration,
) -> Configuration:
    typography = configuration.typography
    inherited_typography = None
    if typography is not None:
        inherited_typography = _compact_typography(
            Typography(
                font_family=typography.font_family,
                font_size=typography.font_size,
                font_weight=typography.font_weight,
                font_style=typography.font_style,
                color=typography.color,
                underline=typography.underline,
                strikethrough=typography.strikethrough,
                script=typography.script,
                text_align=typography.text_align,
                vertical_align=None,
            )
        )
    return Configuration(
        typography=inherited_typography,
        text_effects=configuration.text_effects,
    )


def _filter_block_configuration(
    configuration: Configuration,
    kind: ElementKind,
) -> ResolvedConfiguration:
    common = {
        "placement": _resolved_placement(configuration.placement),
        "size": configuration.size,
        "transform": configuration.transform,
        "appearance": configuration.appearance,
        "stacking": configuration.stacking,
    }
    typography = None
    text_effects = None
    media = None
    code = None
    if kind in _TEXT_BLOCK_KINDS:
        typography = configuration.typography
        text_effects = configuration.text_effects
    elif kind is ElementKind.CODE_BLOCK:
        if configuration.typography is not None:
            typography = _compact_typography(
                Typography(font_size=configuration.typography.font_size)
            )
        code = configuration.code
    elif kind is ElementKind.IMAGE_BLOCK:
        media = configuration.media
    elif kind is ElementKind.MATH_BLOCK:
        if configuration.typography is not None:
            typography = _compact_typography(
                Typography(
                    font_size=configuration.typography.font_size,
                    color=configuration.typography.color,
                )
            )
        text_effects = configuration.text_effects
    return ResolvedConfiguration(
        **common,
        typography=typography,
        text_effects=text_effects,
        media=media,
        code=code,
    )


def _filter_inline_style(
    style: ResolvedInlineStyle,
    node: Inline,
) -> ResolvedInlineStyle:
    if isinstance(node, _INLINE_FULL_TYPES):
        return style
    typography = style.typography
    if isinstance(node, InlineCode):
        return ResolvedInlineStyle(
            typography=InlineTypography(font_size=typography.font_size)
        )
    if isinstance(node, InlineMath):
        return ResolvedInlineStyle(
            typography=InlineTypography(
                font_size=typography.font_size,
                color=typography.color,
            ),
            text_effects=style.text_effects,
        )
    if isinstance(node, InlineImage):
        return ResolvedInlineStyle()
    raise TypeError("Unknown inline node")


def _resolved_placement(placement: Placement | None) -> ResolvedPlacement:
    return ResolvedPlacement(
        mode=(
            ResolvedPlacementMode.FREE
            if placement is not None and placement.mode is PlacementMode.FREE
            else ResolvedPlacementMode.FLOW
        ),
        x=None if placement is None else placement.x,
        y=None if placement is None else placement.y,
    )


def _merge_configuration(
    lower: Configuration,
    upper: Configuration,
) -> Configuration:
    return Configuration(
        placement=_merge_placement(lower.placement, upper.placement),
        size=_merge_size(lower.size, upper.size),
        transform=_merge_transform(lower.transform, upper.transform),
        typography=_merge_typography(lower.typography, upper.typography),
        text_effects=_merge_text_effects(lower.text_effects, upper.text_effects),
        appearance=_merge_appearance(lower.appearance, upper.appearance),
        media=_merge_media(lower.media, upper.media),
        stacking=_merge_stacking(lower.stacking, upper.stacking),
        code=_merge_code(lower.code, upper.code),
    )


def _merge_inline_style(
    lower: ResolvedInlineStyle,
    upper: InlineFormatConfiguration,
) -> ResolvedInlineStyle:
    return ResolvedInlineStyle(
        typography=(
            _merge_inline_typography(lower.typography, upper.typography)
            or InlineTypography()
        ),
        text_effects=_merge_text_effects(lower.text_effects, upper.text_effects),
    )


def _merge_placement(lower, upper):
    if upper is None:
        return lower
    lower = lower or Placement()
    result = Placement(
        mode=_choose(lower.mode, upper.mode),
        x=_choose(lower.x, upper.x),
        y=_choose(lower.y, upper.y),
    )
    return None if result == Placement() else result


def _merge_size(lower, upper):
    if upper is None:
        return lower
    lower = lower or Size()
    result = Size(
        width=_choose(lower.width, upper.width),
        height=_choose(lower.height, upper.height),
    )
    return None if result == Size() else result


def _merge_transform(lower, upper):
    if upper is None:
        return lower
    lower = lower or Transform()
    result = Transform(rotation=_choose(lower.rotation, upper.rotation))
    return None if result == Transform() else result


def _merge_font_family(lower, upper):
    if upper is None:
        return lower
    lower = lower or FontFamily()
    result = FontFamily(
        latin=_choose(lower.latin, upper.latin),
        japanese=_choose(lower.japanese, upper.japanese),
    )
    return None if result == FontFamily() else result


def _merge_typography(lower, upper):
    if upper is None:
        return lower
    lower = lower or Typography()
    result = Typography(
        font_family=_merge_font_family(lower.font_family, upper.font_family),
        font_size=_choose(lower.font_size, upper.font_size),
        font_weight=_choose(lower.font_weight, upper.font_weight),
        font_style=_choose(lower.font_style, upper.font_style),
        color=_choose(lower.color, upper.color),
        underline=_choose(lower.underline, upper.underline),
        strikethrough=_choose(lower.strikethrough, upper.strikethrough),
        script=_choose(lower.script, upper.script),
        text_align=_choose(lower.text_align, upper.text_align),
        vertical_align=_choose(lower.vertical_align, upper.vertical_align),
    )
    return _compact_typography(result)


def _merge_inline_typography(lower, upper):
    if upper is None:
        return lower
    lower = lower or InlineTypography()
    result = InlineTypography(
        font_family=_merge_font_family(lower.font_family, upper.font_family),
        font_size=_choose(lower.font_size, upper.font_size),
        font_weight=_choose(lower.font_weight, upper.font_weight),
        font_style=_choose(lower.font_style, upper.font_style),
        color=_choose(lower.color, upper.color),
        underline=_choose(lower.underline, upper.underline),
        strikethrough=_choose(lower.strikethrough, upper.strikethrough),
        script=_choose(lower.script, upper.script),
    )
    return None if result == InlineTypography() else result


def _merge_outline(lower, upper):
    if upper is None:
        return lower
    lower = lower or Outline()
    result = Outline(
        color=_choose(lower.color, upper.color),
        width=_choose(lower.width, upper.width),
    )
    return None if result == Outline() else result


def _merge_text_effects(lower, upper):
    if upper is None:
        return lower
    lower = lower or TextEffects()
    result = TextEffects(outline=_merge_outline(lower.outline, upper.outline))
    return None if result == TextEffects() else result


def _merge_fill(lower, upper):
    if upper is None:
        return lower
    lower = lower or Fill()
    result = Fill(
        mode=_choose(lower.mode, upper.mode),
        color=_choose(lower.color, upper.color),
        opacity=_choose(lower.opacity, upper.opacity),
    )
    return None if result == Fill() else result


def _merge_border(lower, upper):
    if upper is None:
        return lower
    lower = lower or Border()
    result = Border(
        style=_choose(lower.style, upper.style),
        color=_choose(lower.color, upper.color),
        width=_choose(lower.width, upper.width),
    )
    return None if result == Border() else result


def _merge_shadow(lower, upper):
    if upper is None:
        return lower
    lower = lower or Shadow()
    result = Shadow(
        mode=_choose(lower.mode, upper.mode),
        color=_choose(lower.color, upper.color),
        opacity=_choose(lower.opacity, upper.opacity),
        offset_x=_choose(lower.offset_x, upper.offset_x),
        offset_y=_choose(lower.offset_y, upper.offset_y),
        blur=_choose(lower.blur, upper.blur),
    )
    return None if result == Shadow() else result


def _merge_appearance(lower, upper):
    if upper is None:
        return lower
    lower = lower or Appearance()
    result = Appearance(
        fill=_merge_fill(lower.fill, upper.fill),
        border=_merge_border(lower.border, upper.border),
        corner_radius=_choose(lower.corner_radius, upper.corner_radius),
        opacity=_choose(lower.opacity, upper.opacity),
        shadow=_merge_shadow(lower.shadow, upper.shadow),
    )
    return None if result == Appearance() else result


def _merge_crop(lower, upper):
    if upper is None:
        return lower
    lower = lower or Crop()
    try:
        result = Crop(
            x=_choose(lower.x, upper.x),
            y=_choose(lower.y, upper.y),
            width=_choose(lower.width, upper.width),
            height=_choose(lower.height, upper.height),
        )
    except ValueError:
        return None if lower == Crop() else lower
    return None if result == Crop() else result


def _merge_focal_point(lower, upper):
    if upper is None:
        return lower
    lower = lower or FocalPoint()
    result = FocalPoint(
        x=_choose(lower.x, upper.x),
        y=_choose(lower.y, upper.y),
    )
    return None if result == FocalPoint() else result


def _merge_media(lower, upper):
    if upper is None:
        return lower
    lower = lower or ImageMedia()
    result = ImageMedia(
        aspect_ratio_locked=_choose(
            lower.aspect_ratio_locked,
            upper.aspect_ratio_locked,
        ),
        crop=_merge_crop(lower.crop, upper.crop),
        fit=_choose(lower.fit, upper.fit),
        focal_point=_merge_focal_point(lower.focal_point, upper.focal_point),
    )
    return None if result == ImageMedia() else result


def _merge_stacking(lower, upper):
    if upper is None:
        return lower
    lower = lower or Stacking()
    result = Stacking(z_index=_choose(lower.z_index, upper.z_index))
    return None if result == Stacking() else result


def _merge_code(lower, upper):
    if upper is None:
        return lower
    lower = lower or CodeConfig()
    result = CodeConfig(theme=_choose(lower.theme, upper.theme))
    return None if result == CodeConfig() else result


def _resolve_configuration_colors(
    configuration: Configuration,
    palette: dict[str, DirectColor],
) -> Configuration:
    return Configuration(
        placement=configuration.placement,
        size=configuration.size,
        transform=configuration.transform,
        typography=_resolve_typography_colors(configuration.typography, palette),
        text_effects=_resolve_text_effect_colors(
            configuration.text_effects,
            palette,
        ),
        appearance=_resolve_appearance_colors(configuration.appearance, palette),
        media=configuration.media,
        stacking=configuration.stacking,
        code=configuration.code,
    )


def _resolve_inline_configuration_colors(
    configuration: InlineFormatConfiguration,
    palette: dict[str, DirectColor],
) -> InlineFormatConfiguration:
    return InlineFormatConfiguration(
        typography=_resolve_inline_typography_colors(
            configuration.typography,
            palette,
        ),
        text_effects=_resolve_text_effect_colors(
            configuration.text_effects,
            palette,
        ),
    )


def _resolve_typography_colors(typography, palette):
    if typography is None:
        return None
    return _compact_typography(
        Typography(
            font_family=typography.font_family,
            font_size=typography.font_size,
            font_weight=typography.font_weight,
            font_style=typography.font_style,
            color=_resolve_color(typography.color, palette),
            underline=typography.underline,
            strikethrough=typography.strikethrough,
            script=typography.script,
            text_align=typography.text_align,
            vertical_align=typography.vertical_align,
        )
    )


def _resolve_inline_typography_colors(typography, palette):
    if typography is None:
        return None
    result = InlineTypography(
        font_family=typography.font_family,
        font_size=typography.font_size,
        font_weight=typography.font_weight,
        font_style=typography.font_style,
        color=_resolve_color(typography.color, palette),
        underline=typography.underline,
        strikethrough=typography.strikethrough,
        script=typography.script,
    )
    return None if result == InlineTypography() else result


def _resolve_text_effect_colors(text_effects, palette):
    if text_effects is None or text_effects.outline is None:
        return text_effects
    outline = Outline(
        color=_resolve_color(text_effects.outline.color, palette),
        width=text_effects.outline.width,
    )
    return TextEffects(outline=None if outline == Outline() else outline)


def _resolve_appearance_colors(appearance, palette):
    if appearance is None:
        return None
    fill = appearance.fill
    border = appearance.border
    shadow = appearance.shadow
    return Appearance(
        fill=(
            None
            if fill is None
            else Fill(
                mode=fill.mode,
                color=_resolve_color(fill.color, palette),
                opacity=fill.opacity,
            )
        ),
        border=(
            None
            if border is None
            else Border(
                style=border.style,
                color=_resolve_color(border.color, palette),
                width=border.width,
            )
        ),
        corner_radius=appearance.corner_radius,
        opacity=appearance.opacity,
        shadow=(
            None
            if shadow is None
            else Shadow(
                mode=shadow.mode,
                color=_resolve_color(shadow.color, palette),
                opacity=shadow.opacity,
                offset_x=shadow.offset_x,
                offset_y=shadow.offset_y,
                blur=shadow.blur,
            )
        ),
    )


def _resolve_color(color, palette):
    if color is None or isinstance(color, DirectColor):
        return color
    if isinstance(color, ThemeColor):
        return palette.get(color.theme)
    raise TypeError("Configuration contains an invalid color value")


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


def _element_kind(block: Block) -> ElementKind:
    try:
        return _BLOCK_KIND_BY_TYPE[type(block)]
    except KeyError as error:
        raise TypeError("Unknown block node") from error


def _validate_block_capability(
    kind: ElementKind,
    configuration: ResolvedConfiguration,
) -> None:
    if (
        configuration.placement is None
        or configuration.transform is None
        or configuration.transform.rotation is None
        or configuration.stacking is None
        or configuration.stacking.z_index is None
    ):
        raise ValueError("Resolved block configuration is missing built-in defaults")
    if kind in _TEXT_BLOCK_KINDS:
        if configuration.typography is None:
            raise ValueError("Resolved text block is missing typography defaults")
        if (
            configuration.typography.text_align is None
            or configuration.typography.vertical_align is None
        ):
            raise ValueError("Resolved text block is missing alignment defaults")
        if configuration.media is not None or configuration.code is not None:
            raise ValueError("Resolved text block has unsupported configuration")
        return
    if kind is ElementKind.CODE_BLOCK:
        if not _typography_uses_only(configuration.typography, {"font_size"}):
            raise ValueError("Resolved CodeBlock has unsupported typography")
        if configuration.text_effects is not None or configuration.media is not None:
            raise ValueError("Resolved CodeBlock has unsupported configuration")
        return
    if kind is ElementKind.IMAGE_BLOCK:
        if (
            configuration.typography is not None
            or configuration.text_effects is not None
        ):
            raise ValueError("Resolved ImageBlock has unsupported text configuration")
        if configuration.media is None:
            raise ValueError("Resolved ImageBlock is missing media defaults")
        if (
            configuration.media.aspect_ratio_locked is None
            or configuration.media.fit is None
        ):
            raise ValueError("Resolved ImageBlock is missing media defaults")
        if configuration.code is not None:
            raise ValueError("Resolved ImageBlock has unsupported code configuration")
        return
    if kind is ElementKind.MATH_BLOCK:
        if not _typography_uses_only(
            configuration.typography,
            {"font_size", "color"},
        ):
            raise ValueError("Resolved MathBlock has unsupported typography")
        if configuration.media is not None or configuration.code is not None:
            raise ValueError("Resolved MathBlock has unsupported configuration")
        return
    if kind is ElementKind.THEMATIC_BREAK:
        if (
            configuration.typography is not None
            or configuration.text_effects is not None
            or configuration.media is not None
            or configuration.code is not None
        ):
            raise ValueError("Resolved ThematicBreak has unsupported configuration")
        return
    raise ValueError("Unknown resolved block capability")


def _validate_slide_capability(configuration: ResolvedConfiguration) -> None:
    if any(
        value is not None
        for value in (
            configuration.placement,
            configuration.size,
            configuration.transform,
            configuration.typography,
            configuration.text_effects,
            configuration.media,
            configuration.stacking,
            configuration.code,
        )
    ):
        raise ValueError("Resolved Slide self configuration only supports appearance")


def _validate_inline_capability(node: Inline, style: ResolvedInlineStyle) -> None:
    typography = style.typography
    if isinstance(node, _INLINE_FULL_TYPES):
        return
    if isinstance(node, InlineCode):
        if not _inline_typography_uses_only(typography, {"font_size"}):
            raise ValueError("Resolved InlineCode has unsupported typography")
        if style.text_effects is not None:
            raise ValueError("Resolved InlineCode cannot have text effects")
        return
    if isinstance(node, InlineMath):
        if not _inline_typography_uses_only(typography, {"font_size", "color"}):
            raise ValueError("Resolved InlineMath has unsupported typography")
        return
    if isinstance(node, InlineImage):
        if typography != InlineTypography() or style.text_effects is not None:
            raise ValueError("Resolved InlineImage cannot have inline styling")
        return
    raise ValueError("Unknown resolved inline capability")


def _typography_uses_only(
    typography: Typography | None,
    allowed: set[str],
) -> bool:
    if typography is None:
        return True
    fields = {
        "font_family": typography.font_family,
        "font_size": typography.font_size,
        "font_weight": typography.font_weight,
        "font_style": typography.font_style,
        "color": typography.color,
        "underline": typography.underline,
        "strikethrough": typography.strikethrough,
        "script": typography.script,
        "text_align": typography.text_align,
        "vertical_align": typography.vertical_align,
    }
    return all(value is None or name in allowed for name, value in fields.items())


def _inline_typography_uses_only(
    typography: InlineTypography,
    allowed: set[str],
) -> bool:
    fields = {
        "font_family": typography.font_family,
        "font_size": typography.font_size,
        "font_weight": typography.font_weight,
        "font_style": typography.font_style,
        "color": typography.color,
        "underline": typography.underline,
        "strikethrough": typography.strikethrough,
        "script": typography.script,
    }
    return all(value is None or name in allowed for name, value in fields.items())


def _validate_resolved_colors(typography, text_effects, appearance) -> None:
    colors = []
    if typography is not None:
        colors.append(typography.color)
    if text_effects is not None and text_effects.outline is not None:
        colors.append(text_effects.outline.color)
    if appearance is not None:
        if appearance.fill is not None:
            colors.append(appearance.fill.color)
        if appearance.border is not None:
            colors.append(appearance.border.color)
        if appearance.shadow is not None:
            colors.append(appearance.shadow.color)
    if any(isinstance(color, ThemeColor) for color in colors):
        raise ValueError("Resolved models cannot contain unresolved ThemeColor values")
    if not all(color is None or isinstance(color, DirectColor) for color in colors):
        raise TypeError("Resolved models contain an invalid color value")


def _reject_title_role(block: ResolvedBlock) -> None:
    if block.semantic_role is not None:
        raise ValueError("Only the actual Slide.title can have a semantic role")
    for item in block.list_items:
        for child in item.blocks:
            _reject_title_role(child)
    for child in block.blocks:
        _reject_title_role(child)


def _nodes_match(source_nodes, resolved_nodes) -> bool:
    return len(source_nodes) == len(resolved_nodes) and all(
        resolved.node is source
        for source, resolved in zip(source_nodes, resolved_nodes, strict=True)
    )


def _validate_tuple(name, value, expected) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    if not all(isinstance(item, expected) for item in value):
        raise TypeError(f"{name} contain an invalid item")


def _validate_optional_instance(name, value, expected) -> None:
    if value is not None and not isinstance(value, expected):
        raise TypeError(f"Resolved {name} has an invalid type")


def _validate_optional_number(name, value) -> None:
    if value is None:
        return
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _choose(lower, upper):
    return lower if upper is None else upper


def _compact_typography(typography: Typography) -> Typography | None:
    return None if typography == Typography() else typography


__all__ = [
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
]
