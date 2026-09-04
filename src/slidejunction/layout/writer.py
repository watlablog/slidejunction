"""Canonical JSON writing for SlideJunction layout configuration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from .colors import ColorValue, DirectColor, ThemeColor
from .model import (
    Appearance,
    Border,
    CodeConfig,
    Configuration,
    Crop,
    Fill,
    FocalPoint,
    FontFamily,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    Outline,
    Placement,
    Shadow,
    Size,
    Stacking,
    TextEffects,
    Theme,
    ThemeSlide,
    Transform,
    Typography,
)


def dump_layout(document: LayoutDocument) -> str:
    """Return deterministic canonical JSON for *document*."""
    if not isinstance(document, LayoutDocument):
        raise TypeError("dump_layout() requires a LayoutDocument")

    value = {
        "format_version": document.format_version,
        "theme": _theme(document.theme),
        "configurations": {
            str(ref_id): _configuration(configuration)
            for ref_id, configuration in sorted(document.configurations.items())
        },
        "inline_formats": {
            str(ref_id): _inline_configuration(configuration)
            for ref_id, configuration in sorted(document.inline_formats.items())
        },
    }
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _theme(theme: Theme) -> dict[str, Any]:
    value: dict[str, Any] = {
        "preset": {
            "name": theme.preset.name,
            "version": theme.preset.version,
        }
    }
    if theme.colors:
        value["colors"] = {
            name: color.value for name, color in sorted(theme.colors.items())
        }
    _add_nested(value, "slide", theme.slide, _configuration)
    _add_config_mapping(value, "elements", theme.elements)
    _add_config_mapping(value, "roles", theme.roles)

    slides: dict[str, Any] = {}
    for kind, slide in sorted(theme.slides.items(), key=lambda item: item[0].value):
        serialized = _theme_slide(slide)
        if serialized:
            slides[kind.value] = serialized
    if slides:
        value["slides"] = slides
    return value


def _theme_slide(slide: ThemeSlide) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "self", slide.self_config, _configuration)
    _add_config_mapping(value, "elements", slide.elements)
    _add_config_mapping(value, "roles", slide.roles)
    return value


def _add_config_mapping(
    target: dict[str, Any],
    key: str,
    configurations: Mapping[StrEnum, Configuration],
) -> None:
    serialized: dict[str, Any] = {}
    for name, configuration in sorted(
        configurations.items(), key=lambda item: item[0].value
    ):
        value = _configuration(configuration)
        if value:
            serialized[name.value] = value
    if serialized:
        target[key] = serialized


def _configuration(configuration: Configuration) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "placement", configuration.placement, _placement)
    _add_nested(value, "size", configuration.size, _size)
    _add_nested(value, "transform", configuration.transform, _transform)
    _add_nested(value, "typography", configuration.typography, _typography)
    _add_nested(value, "text_effects", configuration.text_effects, _text_effects)
    _add_nested(value, "appearance", configuration.appearance, _appearance)
    _add_nested(value, "media", configuration.media, _media)
    _add_nested(value, "stacking", configuration.stacking, _stacking)
    _add_nested(value, "code", configuration.code, _code)
    return value


def _inline_configuration(
    configuration: InlineFormatConfiguration,
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "typography", configuration.typography, _inline_typography)
    _add_nested(value, "text_effects", configuration.text_effects, _text_effects)
    return value


def _placement(placement: Placement) -> dict[str, Any]:
    return _properties(
        ("mode", placement.mode),
        ("x", placement.x),
        ("y", placement.y),
    )


def _size(size: Size) -> dict[str, Any]:
    return _properties(("width", size.width), ("height", size.height))


def _transform(transform: Transform) -> dict[str, Any]:
    return _properties(("rotation", transform.rotation))


def _font_family(font_family: FontFamily) -> dict[str, Any]:
    return _properties(
        ("latin", font_family.latin),
        ("japanese", font_family.japanese),
    )


def _typography(typography: Typography) -> dict[str, Any]:
    value = _typography_common(typography)
    _add_property(value, "text_align", typography.text_align)
    _add_property(value, "vertical_align", typography.vertical_align)
    return value


def _inline_typography(typography: InlineTypography) -> dict[str, Any]:
    return _typography_common(typography)


def _typography_common(typography: Typography | InlineTypography) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "font_family", typography.font_family, _font_family)
    _add_property(value, "font_size", typography.font_size)
    _add_property(value, "font_weight", typography.font_weight)
    _add_property(value, "font_style", typography.font_style)
    if typography.color is not None:
        value["color"] = _color(typography.color)
    _add_property(value, "underline", typography.underline)
    _add_property(value, "strikethrough", typography.strikethrough)
    _add_property(value, "script", typography.script)
    return value


def _outline(outline: Outline) -> dict[str, Any]:
    value: dict[str, Any] = {}
    if outline.color is not None:
        value["color"] = _color(outline.color)
    _add_property(value, "width", outline.width)
    return value


def _text_effects(text_effects: TextEffects) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "outline", text_effects.outline, _outline)
    return value


def _fill(fill: Fill) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_property(value, "mode", fill.mode)
    if fill.color is not None:
        value["color"] = _color(fill.color)
    _add_property(value, "opacity", fill.opacity)
    return value


def _border(border: Border) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_property(value, "style", border.style)
    if border.color is not None:
        value["color"] = _color(border.color)
    _add_property(value, "width", border.width)
    return value


def _shadow(shadow: Shadow) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_property(value, "mode", shadow.mode)
    if shadow.color is not None:
        value["color"] = _color(shadow.color)
    _add_property(value, "opacity", shadow.opacity)
    _add_property(value, "offset_x", shadow.offset_x)
    _add_property(value, "offset_y", shadow.offset_y)
    _add_property(value, "blur", shadow.blur)
    return value


def _appearance(appearance: Appearance) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "fill", appearance.fill, _fill)
    _add_nested(value, "border", appearance.border, _border)
    _add_property(value, "corner_radius", appearance.corner_radius)
    _add_property(value, "opacity", appearance.opacity)
    _add_nested(value, "shadow", appearance.shadow, _shadow)
    return value


def _crop(crop: Crop) -> dict[str, Any]:
    return _properties(
        ("x", crop.x),
        ("y", crop.y),
        ("width", crop.width),
        ("height", crop.height),
    )


def _focal_point(focal_point: FocalPoint) -> dict[str, Any]:
    return _properties(("x", focal_point.x), ("y", focal_point.y))


def _media(media: ImageMedia) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_property(value, "aspect_ratio_locked", media.aspect_ratio_locked)
    _add_nested(value, "crop", media.crop, _crop)
    _add_property(value, "fit", media.fit)
    _add_nested(value, "focal_point", media.focal_point, _focal_point)
    return value


def _stacking(stacking: Stacking) -> dict[str, Any]:
    return _properties(("z_index", stacking.z_index))


def _code(code: CodeConfig) -> dict[str, Any]:
    return _properties(("theme", code.theme))


def _color(color: ColorValue) -> object:
    if isinstance(color, DirectColor):
        return color.value
    if isinstance(color, ThemeColor):
        return {"theme": color.theme}
    raise TypeError("Unsupported ColorValue")


def _properties(*items: tuple[str, object | None]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in items:
        _add_property(value, key, item)
    return value


def _add_property(target: dict[str, Any], key: str, value: object | None) -> None:
    if value is None:
        return
    target[key] = value.value if isinstance(value, StrEnum) else value


def _add_nested(target, key, value, serializer) -> None:
    if value is None:
        return
    serialized = serializer(value)
    if serialized:
        target[key] = serialized


__all__ = ["dump_layout"]
