"""Schema and value validation for parsed layout JSON."""

from __future__ import annotations

import math
import re
from enum import StrEnum
from pathlib import Path
from typing import TypeVar

from ..document import ConfigPointer, Diagnostic, DiagnosticSeverity
from .colors import (
    STANDARD_COLOR_TOKENS,
    ColorValue,
    DirectColor,
    ThemeColor,
    is_valid_theme_token_name,
)
from .model import (
    Appearance,
    Border,
    BorderStyle,
    CodeConfig,
    CodeTheme,
    Configuration,
    Crop,
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
    ThemePreset,
    ThemeSlide,
    Transform,
    Typography,
    VerticalAlign,
)

_MISSING = object()
_REF_KEY = re.compile(r"^[1-9][0-9]*$")
_KNOWN_PRESET_NAME = "slidejunction-default"
_KNOWN_PRESET_VERSION = 1


def validate_layout(data: object, *, path: Path | None) -> LayoutLoadResult:
    """Validate a materialized strict-JSON value into the sparse model."""
    validator = _Validator(path)
    return validator.validate(data)


class _Validator:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.diagnostics: list[Diagnostic] = []

    def validate(self, data: object) -> LayoutLoadResult:
        if not isinstance(data, dict):
            self._diagnose(
                "",
                "invalid-layout-type",
                "The root layout JSON value must be an object.",
            )
            return self._result(None)

        self._unknown_properties(
            data,
            {"format_version", "theme", "configurations", "inline_formats"},
            "",
        )
        format_version = self._parse_format_version(data)
        if format_version is None:
            return self._result(None)
        theme, available_tokens = self._parse_theme(data.get("theme", _MISSING))
        if theme is None:
            return self._result(None)

        configurations = self._parse_definitions(
            data.get("configurations", _MISSING),
            "/configurations",
            inline=False,
            available_tokens=available_tokens,
        )
        inline_formats = self._parse_definitions(
            data.get("inline_formats", _MISSING),
            "/inline_formats",
            inline=True,
            available_tokens=available_tokens,
        )
        document = LayoutDocument(
            format_version=format_version,
            theme=theme,
            configurations=configurations,
            inline_formats=inline_formats,
        )
        return self._result(document)

    def _parse_format_version(self, data: dict[str, object]) -> int | None:
        value = data.get("format_version", _MISSING)
        if value is _MISSING:
            self._diagnose(
                "/format_version",
                "missing-layout-format-version",
                "Layout format_version is required.",
            )
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            self._diagnose(
                "/format_version",
                "invalid-layout-type",
                "Layout format_version must be an integer.",
            )
            return None
        if value != 1:
            self._diagnose(
                "/format_version",
                "unsupported-layout-format-version",
                f"Unsupported layout format version: {value}",
            )
            return None
        return value

    def _parse_theme(
        self,
        value: object,
    ) -> tuple[Theme | None, frozenset[str] | None]:
        if value is _MISSING:
            self._diagnose(
                "/theme",
                "missing-layout-property",
                "The required theme property is missing.",
            )
            return None, None
        if not isinstance(value, dict):
            self._diagnose(
                "/theme",
                "invalid-layout-type",
                "theme must be an object.",
            )
            return None, None

        self._unknown_properties(
            value,
            {"preset", "colors", "slide", "elements", "roles", "slides"},
            "/theme",
        )
        preset = self._parse_preset(value.get("preset", _MISSING))
        if preset is None:
            return None, None

        colors = self._parse_theme_colors(value.get("colors", _MISSING))
        known_preset = (
            preset.name == _KNOWN_PRESET_NAME
            and preset.version == _KNOWN_PRESET_VERSION
        )
        if preset.name != _KNOWN_PRESET_NAME:
            self._diagnose(
                "/theme/preset/name",
                "unknown-theme-preset",
                f"Unknown theme preset: {preset.name!r}",
            )
        elif preset.version != _KNOWN_PRESET_VERSION:
            self._diagnose(
                "/theme/preset/version",
                "unsupported-theme-preset-version",
                f"Unsupported {preset.name!r} preset version: {preset.version}",
            )
        available_tokens = (
            frozenset(STANDARD_COLOR_TOKENS | colors.keys()) if known_preset else None
        )

        slide = self._optional_configuration(
            value,
            "slide",
            "/theme",
            available_tokens=available_tokens,
        )
        elements = self._parse_named_configurations(
            value.get("elements", _MISSING),
            "/theme/elements",
            ElementKind,
            available_tokens,
        )
        roles = self._parse_named_configurations(
            value.get("roles", _MISSING),
            "/theme/roles",
            SemanticRole,
            available_tokens,
        )
        slides = self._parse_theme_slides(
            value.get("slides", _MISSING), available_tokens
        )
        return (
            Theme(
                preset=preset,
                colors=colors,
                slide=slide,
                elements=elements,
                roles=roles,
                slides=slides,
            ),
            available_tokens,
        )

    def _parse_preset(self, value: object) -> ThemePreset | None:
        pointer = "/theme/preset"
        if value is _MISSING:
            self._diagnose(
                pointer,
                "missing-layout-property",
                "The required theme preset is missing.",
            )
            return None
        if not isinstance(value, dict):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                "theme.preset must be an object.",
            )
            return None
        self._unknown_properties(value, {"name", "version"}, pointer)

        name = value.get("name", _MISSING)
        version = value.get("version", _MISSING)
        valid = True
        if name is _MISSING:
            self._diagnose(
                f"{pointer}/name",
                "missing-layout-property",
                "Theme preset name is required.",
            )
            valid = False
        elif not isinstance(name, str) or not name:
            self._diagnose(
                f"{pointer}/name",
                "invalid-layout-type",
                "Theme preset name must be a non-empty string.",
            )
            valid = False

        if version is _MISSING:
            self._diagnose(
                f"{pointer}/version",
                "missing-layout-property",
                "Theme preset version is required.",
            )
            valid = False
        elif not isinstance(version, int) or isinstance(version, bool):
            self._diagnose(
                f"{pointer}/version",
                "invalid-layout-type",
                "Theme preset version must be an integer.",
            )
            valid = False

        if not valid:
            return None
        if not isinstance(name, str) or not isinstance(version, int):
            raise TypeError("Validated preset fields have inconsistent types")
        return ThemePreset(name=name, version=version)

    def _parse_theme_colors(self, value: object) -> dict[str, DirectColor]:
        pointer = "/theme/colors"
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                "theme.colors must be an object.",
            )
            return {}

        colors: dict[str, DirectColor] = {}
        for name, raw_color in value.items():
            color_pointer = self._join(pointer, name)
            if not is_valid_theme_token_name(name):
                self._diagnose(
                    color_pointer,
                    "invalid-theme-color-token-name",
                    f"Invalid theme color token name: {name!r}",
                )
                continue
            if raw_color is None:
                self._diagnose(
                    color_pointer,
                    "invalid-layout-type",
                    "Theme token definitions cannot be null.",
                )
                continue
            if not isinstance(raw_color, str):
                self._diagnose(
                    color_pointer,
                    "invalid-color-value",
                    "Theme token definitions must be direct #RRGGBB colors.",
                )
                continue
            try:
                colors[name] = DirectColor(raw_color)
            except ValueError:
                self._diagnose(
                    color_pointer,
                    "invalid-color-value",
                    "Theme token definitions must be six-digit #RRGGBB colors.",
                )
        return colors

    def _parse_named_configurations(
        self,
        value: object,
        pointer: str,
        key_type: type[_EnumT],
        available_tokens: frozenset[str] | None,
    ) -> dict[_EnumT, Configuration]:
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._diagnose(pointer, "invalid-layout-type", "Expected an object.")
            return {}
        result: dict[_EnumT, Configuration] = {}
        for raw_key, raw_configuration in value.items():
            entry_pointer = self._join(pointer, raw_key)
            try:
                key = key_type(raw_key)
            except ValueError:
                self._diagnose(
                    entry_pointer,
                    "unknown-layout-property",
                    f"Unknown {key_type.__name__} key: {raw_key!r}",
                )
                continue
            if not isinstance(raw_configuration, dict):
                self._diagnose(
                    entry_pointer,
                    "invalid-layout-type",
                    "Theme configuration must be an object.",
                )
                continue
            result[key] = self._parse_configuration(
                raw_configuration,
                entry_pointer,
                available_tokens=available_tokens,
            )
        return result

    def _parse_theme_slides(
        self,
        value: object,
        available_tokens: frozenset[str] | None,
    ) -> dict[SlideKind, ThemeSlide]:
        pointer = "/theme/slides"
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._diagnose(
                pointer, "invalid-layout-type", "theme.slides must be an object."
            )
            return {}

        result: dict[SlideKind, ThemeSlide] = {}
        for raw_key, raw_slide in value.items():
            slide_pointer = self._join(pointer, raw_key)
            try:
                key = SlideKind(raw_key)
            except ValueError:
                self._diagnose(
                    slide_pointer,
                    "unknown-layout-property",
                    f"Unknown slide kind: {raw_key!r}",
                )
                continue
            if not isinstance(raw_slide, dict):
                self._diagnose(
                    slide_pointer,
                    "invalid-layout-type",
                    "Theme slide scope must be an object.",
                )
                continue
            self._unknown_properties(
                raw_slide, {"self", "elements", "roles"}, slide_pointer
            )
            self_config = self._optional_configuration(
                raw_slide,
                "self",
                slide_pointer,
                available_tokens=available_tokens,
            )
            elements = self._parse_named_configurations(
                raw_slide.get("elements", _MISSING),
                f"{slide_pointer}/elements",
                ElementKind,
                available_tokens,
            )
            roles = self._parse_named_configurations(
                raw_slide.get("roles", _MISSING),
                f"{slide_pointer}/roles",
                SemanticRole,
                available_tokens,
            )
            result[key] = ThemeSlide(
                self_config=self_config,
                elements=elements,
                roles=roles,
            )
        return result

    def _parse_definitions(
        self,
        value: object,
        pointer: str,
        *,
        inline: bool,
        available_tokens: frozenset[str] | None,
    ) -> dict[int, Configuration] | dict[int, InlineFormatConfiguration]:
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._diagnose(pointer, "invalid-layout-type", "Expected an object.")
            return {}

        if inline:
            inline_result: dict[int, InlineFormatConfiguration] = {}
        else:
            object_result: dict[int, Configuration] = {}
        for raw_key, raw_definition in value.items():
            entry_pointer = self._join(pointer, raw_key)
            if _REF_KEY.fullmatch(raw_key) is None:
                self._diagnose(
                    entry_pointer,
                    "invalid-ref-key",
                    f"Configuration ref key must be a canonical positive integer: {raw_key!r}",
                )
                continue
            ref_id = int(raw_key)
            if not isinstance(raw_definition, dict):
                self._diagnose(
                    entry_pointer,
                    "invalid-layout-type",
                    "A configuration definition must be an object.",
                    ref_id=ref_id,
                )
                continue
            if inline:
                inline_result[ref_id] = self._parse_inline_configuration(
                    raw_definition,
                    entry_pointer,
                    available_tokens=available_tokens,
                    ref_id=ref_id,
                )
            else:
                object_result[ref_id] = self._parse_configuration(
                    raw_definition,
                    entry_pointer,
                    available_tokens=available_tokens,
                    ref_id=ref_id,
                )
        return inline_result if inline else object_result

    def _optional_configuration(
        self,
        container: dict[str, object],
        key: str,
        parent_pointer: str,
        *,
        available_tokens: frozenset[str] | None,
    ) -> Configuration | None:
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        pointer = f"{parent_pointer}/{key}"
        if not isinstance(value, dict):
            self._diagnose(pointer, "invalid-layout-type", "Expected an object.")
            return None
        return self._parse_configuration(
            value, pointer, available_tokens=available_tokens
        )

    def _parse_configuration(
        self,
        value: dict[str, object],
        pointer: str,
        *,
        available_tokens: frozenset[str] | None,
        ref_id: int | None = None,
    ) -> Configuration:
        allowed = {
            "placement",
            "size",
            "transform",
            "typography",
            "text_effects",
            "appearance",
            "media",
            "stacking",
            "code",
        }
        self._unknown_properties(value, allowed, pointer, ref_id=ref_id)
        return Configuration(
            placement=self._nested(
                value,
                "placement",
                pointer,
                self._parse_placement,
                ref_id=ref_id,
            ),
            size=self._nested(value, "size", pointer, self._parse_size, ref_id=ref_id),
            transform=self._nested(
                value,
                "transform",
                pointer,
                self._parse_transform,
                ref_id=ref_id,
            ),
            typography=self._nested(
                value,
                "typography",
                pointer,
                lambda item, location, reference: self._parse_typography(
                    item,
                    location,
                    available_tokens,
                    inline=False,
                    ref_id=reference,
                ),
                ref_id=ref_id,
            ),
            text_effects=self._nested(
                value,
                "text_effects",
                pointer,
                lambda item, location, reference: self._parse_text_effects(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
            appearance=self._nested(
                value,
                "appearance",
                pointer,
                lambda item, location, reference: self._parse_appearance(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
            media=self._nested(
                value, "media", pointer, self._parse_media, ref_id=ref_id
            ),
            stacking=self._nested(
                value,
                "stacking",
                pointer,
                self._parse_stacking,
                ref_id=ref_id,
            ),
            code=self._nested(value, "code", pointer, self._parse_code, ref_id=ref_id),
        )

    def _parse_inline_configuration(
        self,
        value: dict[str, object],
        pointer: str,
        *,
        available_tokens: frozenset[str] | None,
        ref_id: int,
    ) -> InlineFormatConfiguration:
        allowed = {"typography", "text_effects"}
        forbidden = {
            "placement",
            "size",
            "transform",
            "appearance",
            "media",
            "stacking",
            "code",
        }
        for key in value:
            if key in forbidden:
                self._diagnose(
                    self._join(pointer, key),
                    "property-not-allowed-in-inline-format",
                    f"{key!r} is not allowed in inline_formats.",
                    ref_id=ref_id,
                )
            elif key not in allowed:
                self._diagnose(
                    self._join(pointer, key),
                    "unknown-layout-property",
                    f"Unknown layout property: {key!r}",
                    ref_id=ref_id,
                )
        return InlineFormatConfiguration(
            typography=self._nested(
                value,
                "typography",
                pointer,
                lambda item, location, reference: self._parse_typography(
                    item,
                    location,
                    available_tokens,
                    inline=True,
                    ref_id=reference,
                ),
                ref_id=ref_id,
            ),
            text_effects=self._nested(
                value,
                "text_effects",
                pointer,
                lambda item, location, reference: self._parse_text_effects(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
        )

    def _nested(self, container, key, parent_pointer, parser, *, ref_id=None):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        pointer = f"{parent_pointer}/{key}"
        if not isinstance(value, dict):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                f"{key} must be an object.",
                ref_id=ref_id,
            )
            return None
        return parser(value, pointer, ref_id)

    def _parse_placement(self, value, pointer, ref_id):
        self._unknown_properties(value, {"mode", "x", "y"}, pointer, ref_id=ref_id)
        return Placement(
            mode=self._enum(value, "mode", pointer, PlacementMode, ref_id),
            x=self._number(value, "x", pointer, ref_id=ref_id),
            y=self._number(value, "y", pointer, ref_id=ref_id),
        )

    def _parse_size(self, value, pointer, ref_id):
        self._unknown_properties(value, {"width", "height"}, pointer, ref_id=ref_id)
        return Size(
            width=self._number(
                value, "width", pointer, minimum=0, exclusive=True, ref_id=ref_id
            ),
            height=self._number(
                value, "height", pointer, minimum=0, exclusive=True, ref_id=ref_id
            ),
        )

    def _parse_transform(self, value, pointer, ref_id):
        self._unknown_properties(value, {"rotation"}, pointer, ref_id=ref_id)
        return Transform(
            rotation=self._number(value, "rotation", pointer, ref_id=ref_id)
        )

    def _parse_typography(
        self,
        value,
        pointer,
        available_tokens,
        *,
        inline,
        ref_id,
    ):
        common = {
            "font_family",
            "font_size",
            "font_weight",
            "font_style",
            "color",
            "underline",
            "strikethrough",
            "script",
        }
        aligned = {"text_align", "vertical_align"}
        if inline:
            for key in value:
                if key in aligned:
                    self._diagnose(
                        self._join(pointer, key),
                        "property-not-allowed-in-inline-format",
                        f"typography.{key} is not allowed in inline_formats.",
                        ref_id=ref_id,
                    )
                elif key not in common:
                    self._diagnose(
                        self._join(pointer, key),
                        "unknown-layout-property",
                        f"Unknown typography property: {key!r}",
                        ref_id=ref_id,
                    )
        else:
            self._unknown_properties(value, common | aligned, pointer, ref_id=ref_id)

        font_family = self._nested(
            value,
            "font_family",
            pointer,
            self._parse_font_family,
            ref_id=ref_id,
        )
        arguments = {
            "font_family": font_family,
            "font_size": self._number(
                value,
                "font_size",
                pointer,
                minimum=0,
                exclusive=True,
                ref_id=ref_id,
            ),
            "font_weight": self._enum(
                value, "font_weight", pointer, FontWeight, ref_id
            ),
            "font_style": self._enum(value, "font_style", pointer, FontStyle, ref_id),
            "color": self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            "underline": self._boolean(value, "underline", pointer, ref_id),
            "strikethrough": self._enum(
                value, "strikethrough", pointer, Strikethrough, ref_id
            ),
            "script": self._enum(value, "script", pointer, Script, ref_id),
        }
        if inline:
            return InlineTypography(**arguments)
        return Typography(
            **arguments,
            text_align=self._enum(value, "text_align", pointer, TextAlign, ref_id),
            vertical_align=self._enum(
                value, "vertical_align", pointer, VerticalAlign, ref_id
            ),
        )

    def _parse_font_family(self, value, pointer, ref_id):
        self._unknown_properties(value, {"latin", "japanese"}, pointer, ref_id=ref_id)
        return FontFamily(
            latin=self._string(value, "latin", pointer, ref_id),
            japanese=self._string(value, "japanese", pointer, ref_id),
        )

    def _parse_text_effects(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(value, {"outline"}, pointer, ref_id=ref_id)
        return TextEffects(
            outline=self._nested(
                value,
                "outline",
                pointer,
                lambda item, location, reference: self._parse_outline(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            )
        )

    def _parse_outline(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(value, {"color", "width"}, pointer, ref_id=ref_id)
        return Outline(
            color=self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            width=self._number(
                value, "width", pointer, minimum=0, exclusive=True, ref_id=ref_id
            ),
        )

    def _parse_appearance(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(
            value,
            {"fill", "border", "corner_radius", "opacity", "shadow"},
            pointer,
            ref_id=ref_id,
        )
        return Appearance(
            fill=self._nested(
                value,
                "fill",
                pointer,
                lambda item, location, reference: self._parse_fill(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
            border=self._nested(
                value,
                "border",
                pointer,
                lambda item, location, reference: self._parse_border(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
            corner_radius=self._number(
                value, "corner_radius", pointer, minimum=0, ref_id=ref_id
            ),
            opacity=self._number(
                value, "opacity", pointer, minimum=0, maximum=1, ref_id=ref_id
            ),
            shadow=self._nested(
                value,
                "shadow",
                pointer,
                lambda item, location, reference: self._parse_shadow(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
        )

    def _parse_fill(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(
            value, {"mode", "color", "opacity"}, pointer, ref_id=ref_id
        )
        return Fill(
            mode=self._enum(value, "mode", pointer, FillMode, ref_id),
            color=self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            opacity=self._number(
                value, "opacity", pointer, minimum=0, maximum=1, ref_id=ref_id
            ),
        )

    def _parse_border(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(
            value, {"style", "color", "width"}, pointer, ref_id=ref_id
        )
        return Border(
            style=self._enum(value, "style", pointer, BorderStyle, ref_id),
            color=self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            width=self._number(
                value, "width", pointer, minimum=0, exclusive=True, ref_id=ref_id
            ),
        )

    def _parse_shadow(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(
            value,
            {"mode", "color", "opacity", "offset_x", "offset_y", "blur"},
            pointer,
            ref_id=ref_id,
        )
        return Shadow(
            mode=self._enum(value, "mode", pointer, ShadowMode, ref_id),
            color=self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            opacity=self._number(
                value, "opacity", pointer, minimum=0, maximum=1, ref_id=ref_id
            ),
            offset_x=self._number(value, "offset_x", pointer, ref_id=ref_id),
            offset_y=self._number(value, "offset_y", pointer, ref_id=ref_id),
            blur=self._number(value, "blur", pointer, minimum=0, ref_id=ref_id),
        )

    def _parse_media(self, value, pointer, ref_id):
        self._unknown_properties(
            value,
            {"aspect_ratio_locked", "crop", "fit", "focal_point"},
            pointer,
            ref_id=ref_id,
        )
        return ImageMedia(
            aspect_ratio_locked=self._boolean(
                value, "aspect_ratio_locked", pointer, ref_id
            ),
            crop=self._nested(value, "crop", pointer, self._parse_crop, ref_id=ref_id),
            fit=self._enum(value, "fit", pointer, MediaFit, ref_id),
            focal_point=self._nested(
                value,
                "focal_point",
                pointer,
                self._parse_focal_point,
                ref_id=ref_id,
            ),
        )

    def _parse_crop(self, value, pointer, ref_id):
        diagnostic_count = len(self.diagnostics)
        self._unknown_properties(
            value, {"x", "y", "width", "height"}, pointer, ref_id=ref_id
        )
        x = self._number(
            value,
            "x",
            pointer,
            minimum=0,
            maximum=100,
            maximum_exclusive=True,
            ref_id=ref_id,
        )
        y = self._number(
            value,
            "y",
            pointer,
            minimum=0,
            maximum=100,
            maximum_exclusive=True,
            ref_id=ref_id,
        )
        width = self._number(
            value,
            "width",
            pointer,
            minimum=0,
            exclusive=True,
            maximum=100,
            ref_id=ref_id,
        )
        height = self._number(
            value,
            "height",
            pointer,
            minimum=0,
            exclusive=True,
            maximum=100,
            ref_id=ref_id,
        )
        if x is not None and width is not None and x + width > 100:
            self._diagnose(
                pointer,
                "config-number-out-of-range",
                "crop.x + crop.width must not exceed 100.",
                ref_id=ref_id,
            )
        if y is not None and height is not None and y + height > 100:
            self._diagnose(
                pointer,
                "config-number-out-of-range",
                "crop.y + crop.height must not exceed 100.",
                ref_id=ref_id,
            )
        if len(self.diagnostics) != diagnostic_count:
            return None
        return Crop(x=x, y=y, width=width, height=height)

    def _parse_focal_point(self, value, pointer, ref_id):
        diagnostic_count = len(self.diagnostics)
        self._unknown_properties(value, {"x", "y"}, pointer, ref_id=ref_id)
        focal_point = FocalPoint(
            x=self._number(value, "x", pointer, minimum=0, maximum=100, ref_id=ref_id),
            y=self._number(value, "y", pointer, minimum=0, maximum=100, ref_id=ref_id),
        )
        if len(self.diagnostics) != diagnostic_count:
            return None
        return focal_point

    def _parse_stacking(self, value, pointer, ref_id):
        self._unknown_properties(value, {"z_index"}, pointer, ref_id=ref_id)
        raw = value.get("z_index", _MISSING)
        if raw is _MISSING:
            z_index = None
        elif not isinstance(raw, int) or isinstance(raw, bool):
            self._diagnose(
                f"{pointer}/z_index",
                "invalid-layout-type",
                "stacking.z_index must be an integer.",
                ref_id=ref_id,
            )
            z_index = None
        else:
            z_index = raw
        return Stacking(z_index=z_index)

    def _parse_code(self, value, pointer, ref_id):
        self._unknown_properties(value, {"theme"}, pointer, ref_id=ref_id)
        return CodeConfig(theme=self._enum(value, "theme", pointer, CodeTheme, ref_id))

    def _number(
        self,
        container,
        key,
        parent_pointer,
        *,
        minimum=None,
        maximum=None,
        exclusive=False,
        maximum_exclusive=False,
        ref_id=None,
    ):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        pointer = f"{parent_pointer}/{key}"
        if not isinstance(value, int | float) or isinstance(value, bool):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                f"{key} must be numeric.",
                ref_id=ref_id,
            )
            return None
        if isinstance(value, float) and not math.isfinite(value):
            self._diagnose(
                pointer,
                "non-finite-config-number",
                f"{key} must be finite.",
                ref_id=ref_id,
            )
            return None
        below = minimum is not None and (
            value <= minimum if exclusive else value < minimum
        )
        above = maximum is not None and (
            value >= maximum if maximum_exclusive else value > maximum
        )
        if below or above:
            self._diagnose(
                pointer,
                "config-number-out-of-range",
                f"{key} is outside its allowed range.",
                ref_id=ref_id,
            )
            return None
        return value

    def _boolean(self, container, key, parent_pointer, ref_id):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        if not isinstance(value, bool):
            self._diagnose(
                f"{parent_pointer}/{key}",
                "invalid-layout-type",
                f"{key} must be a boolean.",
                ref_id=ref_id,
            )
            return None
        return value

    def _string(self, container, key, parent_pointer, ref_id):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        if not isinstance(value, str) or not value:
            self._diagnose(
                f"{parent_pointer}/{key}",
                "invalid-layout-type",
                f"{key} must be a non-empty string.",
                ref_id=ref_id,
            )
            return None
        return value

    def _enum(self, container, key, parent_pointer, enum_type, ref_id):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        pointer = f"{parent_pointer}/{key}"
        if not isinstance(value, str):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                f"{key} must be a string.",
                ref_id=ref_id,
            )
            return None
        try:
            return enum_type(value)
        except ValueError:
            self._diagnose(
                pointer,
                "invalid-config-enum",
                f"Invalid {key} value: {value!r}",
                ref_id=ref_id,
            )
            return None

    def _color(
        self,
        value: object,
        pointer: str,
        available_tokens: frozenset[str] | None,
        ref_id: int | None,
    ) -> ColorValue | None:
        if value is _MISSING:
            return None
        if value is None:
            self._diagnose(
                pointer,
                "invalid-layout-type",
                "A color value cannot be null.",
                ref_id=ref_id,
            )
            return None
        if isinstance(value, str):
            try:
                return DirectColor(value)
            except ValueError:
                self._diagnose(
                    pointer,
                    "invalid-color-value",
                    "Direct colors must use six-digit #RRGGBB syntax.",
                    ref_id=ref_id,
                )
                return None
        if not isinstance(value, dict):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                "A color must be a string or theme-reference object.",
                ref_id=ref_id,
            )
            return None
        if "theme" not in value:
            self._diagnose(
                pointer,
                "invalid-color-value",
                "A theme-reference color object must contain 'theme'.",
                ref_id=ref_id,
            )
            return None
        for key in value:
            if key != "theme":
                self._diagnose(
                    self._join(pointer, key),
                    "unknown-layout-property",
                    f"Unknown theme-reference color property: {key!r}",
                    ref_id=ref_id,
                )
        token = value["theme"]
        if token is None or not isinstance(token, str):
            self._diagnose(
                f"{pointer}/theme",
                "invalid-layout-type",
                "A theme color token must be a string.",
                ref_id=ref_id,
            )
            return None
        if not is_valid_theme_token_name(token):
            self._diagnose(
                f"{pointer}/theme",
                "invalid-theme-color-token-name",
                "Theme color token names must use canonical kebab-case.",
                ref_id=ref_id,
            )
            return None
        if available_tokens is not None and token not in available_tokens:
            self._diagnose(
                pointer,
                "missing-theme-color-token",
                f"Theme color token is not defined: {token!r}",
                ref_id=ref_id,
            )
            return None
        return ThemeColor(token)

    def _unknown_properties(
        self,
        value: dict[str, object],
        allowed: set[str],
        pointer: str,
        *,
        ref_id: int | None = None,
    ) -> None:
        for key in value:
            if key not in allowed:
                self._diagnose(
                    self._join(pointer, key),
                    "unknown-layout-property",
                    f"Unknown layout property: {key!r}",
                    ref_id=ref_id,
                )

    def _diagnose(
        self,
        pointer: str,
        code: str,
        message: str,
        *,
        ref_id: int | None = None,
    ) -> None:
        self.diagnostics.append(
            Diagnostic(
                severity=DiagnosticSeverity.ERROR,
                code=code,
                message=message,
                config_pointer=ConfigPointer(path=self.path, pointer=pointer),
                ref_id=ref_id,
            )
        )

    def _result(self, document: LayoutDocument | None) -> LayoutLoadResult:
        diagnostics = tuple(
            sorted(
                self.diagnostics,
                key=lambda item: (
                    item.config_pointer.pointer
                    if item.config_pointer is not None
                    else "",
                    item.code,
                    item.ref_id or 0,
                ),
            )
        )
        return LayoutLoadResult(document=document, diagnostics=diagnostics)

    @staticmethod
    def _join(parent: str, component: str) -> str:
        escaped = component.replace("~", "~0").replace("/", "~1")
        return f"{parent}/{escaped}"


_EnumT = TypeVar("_EnumT", bound=StrEnum)


__all__: list[str] = []
