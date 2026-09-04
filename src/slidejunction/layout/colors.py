"""Canonical color values for SlideJunction layout configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_TOKEN_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

STANDARD_COLOR_TOKENS = frozenset(
    {
        "background-1",
        "foreground-1",
        "background-2",
        "foreground-2",
        "accent-1",
        "accent-2",
        "accent-3",
        "accent-4",
        "accent-5",
        "accent-6",
        "link",
        "visited-link",
    }
)


def is_valid_theme_token_name(value: object) -> bool:
    """Return whether *value* is a canonical theme color token name."""
    return isinstance(value, str) and _TOKEN_NAME.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class DirectColor:
    """A canonical direct ``#RRGGBB`` color."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _HEX_COLOR.fullmatch(self.value) is None:
            raise ValueError("Direct colors must use six-digit #RRGGBB syntax")
        object.__setattr__(self, "value", self.value.upper())


@dataclass(frozen=True, slots=True)
class ThemeColor:
    """A reference to a theme color token."""

    theme: str

    def __post_init__(self) -> None:
        if not is_valid_theme_token_name(self.theme):
            raise ValueError("Theme color references must use kebab-case token names")


ColorValue: TypeAlias = DirectColor | ThemeColor


__all__ = [
    "STANDARD_COLOR_TOKENS",
    "ColorValue",
    "DirectColor",
    "ThemeColor",
    "is_valid_theme_token_name",
]
