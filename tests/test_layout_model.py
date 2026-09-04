from dataclasses import FrozenInstanceError

import pytest

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
    LayoutLoadResult,
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
    dump_layout,
)


def test_sparse_model_represents_every_v0_configuration_category() -> None:
    outline = Outline(color=DirectColor("#abcdef"), width=1.5)
    configuration = Configuration(
        placement=Placement(mode=PlacementMode.FREE, x=-5, y=125),
        size=Size(width=40, height=25),
        transform=Transform(rotation=725),
        typography=Typography(
            font_family=FontFamily(latin="liberation-serif", japanese="biz-udgothic"),
            font_size=24,
            font_weight=FontWeight.BOLD,
            font_style=FontStyle.ITALIC,
            color=ThemeColor("accent-1"),
            underline=False,
            strikethrough=Strikethrough.DOUBLE,
            script=Script.SUPERSCRIPT,
            text_align=TextAlign.CENTER,
            vertical_align=VerticalAlign.MIDDLE,
        ),
        text_effects=TextEffects(outline=outline),
        appearance=Appearance(
            fill=Fill(
                mode=FillMode.SOLID,
                color=DirectColor("#ffffff"),
                opacity=0.8,
            ),
            border=Border(
                style=BorderStyle.DASHED,
                color=DirectColor("#000000"),
                width=2,
            ),
            corner_radius=0,
            opacity=1,
            shadow=Shadow(
                mode=ShadowMode.DROP,
                color=DirectColor("#123456"),
                opacity=0.25,
                offset_x=-2,
                offset_y=3,
                blur=6,
            ),
        ),
        media=ImageMedia(
            aspect_ratio_locked=False,
            crop=Crop(x=10, y=5, width=70, height=90),
            fit=MediaFit.COVER,
            focal_point=FocalPoint(x=74, y=32),
        ),
        stacking=Stacking(z_index=-3),
        code=CodeConfig(theme=CodeTheme.DARK),
    )
    inline = InlineFormatConfiguration(
        typography=InlineTypography(
            font_size=18,
            color=DirectColor("#ff0000"),
            underline=True,
        ),
        text_effects=TextEffects(outline=outline),
    )
    theme_slide = ThemeSlide(
        self_config=configuration,
        elements={ElementKind.PARAGRAPH: configuration},
        roles={SemanticRole.SLIDE_TITLE: configuration},
    )
    document = LayoutDocument(
        format_version=1,
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
            colors={"warning": DirectColor("#ff3b30")},
            slide=configuration,
            elements={ElementKind.IMAGE_BLOCK: configuration},
            roles={SemanticRole.SLIDE_TITLE: configuration},
            slides={SlideKind.H1: theme_slide},
        ),
        configurations={7: configuration},
        inline_formats={8: inline},
    )

    assert document.configurations[7].placement.x == -5
    assert document.configurations[7].appearance.corner_radius == 0
    assert document.configurations[7].media.aspect_ratio_locked is False
    assert document.inline_formats[8].typography.color == DirectColor("#FF0000")
    assert document.theme.slides[SlideKind.H1] is theme_slide


def test_models_are_frozen_and_mappings_are_defensively_copied() -> None:
    definitions: dict[int, Configuration] = {3: Configuration()}
    document = LayoutDocument(
        format_version=1,
        theme=_theme(),
        configurations=definitions,
    )
    definitions[4] = Configuration()

    assert tuple(document.configurations) == (3,)
    with pytest.raises(TypeError):
        document.configurations[5] = Configuration()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        document.theme = _theme()  # type: ignore[misc]


def test_missing_properties_differ_from_explicit_off_and_zero() -> None:
    missing = Configuration()
    explicit = Configuration(
        appearance=Appearance(
            fill=Fill(mode=FillMode.NONE),
            corner_radius=0,
            opacity=0,
        ),
        media=ImageMedia(aspect_ratio_locked=False),
        stacking=Stacking(z_index=0),
    )

    assert missing.appearance is None
    assert explicit.appearance.fill.mode is FillMode.NONE
    assert explicit.appearance.corner_radius == 0
    assert explicit.appearance.opacity == 0
    assert explicit.media.aspect_ratio_locked is False
    assert explicit.stacking.z_index == 0


def test_direct_color_accepts_lowercase_and_canonicalizes_in_memory() -> None:
    assert DirectColor("#a1b2cf").value == "#A1B2CF"


@pytest.mark.parametrize(
    "value",
    ["red", "rgb(255, 0, 0)", "#ABC", "#11223344", "112233", "#GG0000"],
)
def test_direct_color_rejects_noncanonical_color_syntax(value: str) -> None:
    with pytest.raises(ValueError):
        DirectColor(value)


@pytest.mark.parametrize(
    "factory, error_type",
    [
        (lambda: Size(width=True), TypeError),
        (lambda: Size(width=float("inf")), ValueError),
        (lambda: Size(width=0), ValueError),
        (lambda: Appearance(opacity=1.1), ValueError),
        (lambda: Outline(width=0), ValueError),
        (lambda: Crop(x=100), ValueError),
        (lambda: Crop(y=100), ValueError),
        (lambda: Crop(x=80, width=30), ValueError),
        (lambda: FocalPoint(x=-1), ValueError),
        (lambda: FocalPoint(x=101), ValueError),
        (lambda: Stacking(z_index=True), TypeError),
        (lambda: Placement(mode="free"), TypeError),
    ],
)
def test_programmatic_model_validation(factory, error_type: type[Exception]) -> None:
    with pytest.raises(error_type):
        factory()


def test_crop_and_focal_point_boundary_values_are_distinct() -> None:
    crop = Crop(x=99.5, y=99.5)
    focal_point = FocalPoint(x=100, y=100)

    assert Crop(x=0, y=0).x == 0
    assert crop.x == 99.5
    assert crop.y == 99.5
    assert focal_point.x == 100
    assert focal_point.y == 100


def test_structurally_valid_unknown_preset_is_representable() -> None:
    preset = ThemePreset(name="future-preset", version=99)
    document = LayoutDocument(format_version=1, theme=Theme(preset=preset))

    assert document.theme.preset == preset


def test_layout_load_result_has_no_renderability_policy() -> None:
    result = LayoutLoadResult(document=None)

    assert not hasattr(result, "can_render")


@pytest.mark.parametrize("value", [None, LayoutLoadResult(document=None)])
def test_dump_layout_only_accepts_layout_document(value: object) -> None:
    with pytest.raises(TypeError, match="requires a LayoutDocument"):
        dump_layout(value)  # type: ignore[arg-type]


def _theme() -> Theme:
    return Theme(preset=ThemePreset(name="slidejunction-default", version=1))
