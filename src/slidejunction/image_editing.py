"""Pure immutable transactions on a caller-selected sparse image configuration.

The local configuration is the write target; the resolved block supplies the
current effective state. The caller owns ref selection, snapshot consistency,
and re-resolution. Semantic no-ops return the original configuration, comparing
crop and focal intent in canonical persistent percentages without tolerance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TypeVar

from ._image_common import (
    _complete_crop_percent_to_normalized_components,
    _complete_focal_percent_to_normalized_candidate,
    _positive_float,
    _positive_product,
    _positive_ratio,
    _require_image_media,
    _require_instance,
)
from .image_geometry import NormalizedPoint, NormalizedRect
from .layout import Configuration, Crop, FocalPoint, ImageMedia, MediaFit, Size
from .resolver import ResolvedBlock


class ImageResizeDriver(StrEnum):
    """The single axis supplying an image resize request."""

    WIDTH = "width"
    HEIGHT = "height"


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterializedImageSize:
    """Current untransformed border-box size in respective slide-axis percentages.

    These caller-supplied dimensions are neither intrinsic pixels nor the
    contain destination rectangle or a rotated bounding box.
    """

    width: float
    height: float

    def __post_init__(self) -> None:
        width = _positive_float("current image width", self.width)
        height = _positive_float("current image height", self.height)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


def lock_image_aspect_ratio(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
) -> Configuration:
    """Set an explicit local lock without changing size or storing a ratio."""
    _require_instance("local_configuration", local_configuration, Configuration)
    media = _require_image_media(resolved_image_block)
    if media.aspect_ratio_locked:
        return local_configuration
    return _set_media_properties(local_configuration, aspect_ratio_locked=True)


def unlock_image_aspect_ratio(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    current_size: MaterializedImageSize,
) -> Configuration:
    """Release an effective lock, preserving both current visible dimensions."""
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("current_size", current_size, MaterializedImageSize)
    media = _require_image_media(resolved_image_block)
    if not media.aspect_ratio_locked:
        return local_configuration
    size = _replace_if_changed(
        local_configuration.size or Size(),
        width=current_size.width,
        height=current_size.height,
    )
    local_media = _replace_if_changed(
        local_configuration.media or ImageMedia(),
        aspect_ratio_locked=False,
    )
    return _replace_if_changed(local_configuration, size=size, media=local_media)


def reset_image_aspect_ratio_lock(
    local_configuration: Configuration,
) -> Configuration:
    """Remove only the local lock override; retain previously materialized size."""
    return _reset_media_property(local_configuration, "aspect_ratio_locked")


def resize_image_size(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    current_size: MaterializedImageSize,
    *,
    driver: ImageResizeDriver,
    value: int | float,  # noqa: PYI041 - Preserve the explicit persistent numeric API.
) -> Configuration:
    """Resize one axis, scaling the other current axis only when effectively locked.

    The driven value retains its int/float representation. The current
    dimensions use different slide axes, so their quotient is not a physical
    image aspect ratio. No-op requests do not materialize either dimension.
    """
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("current_size", current_size, MaterializedImageSize)
    _require_instance("driver", driver, ImageResizeDriver)
    _require_positive_size_value(value)
    media = _require_image_media(resolved_image_block)

    current_driver = (
        current_size.width if driver is ImageResizeDriver.WIDTH else current_size.height
    )
    if value == current_driver:
        return local_configuration

    dimensions = {driver.value: value}
    if media.aspect_ratio_locked:
        scale = _positive_ratio("image resize scale", value, current_driver)
        if driver is ImageResizeDriver.WIDTH:
            dimensions["height"] = _positive_product(
                "resized image height", current_size.height, scale
            )
        else:
            dimensions["width"] = _positive_product(
                "resized image width", current_size.width, scale
            )
    size = _replace_if_changed(local_configuration.size or Size(), **dimensions)
    return _replace_if_changed(local_configuration, size=size)


def set_image_crop(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    source_crop: NormalizedRect,
) -> Configuration:
    """Set a complete original-asset crop, comparing both values in stored units."""
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("source_crop", source_crop, NormalizedRect)
    media = _require_image_media(resolved_image_block)
    requested_crop = _normalized_rect_to_crop_percent(source_crop)
    current_crop = _normalized_rect_to_crop_percent(
        _complete_crop_normalized_rect(media.crop)
    )
    if requested_crop == current_crop:
        return local_configuration
    return _set_media_properties(local_configuration, crop=requested_crop)


def reset_image_crop(local_configuration: Configuration) -> Configuration:
    """Remove only the local crop override, leaving stored focal intent intact."""
    return _reset_media_property(local_configuration, "crop")


def set_image_focal_point(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    point: NormalizedPoint,
) -> Configuration:
    """Set complete original-asset focal intent without crop clamping or fit changes."""
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("point", point, NormalizedPoint)
    media = _require_image_media(resolved_image_block)
    requested_focal = _normalized_xy_to_focal_percent(point.x, point.y)
    crop_normalized = _complete_crop_normalized_rect(media.crop)
    x_normalized, y_normalized = _complete_focal_percent_to_normalized_candidate(
        media.focal_point, crop_normalized
    )
    # Do not construct a NormalizedPoint here: it would snap the raw candidate
    # before the persistent comparison and erase small stored intent changes.
    current_focal = _normalized_xy_to_focal_percent(x_normalized, y_normalized)
    if requested_focal == current_focal:
        return local_configuration
    return _set_media_properties(local_configuration, focal_point=requested_focal)


def reset_image_focal_point(local_configuration: Configuration) -> Configuration:
    """Remove only the local focal override, delegating to upstream state."""
    return _reset_media_property(local_configuration, "focal_point")


def set_image_fit(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    fit: MediaFit,
) -> Configuration:
    """Set an explicit local fit only when it differs from the effective fit."""
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("fit", fit, MediaFit)
    media = _require_image_media(resolved_image_block)
    if fit is media.fit:
        return local_configuration
    return _set_media_properties(local_configuration, fit=fit)


def reset_image_fit(local_configuration: Configuration) -> Configuration:
    """Remove the local fit override rather than explicitly selecting stretch."""
    return _reset_media_property(local_configuration, "fit")


def _complete_crop_normalized_rect(crop_percent: Crop | None) -> NormalizedRect:
    x, y, width, height = _complete_crop_percent_to_normalized_components(crop_percent)
    return NormalizedRect(x=x, y=y, width=width, height=height)


def _normalized_rect_to_crop_percent(rect_normalized: NormalizedRect) -> Crop:
    x_percent = rect_normalized.x * 100
    y_percent = rect_normalized.y * 100
    width_percent = (
        100 - x_percent
        if rect_normalized.x + rect_normalized.width == 1
        else rect_normalized.width * 100
    )
    height_percent = (
        100 - y_percent
        if rect_normalized.y + rect_normalized.height == 1
        else rect_normalized.height * 100
    )
    return Crop(x=x_percent, y=y_percent, width=width_percent, height=height_percent)


def _normalized_xy_to_focal_percent(
    x_normalized: float, y_normalized: float
) -> FocalPoint:
    return FocalPoint(x=x_normalized * 100, y=y_normalized * 100)


def _require_positive_size_value(value: object) -> None:
    # Unlike materialized geometry floats, persistent Size accepts arbitrary
    # positive integers. Converting here would lose precision or reject them.
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError("requested image size must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("requested image size must be finite")
    if value <= 0:
        raise ValueError("requested image size must be positive")


_ModelT = TypeVar("_ModelT", Configuration, ImageMedia, Size)


def _replace_if_changed(model: _ModelT, **changes: object) -> _ModelT:
    result = replace(model, **changes)
    return model if result == model else result


def _set_media_properties(
    local_configuration: Configuration, **changes: object
) -> Configuration:
    media = _replace_if_changed(local_configuration.media or ImageMedia(), **changes)
    return _replace_if_changed(local_configuration, media=media)


def _reset_media_property(
    local_configuration: Configuration, property_name: str
) -> Configuration:
    _require_instance("local_configuration", local_configuration, Configuration)
    media = local_configuration.media
    if media is None or getattr(media, property_name) is None:
        return local_configuration
    updated_media = replace(media, **{property_name: None})
    return _replace_if_changed(
        local_configuration,
        media=None if updated_media == ImageMedia() else updated_media,
    )


__all__ = [
    "ImageResizeDriver",
    "MaterializedImageSize",
    "lock_image_aspect_ratio",
    "reset_image_aspect_ratio_lock",
    "reset_image_crop",
    "reset_image_fit",
    "reset_image_focal_point",
    "resize_image_size",
    "set_image_crop",
    "set_image_fit",
    "set_image_focal_point",
    "unlock_image_aspect_ratio",
]
