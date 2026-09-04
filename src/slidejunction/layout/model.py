"""Immutable sparse models for SlideJunction layout configuration."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TypeAlias, TypeVar

from ..document import Diagnostic
from .colors import ColorValue, DirectColor, ThemeColor, is_valid_theme_token_name

Number: TypeAlias = int | float


class PlacementMode(StrEnum):
    """Persistent placement modes."""

    FREE = "free"


class FontWeight(StrEnum):
    """Supported font weights."""

    REGULAR = "regular"
    BOLD = "bold"


class FontStyle(StrEnum):
    """Supported font styles."""

    NORMAL = "normal"
    ITALIC = "italic"


class Strikethrough(StrEnum):
    """Supported strikethrough modes."""

    NONE = "none"
    SINGLE = "single"
    DOUBLE = "double"


class Script(StrEnum):
    """Supported typographic scripts."""

    NORMAL = "normal"
    SUPERSCRIPT = "superscript"
    SUBSCRIPT = "subscript"


class TextAlign(StrEnum):
    """Supported horizontal text alignment values."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class VerticalAlign(StrEnum):
    """Supported vertical text alignment values."""

    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class FillMode(StrEnum):
    """Supported object fill modes."""

    NONE = "none"
    SOLID = "solid"


class BorderStyle(StrEnum):
    """Supported border styles."""

    NONE = "none"
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class ShadowMode(StrEnum):
    """Supported object shadow modes."""

    NONE = "none"
    DROP = "drop"


class MediaFit(StrEnum):
    """Supported ImageBlock fitting modes."""

    STRETCH = "stretch"
    CONTAIN = "contain"
    COVER = "cover"


class CodeTheme(StrEnum):
    """Supported CodeBlock syntax themes."""

    LIGHT = "light"
    DARK = "dark"


class SlideKind(StrEnum):
    """Semantic slide kinds used by the theme cascade."""

    H1 = "h1"
    H2 = "h2"
    IMPLICIT = "implicit"


class ElementKind(StrEnum):
    """Semantic block element kinds used by the theme cascade."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    BLOCK_QUOTE = "block-quote"
    CODE_BLOCK = "code-block"
    IMAGE_BLOCK = "image-block"
    MATH_BLOCK = "math-block"
    THEMATIC_BREAK = "thematic-break"


class SemanticRole(StrEnum):
    """Semantic roles supported by Configuration v0."""

    SLIDE_TITLE = "slide-title"


@dataclass(frozen=True, slots=True, kw_only=True)
class Placement:
    """Sparse placement override."""

    mode: PlacementMode | None = None
    x: Number | None = None
    y: Number | None = None

    def __post_init__(self) -> None:
        _optional_enum("placement.mode", self.mode, PlacementMode)
        _optional_number("placement.x", self.x)
        _optional_number("placement.y", self.y)


@dataclass(frozen=True, slots=True, kw_only=True)
class Size:
    """Sparse untransformed border-box size override."""

    width: Number | None = None
    height: Number | None = None

    def __post_init__(self) -> None:
        _optional_number("size.width", self.width, minimum=0, minimum_exclusive=True)
        _optional_number("size.height", self.height, minimum=0, minimum_exclusive=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class Transform:
    """Sparse transform override."""

    rotation: Number | None = None

    def __post_init__(self) -> None:
        _optional_number("transform.rotation", self.rotation)


@dataclass(frozen=True, slots=True, kw_only=True)
class FontFamily:
    """Sparse Latin/Japanese font selection."""

    latin: str | None = None
    japanese: str | None = None

    def __post_init__(self) -> None:
        _optional_non_empty_string("font_family.latin", self.latin)
        _optional_non_empty_string("font_family.japanese", self.japanese)


@dataclass(frozen=True, slots=True, kw_only=True)
class Typography:
    """Sparse object typography override."""

    font_family: FontFamily | None = None
    font_size: Number | None = None
    font_weight: FontWeight | None = None
    font_style: FontStyle | None = None
    color: ColorValue | None = None
    underline: bool | None = None
    strikethrough: Strikethrough | None = None
    script: Script | None = None
    text_align: TextAlign | None = None
    vertical_align: VerticalAlign | None = None

    def __post_init__(self) -> None:
        _optional_instance("typography.font_family", self.font_family, FontFamily)
        _optional_number(
            "typography.font_size", self.font_size, minimum=0, minimum_exclusive=True
        )
        _optional_enum("typography.font_weight", self.font_weight, FontWeight)
        _optional_enum("typography.font_style", self.font_style, FontStyle)
        _optional_color("typography.color", self.color)
        _optional_bool("typography.underline", self.underline)
        _optional_enum("typography.strikethrough", self.strikethrough, Strikethrough)
        _optional_enum("typography.script", self.script, Script)
        _optional_enum("typography.text_align", self.text_align, TextAlign)
        _optional_enum("typography.vertical_align", self.vertical_align, VerticalAlign)


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineTypography:
    """Sparse typography subset allowed for InlineFormat."""

    font_family: FontFamily | None = None
    font_size: Number | None = None
    font_weight: FontWeight | None = None
    font_style: FontStyle | None = None
    color: ColorValue | None = None
    underline: bool | None = None
    strikethrough: Strikethrough | None = None
    script: Script | None = None

    def __post_init__(self) -> None:
        _optional_instance("typography.font_family", self.font_family, FontFamily)
        _optional_number(
            "typography.font_size", self.font_size, minimum=0, minimum_exclusive=True
        )
        _optional_enum("typography.font_weight", self.font_weight, FontWeight)
        _optional_enum("typography.font_style", self.font_style, FontStyle)
        _optional_color("typography.color", self.color)
        _optional_bool("typography.underline", self.underline)
        _optional_enum("typography.strikethrough", self.strikethrough, Strikethrough)
        _optional_enum("typography.script", self.script, Script)


@dataclass(frozen=True, slots=True, kw_only=True)
class Outline:
    """Sparse glyph outline paint."""

    color: ColorValue | None = None
    width: Number | None = None

    def __post_init__(self) -> None:
        _optional_color("outline.color", self.color)
        _optional_number("outline.width", self.width, minimum=0, minimum_exclusive=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class TextEffects:
    """Sparse text paint effects."""

    outline: Outline | None = None

    def __post_init__(self) -> None:
        _optional_instance("text_effects.outline", self.outline, Outline)


@dataclass(frozen=True, slots=True, kw_only=True)
class Fill:
    """Sparse object fill override."""

    mode: FillMode | None = None
    color: ColorValue | None = None
    opacity: Number | None = None

    def __post_init__(self) -> None:
        _optional_enum("fill.mode", self.mode, FillMode)
        _optional_color("fill.color", self.color)
        _optional_number("fill.opacity", self.opacity, minimum=0, maximum=1)


@dataclass(frozen=True, slots=True, kw_only=True)
class Border:
    """Sparse object border override."""

    style: BorderStyle | None = None
    color: ColorValue | None = None
    width: Number | None = None

    def __post_init__(self) -> None:
        _optional_enum("border.style", self.style, BorderStyle)
        _optional_color("border.color", self.color)
        _optional_number("border.width", self.width, minimum=0, minimum_exclusive=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class Shadow:
    """Sparse outer drop-shadow override."""

    mode: ShadowMode | None = None
    color: ColorValue | None = None
    opacity: Number | None = None
    offset_x: Number | None = None
    offset_y: Number | None = None
    blur: Number | None = None

    def __post_init__(self) -> None:
        _optional_enum("shadow.mode", self.mode, ShadowMode)
        _optional_color("shadow.color", self.color)
        _optional_number("shadow.opacity", self.opacity, minimum=0, maximum=1)
        _optional_number("shadow.offset_x", self.offset_x)
        _optional_number("shadow.offset_y", self.offset_y)
        _optional_number("shadow.blur", self.blur, minimum=0)


@dataclass(frozen=True, slots=True, kw_only=True)
class Appearance:
    """Sparse object-box appearance override."""

    fill: Fill | None = None
    border: Border | None = None
    corner_radius: Number | None = None
    opacity: Number | None = None
    shadow: Shadow | None = None

    def __post_init__(self) -> None:
        _optional_instance("appearance.fill", self.fill, Fill)
        _optional_instance("appearance.border", self.border, Border)
        _optional_number("appearance.corner_radius", self.corner_radius, minimum=0)
        _optional_number("appearance.opacity", self.opacity, minimum=0, maximum=1)
        _optional_instance("appearance.shadow", self.shadow, Shadow)


@dataclass(frozen=True, slots=True, kw_only=True)
class Crop:
    """Sparse crop rectangle in oriented source percentages."""

    x: Number | None = None
    y: Number | None = None
    width: Number | None = None
    height: Number | None = None

    def __post_init__(self) -> None:
        _optional_number(
            "crop.x",
            self.x,
            minimum=0,
            maximum=100,
            maximum_exclusive=True,
        )
        _optional_number(
            "crop.y",
            self.y,
            minimum=0,
            maximum=100,
            maximum_exclusive=True,
        )
        _optional_number(
            "crop.width",
            self.width,
            minimum=0,
            minimum_exclusive=True,
            maximum=100,
        )
        _optional_number(
            "crop.height",
            self.height,
            minimum=0,
            minimum_exclusive=True,
            maximum=100,
        )
        if self.x is not None and self.width is not None and self.x + self.width > 100:
            raise ValueError("crop.x + crop.width must not exceed 100")
        if (
            self.y is not None
            and self.height is not None
            and self.y + self.height > 100
        ):
            raise ValueError("crop.y + crop.height must not exceed 100")


@dataclass(frozen=True, slots=True, kw_only=True)
class FocalPoint:
    """Sparse focal point in oriented source percentages."""

    x: Number | None = None
    y: Number | None = None

    def __post_init__(self) -> None:
        _optional_number("focal_point.x", self.x, minimum=0, maximum=100)
        _optional_number("focal_point.y", self.y, minimum=0, maximum=100)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageMedia:
    """Sparse ImageBlock media configuration."""

    aspect_ratio_locked: bool | None = None
    crop: Crop | None = None
    fit: MediaFit | None = None
    focal_point: FocalPoint | None = None

    def __post_init__(self) -> None:
        _optional_bool("media.aspect_ratio_locked", self.aspect_ratio_locked)
        _optional_instance("media.crop", self.crop, Crop)
        _optional_enum("media.fit", self.fit, MediaFit)
        _optional_instance("media.focal_point", self.focal_point, FocalPoint)


@dataclass(frozen=True, slots=True, kw_only=True)
class Stacking:
    """Sparse sibling stacking override."""

    z_index: int | None = None

    def __post_init__(self) -> None:
        if self.z_index is not None and (
            not isinstance(self.z_index, int) or isinstance(self.z_index, bool)
        ):
            raise TypeError("stacking.z_index must be an integer")


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeConfig:
    """Sparse CodeBlock-specific configuration."""

    theme: CodeTheme | None = None

    def __post_init__(self) -> None:
        _optional_enum("code.theme", self.theme, CodeTheme)


@dataclass(frozen=True, slots=True, kw_only=True)
class Configuration:
    """Sparse object or theme configuration."""

    placement: Placement | None = None
    size: Size | None = None
    transform: Transform | None = None
    typography: Typography | None = None
    text_effects: TextEffects | None = None
    appearance: Appearance | None = None
    media: ImageMedia | None = None
    stacking: Stacking | None = None
    code: CodeConfig | None = None

    def __post_init__(self) -> None:
        expected = (
            ("placement", self.placement, Placement),
            ("size", self.size, Size),
            ("transform", self.transform, Transform),
            ("typography", self.typography, Typography),
            ("text_effects", self.text_effects, TextEffects),
            ("appearance", self.appearance, Appearance),
            ("media", self.media, ImageMedia),
            ("stacking", self.stacking, Stacking),
            ("code", self.code, CodeConfig),
        )
        for name, value, expected_type in expected:
            _optional_instance(name, value, expected_type)


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineFormatConfiguration:
    """Sparse configuration allowed on an InlineFormat container."""

    typography: InlineTypography | None = None
    text_effects: TextEffects | None = None

    def __post_init__(self) -> None:
        _optional_instance("typography", self.typography, InlineTypography)
        _optional_instance("text_effects", self.text_effects, TextEffects)


@dataclass(frozen=True, slots=True, kw_only=True)
class ThemePreset:
    """A structurally valid theme preset identity."""

    name: str
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Theme preset name must be a non-empty string")
        if not isinstance(self.version, int) or isinstance(self.version, bool):
            raise TypeError("Theme preset version must be an integer")


@dataclass(frozen=True, slots=True, kw_only=True)
class ThemeSlide:
    """Sparse theme overrides for a semantic slide kind."""

    self_config: Configuration | None = None
    elements: Mapping[ElementKind, Configuration] = field(default_factory=dict)
    roles: Mapping[SemanticRole, Configuration] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _optional_instance("theme slide self", self.self_config, Configuration)
        _freeze_mapping(self, "elements", ElementKind, Configuration)
        _freeze_mapping(self, "roles", SemanticRole, Configuration)


@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    """Sparse structured theme configuration."""

    preset: ThemePreset
    colors: Mapping[str, DirectColor] = field(default_factory=dict)
    slide: Configuration | None = None
    elements: Mapping[ElementKind, Configuration] = field(default_factory=dict)
    roles: Mapping[SemanticRole, Configuration] = field(default_factory=dict)
    slides: Mapping[SlideKind, ThemeSlide] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.preset, ThemePreset):
            raise TypeError("theme.preset must be a ThemePreset")
        color_copy: dict[str, DirectColor] = {}
        if not isinstance(self.colors, Mapping):
            raise TypeError("theme.colors must be a mapping")
        for name, color in self.colors.items():
            if not is_valid_theme_token_name(name):
                raise ValueError(f"Invalid theme color token name: {name!r}")
            if not isinstance(color, DirectColor):
                raise TypeError("Theme color definitions must be direct colors")
            color_copy[name] = color
        object.__setattr__(self, "colors", MappingProxyType(color_copy))
        _optional_instance("theme.slide", self.slide, Configuration)
        _freeze_mapping(self, "elements", ElementKind, Configuration)
        _freeze_mapping(self, "roles", SemanticRole, Configuration)
        _freeze_mapping(self, "slides", SlideKind, ThemeSlide)


@dataclass(frozen=True, slots=True, kw_only=True)
class LayoutDocument:
    """Canonical sparse configuration state for one presentation."""

    format_version: int
    theme: Theme
    configurations: Mapping[int, Configuration] = field(default_factory=dict)
    inline_formats: Mapping[int, InlineFormatConfiguration] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.format_version, int)
            or isinstance(self.format_version, bool)
            or self.format_version != 1
        ):
            raise ValueError("LayoutDocument format_version must be 1")
        if not isinstance(self.theme, Theme):
            raise TypeError("LayoutDocument theme must be a Theme")
        _freeze_ref_mapping(self, "configurations", Configuration)
        _freeze_ref_mapping(self, "inline_formats", InlineFormatConfiguration)


@dataclass(frozen=True, slots=True, kw_only=True)
class LayoutLoadResult:
    """The document and diagnostics produced by strict layout parsing."""

    document: LayoutDocument | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if self.document is not None and not isinstance(self.document, LayoutDocument):
            raise TypeError("document must be a LayoutDocument or None")
        if not isinstance(self.diagnostics, tuple) or not all(
            isinstance(item, Diagnostic) for item in self.diagnostics
        ):
            raise TypeError("diagnostics must be a tuple of Diagnostic objects")


_EnumT = TypeVar("_EnumT", bound=StrEnum)
_ValueT = TypeVar("_ValueT")


def _optional_number(
    name: str,
    value: Number | None,
    *,
    minimum: Number | None = None,
    minimum_exclusive: bool = False,
    maximum: Number | None = None,
    maximum_exclusive: bool = False,
) -> None:
    if value is None:
        return
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and (
        value <= minimum if minimum_exclusive else value < minimum
    ):
        comparator = "greater than" if minimum_exclusive else "at least"
        raise ValueError(f"{name} must be {comparator} {minimum}")
    if maximum is not None and (
        value >= maximum if maximum_exclusive else value > maximum
    ):
        comparator = "less than" if maximum_exclusive else "at most"
        raise ValueError(f"{name} must be {comparator} {maximum}")


def _optional_bool(name: str, value: bool | None) -> None:
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _optional_non_empty_string(name: str, value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ValueError(f"{name} must be a non-empty string")


def _optional_enum(name: str, value: _EnumT | None, expected: type[_EnumT]) -> None:
    if value is not None and not isinstance(value, expected):
        raise TypeError(f"{name} must be a {expected.__name__}")


def _optional_color(name: str, value: ColorValue | None) -> None:
    if value is not None and not isinstance(value, DirectColor | ThemeColor):
        raise TypeError(f"{name} must be a ColorValue")


def _optional_instance(name: str, value: object | None, expected: type[object]) -> None:
    if value is not None and not isinstance(value, expected):
        raise TypeError(f"{name} must be a {expected.__name__}")


def _freeze_mapping(
    instance: object,
    name: str,
    key_type: type[object],
    value_type: type[_ValueT],
) -> None:
    value = getattr(instance, name)
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    copied: dict[object, _ValueT] = {}
    for key, item in value.items():
        if not isinstance(key, key_type):
            raise TypeError(f"{name} has an invalid key")
        if not isinstance(item, value_type):
            raise TypeError(f"{name} has an invalid value")
        copied[key] = item
    object.__setattr__(instance, name, MappingProxyType(copied))


def _freeze_ref_mapping(
    instance: object,
    name: str,
    value_type: type[_ValueT],
) -> None:
    value = getattr(instance, name)
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    copied: dict[int, _ValueT] = {}
    for key, item in value.items():
        if not isinstance(key, int) or isinstance(key, bool) or key < 1:
            raise ValueError(f"{name} keys must be positive integers")
        if not isinstance(item, value_type):
            raise TypeError(f"{name} has an invalid value")
        copied[key] = item
    object.__setattr__(instance, name, MappingProxyType(copied))


__all__ = [
    "Appearance",
    "Border",
    "BorderStyle",
    "CodeConfig",
    "CodeTheme",
    "Configuration",
    "Crop",
    "ElementKind",
    "Fill",
    "FillMode",
    "FocalPoint",
    "FontFamily",
    "FontStyle",
    "FontWeight",
    "ImageMedia",
    "InlineFormatConfiguration",
    "InlineTypography",
    "LayoutDocument",
    "LayoutLoadResult",
    "MediaFit",
    "Number",
    "Outline",
    "Placement",
    "PlacementMode",
    "Script",
    "SemanticRole",
    "Shadow",
    "ShadowMode",
    "Size",
    "Stacking",
    "Strikethrough",
    "TextAlign",
    "TextEffects",
    "Theme",
    "ThemePreset",
    "ThemeSlide",
    "Transform",
    "Typography",
    "VerticalAlign",
]
