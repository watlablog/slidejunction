"""Private immutable theme-preset registry."""

from __future__ import annotations

from types import MappingProxyType

from .layout import DirectColor, Theme, ThemePreset

_DEFAULT_PRESET_NAME = "slidejunction-default"
_DEFAULT_PRESET_VERSION = 1

_DEFAULT_PRESET = Theme(
    preset=ThemePreset(
        name=_DEFAULT_PRESET_NAME,
        version=_DEFAULT_PRESET_VERSION,
    ),
    colors={
        "background-1": DirectColor("#FFFFFF"),
        "foreground-1": DirectColor("#1F2328"),
        "background-2": DirectColor("#F6F8FA"),
        "foreground-2": DirectColor("#57606A"),
        "accent-1": DirectColor("#2563EB"),
        "accent-2": DirectColor("#0F766E"),
        "accent-3": DirectColor("#16A34A"),
        "accent-4": DirectColor("#D97706"),
        "accent-5": DirectColor("#DC2626"),
        "accent-6": DirectColor("#7C3AED"),
        "link": DirectColor("#2563EB"),
        "visited-link": DirectColor("#7C3AED"),
    },
)
_PRESETS = MappingProxyType(
    {(_DEFAULT_PRESET_NAME, _DEFAULT_PRESET_VERSION): _DEFAULT_PRESET}
)


def _effective_preset(preset: ThemePreset) -> Theme:
    """Return the known preset or the v1 effective fallback."""
    return _PRESETS.get((preset.name, preset.version), _DEFAULT_PRESET)
