"""Private numeric validation and image completion shared by M5A and M5B."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .layout import Crop, ElementKind, FocalPoint, ImageMedia
from .resolver import ResolvedBlock

if TYPE_CHECKING:
    from .image_geometry import NormalizedRect


def _complete_crop_percent_to_normalized_components(
    crop_percent: Crop | None,
) -> tuple[float, float, float, float]:
    """Complete crop percentages before converting each component to 0..1."""
    if crop_percent is None:
        return 0.0, 0.0, 1.0, 1.0
    x_percent = 0 if crop_percent.x is None else crop_percent.x
    y_percent = 0 if crop_percent.y is None else crop_percent.y
    width_percent = (
        100 - x_percent if crop_percent.width is None else crop_percent.width
    )
    height_percent = (
        100 - y_percent if crop_percent.height is None else crop_percent.height
    )
    return (
        x_percent / 100,
        y_percent / 100,
        width_percent / 100,
        height_percent / 100,
    )


def _complete_focal_percent_to_normalized_candidate(
    focal_percent: FocalPoint | None,
    crop_normalized: NormalizedRect,
) -> tuple[float, float]:
    """Complete focal axes from a boundary-snapped crop without clamping."""
    center_x_normalized = crop_normalized.x + crop_normalized.width / 2
    center_y_normalized = crop_normalized.y + crop_normalized.height / 2
    x_normalized = (
        center_x_normalized
        if focal_percent is None or focal_percent.x is None
        else focal_percent.x / 100
    )
    y_normalized = (
        center_y_normalized
        if focal_percent is None or focal_percent.y is None
        else focal_percent.y / 100
    )
    return x_normalized, y_normalized


def _finite_float(name: str, value: float) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be finite") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _positive_float(name: str, value: float) -> float:
    result = _finite_float(name, value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_ratio(name: str, numerator: float, denominator: float) -> float:
    try:
        result = numerator / denominator
    except OverflowError as error:
        raise ValueError(f"{name} must be finite and positive") from error
    if not isinstance(result, int | float) or not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return float(result)


def _positive_product(name: str, left: float, right: float) -> float:
    result = left * right
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _require_instance(name: str, value: object, expected: type[object]) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{name} must be a {expected.__name__}")


def _require_image_media(resolved_image_block: ResolvedBlock) -> ImageMedia:
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    if resolved_image_block.element_kind is not ElementKind.IMAGE_BLOCK:
        raise ValueError("resolved_image_block must resolve an ImageBlock")
    media = resolved_image_block.configuration.media
    if media is None or media.fit is None:  # pragma: no cover - M4 invariant
        raise ValueError("Resolved ImageBlock must have effective media and fit")
    return media
