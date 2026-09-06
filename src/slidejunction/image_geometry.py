"""Pure renderer-independent geometry for resolved ImageBlock content."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ._image_common import (
    _complete_crop_percent_to_normalized_components,
    _complete_focal_percent_to_normalized_candidate,
    _finite_float,
    _positive_float,
    _positive_product,
    _positive_ratio,
    _require_image_media,
    _require_instance,
)
from .layout import Crop, FocalPoint, MediaFit
from .resolver import ResolvedBlock

_BOUNDARY_TOLERANCE = 1e-15
_ASPECT_RELATIVE_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True, kw_only=True)
class IntrinsicImageMetadata:
    """Orientation-normalized intrinsic image dimensions."""

    width: float
    height: float

    def __post_init__(self) -> None:
        width = _positive_float("intrinsic width", self.width)
        height = _positive_float("intrinsic height", self.height)
        _positive_ratio("intrinsic aspect ratio", width, height)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageTargetBox:
    """Caller-supplied untransformed local image box dimensions."""

    width: float
    height: float

    def __post_init__(self) -> None:
        width = _positive_float("target width", self.width)
        height = _positive_float("target height", self.height)
        _positive_ratio("target aspect ratio", width, height)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedPoint:
    """A point exactly contained by a normalized unit square."""

    x: float
    y: float

    def __post_init__(self) -> None:
        x = _snap_unit_coordinate(_finite_float("normalized point x", self.x))
        y = _snap_unit_coordinate(_finite_float("normalized point y", self.y))
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("Normalized point must be inside the unit square")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedRect:
    """A positive rectangle exactly contained by a normalized unit square."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        x = _snap_unit_coordinate(_finite_float("normalized rect x", self.x))
        y = _snap_unit_coordinate(_finite_float("normalized rect y", self.y))
        width = _snap_unit_extent(_finite_float("normalized rect width", self.width))
        height = _snap_unit_extent(_finite_float("normalized rect height", self.height))
        width = _snap_extent_to_unit_edge(x, width)
        height = _snap_extent_to_unit_edge(y, height)
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("Normalized rect origin must be inside the unit square")
        if not 0 < width <= 1 or not 0 < height <= 1:
            raise ValueError("Normalized rect dimensions must be in (0, 1]")
        if x + width > 1 or y + height > 1:
            raise ValueError("Normalized rect must be inside the unit square")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedImageGeometry:
    """Internally consistent image-local source and destination geometry."""

    intrinsic: IntrinsicImageMetadata
    target_box: ImageTargetBox
    fit: MediaFit
    source_crop: NormalizedRect
    effective_focal_point: NormalizedPoint | None
    visible_source_rect: NormalizedRect
    destination_rect: NormalizedRect

    def __post_init__(self) -> None:
        _require_instance("intrinsic", self.intrinsic, IntrinsicImageMetadata)
        _require_instance("target_box", self.target_box, ImageTargetBox)
        _require_instance("fit", self.fit, MediaFit)
        _require_instance("source_crop", self.source_crop, NormalizedRect)
        _require_optional_instance(
            "effective_focal_point",
            self.effective_focal_point,
            NormalizedPoint,
        )
        _require_instance(
            "visible_source_rect",
            self.visible_source_rect,
            NormalizedRect,
        )
        _require_instance(
            "destination_rect",
            self.destination_rect,
            NormalizedRect,
        )
        if not _contains_rect(self.source_crop, self.visible_source_rect):
            raise ValueError("Visible source rectangle must be inside source crop")

        if self.fit is MediaFit.STRETCH:
            if self.effective_focal_point is not None:
                raise ValueError(
                    "Stretch geometry cannot have an effective focal point"
                )
            if not _rects_close(self.visible_source_rect, self.source_crop):
                raise ValueError("Stretch geometry must use the complete source crop")
            if not _rects_close(self.destination_rect, _FULL_RECT):
                raise ValueError("Stretch geometry must fill the target box")
            return

        source_ratio = _source_aspect_ratio(self.intrinsic, self.source_crop)
        if self.fit is MediaFit.CONTAIN:
            if self.effective_focal_point is not None:
                raise ValueError(
                    "Contain geometry cannot have an effective focal point"
                )
            if not _rects_close(self.visible_source_rect, self.source_crop):
                raise ValueError("Contain geometry must use the complete source crop")
            destination_ratio = _destination_aspect_ratio(
                self.target_box,
                self.destination_rect,
            )
            if not _aspect_close(source_ratio, destination_ratio):
                raise ValueError("Contain geometry must preserve source aspect ratio")
            return

        if self.fit is MediaFit.COVER:
            if self.effective_focal_point is None:
                raise ValueError("Cover geometry requires an effective focal point")
            if not _contains_point(self.source_crop, self.effective_focal_point):
                raise ValueError("Effective focal point must be inside source crop")
            if not _rects_close(self.destination_rect, _FULL_RECT):
                raise ValueError("Cover geometry must fill the target box")
            target_ratio = _target_aspect_ratio(self.target_box)
            visible_ratio = _source_aspect_ratio(
                self.intrinsic,
                self.visible_source_rect,
            )
            if not _aspect_close(visible_ratio, target_ratio):
                raise ValueError("Cover viewport must match the target aspect ratio")
            return

        raise ValueError("Unsupported image fit")  # pragma: no cover


def resolve_image_geometry(
    resolved_image_block: ResolvedBlock,
    intrinsic: IntrinsicImageMetadata,
    target_box: ImageTargetBox,
) -> ResolvedImageGeometry:
    """Resolve pure image-local render geometry from Milestone 4 state."""
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("intrinsic", intrinsic, IntrinsicImageMetadata)
    _require_instance("target_box", target_box, ImageTargetBox)
    media = _require_image_media(resolved_image_block)
    source_crop = _complete_source_crop(media.crop)

    if media.fit is MediaFit.STRETCH:
        return ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target_box,
            fit=media.fit,
            source_crop=source_crop,
            effective_focal_point=None,
            visible_source_rect=source_crop,
            destination_rect=_FULL_RECT,
        )

    source_ratio = _source_aspect_ratio(intrinsic, source_crop)
    target_ratio = _target_aspect_ratio(target_box)
    if media.fit is MediaFit.CONTAIN:
        destination = _contain_destination(source_ratio, target_ratio)
        return ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target_box,
            fit=media.fit,
            source_crop=source_crop,
            effective_focal_point=None,
            visible_source_rect=source_crop,
            destination_rect=destination,
        )

    if media.fit is MediaFit.COVER:
        focal_point = _effective_focal_point(media.focal_point, source_crop)
        viewport = _cover_viewport(
            source_crop,
            focal_point,
            source_ratio,
            target_ratio,
        )
        return ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target_box,
            fit=media.fit,
            source_crop=source_crop,
            effective_focal_point=focal_point,
            visible_source_rect=viewport,
            destination_rect=_FULL_RECT,
        )

    raise ValueError("Unsupported image fit")  # pragma: no cover


def _complete_source_crop(crop: Crop | None) -> NormalizedRect:
    if crop is None:
        return _FULL_RECT
    x, y, width, height = _complete_crop_percent_to_normalized_components(crop)
    return NormalizedRect(
        x=x,
        y=y,
        width=width,
        height=height,
    )


def _effective_focal_point(
    focal_point: FocalPoint | None,
    crop: NormalizedRect,
) -> NormalizedPoint:
    x, y = _complete_focal_percent_to_normalized_candidate(focal_point, crop)
    return NormalizedPoint(
        x=_clamp(x, crop.x, crop.x + crop.width),
        y=_clamp(y, crop.y, crop.y + crop.height),
    )


def _contain_destination(
    source_ratio: float,
    target_ratio: float,
) -> NormalizedRect:
    if source_ratio > target_ratio:
        height = _positive_ratio(
            "contain destination height",
            target_ratio,
            source_ratio,
        )
        return NormalizedRect(x=0, y=(1 - height) / 2, width=1, height=height)
    if source_ratio < target_ratio:
        width = _positive_ratio(
            "contain destination width",
            source_ratio,
            target_ratio,
        )
        return NormalizedRect(x=(1 - width) / 2, y=0, width=width, height=1)
    return _FULL_RECT


def _cover_viewport(
    crop: NormalizedRect,
    focal_point: NormalizedPoint,
    source_ratio: float,
    target_ratio: float,
) -> NormalizedRect:
    if source_ratio > target_ratio:
        width_factor = _positive_ratio(
            "cover viewport width factor",
            target_ratio,
            source_ratio,
        )
        width = _positive_product(
            "cover viewport width",
            crop.width,
            width_factor,
        )
        height = crop.height
    elif source_ratio < target_ratio:
        height_factor = _positive_ratio(
            "cover viewport height factor",
            source_ratio,
            target_ratio,
        )
        width = crop.width
        height = _positive_product(
            "cover viewport height",
            crop.height,
            height_factor,
        )
    else:
        return crop

    x = _clamp(
        focal_point.x - width / 2,
        crop.x,
        crop.x + crop.width - width,
    )
    y = _clamp(
        focal_point.y - height / 2,
        crop.y,
        crop.y + crop.height - height,
    )
    return NormalizedRect(x=x, y=y, width=width, height=height)


def _source_aspect_ratio(
    intrinsic: IntrinsicImageMetadata,
    rect: NormalizedRect,
) -> float:
    intrinsic_ratio = _positive_ratio(
        "intrinsic aspect ratio",
        intrinsic.width,
        intrinsic.height,
    )
    crop_ratio = _positive_ratio(
        "source rectangle ratio",
        rect.width,
        rect.height,
    )
    return _positive_product(
        "effective source aspect ratio",
        intrinsic_ratio,
        crop_ratio,
    )


def _target_aspect_ratio(target_box: ImageTargetBox) -> float:
    return _positive_ratio(
        "target aspect ratio",
        target_box.width,
        target_box.height,
    )


def _destination_aspect_ratio(
    target_box: ImageTargetBox,
    rect: NormalizedRect,
) -> float:
    target_ratio = _target_aspect_ratio(target_box)
    rect_ratio = _positive_ratio(
        "destination rectangle ratio",
        rect.width,
        rect.height,
    )
    return _positive_product(
        "destination physical aspect ratio",
        target_ratio,
        rect_ratio,
    )


def _snap_unit_coordinate(value: float) -> float:
    if math.isclose(value, 0, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return 0.0
    if math.isclose(value, 1, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return 1.0
    return value


def _snap_unit_extent(value: float) -> float:
    if math.isclose(value, 1, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return 1.0
    return value


def _snap_extent_to_unit_edge(origin: float, extent: float) -> float:
    if math.isclose(
        origin + extent,
        1,
        rel_tol=0,
        abs_tol=_BOUNDARY_TOLERANCE,
    ):
        return 1 - origin
    return extent


def _clamp(value: float, lower: float, upper: float) -> float:
    if upper < lower:
        if math.isclose(
            upper,
            lower,
            rel_tol=0,
            abs_tol=_BOUNDARY_TOLERANCE,
        ):
            upper = lower
        else:
            raise ValueError("Geometry clamp range is inverted")
    if math.isclose(value, lower, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return lower
    if math.isclose(value, upper, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return upper
    return min(max(value, lower), upper)


def _contains_rect(outer: NormalizedRect, inner: NormalizedRect) -> bool:
    return (
        inner.x >= outer.x - _BOUNDARY_TOLERANCE
        and inner.y >= outer.y - _BOUNDARY_TOLERANCE
        and inner.x + inner.width <= outer.x + outer.width + _BOUNDARY_TOLERANCE
        and inner.y + inner.height <= outer.y + outer.height + _BOUNDARY_TOLERANCE
    )


def _contains_point(rect: NormalizedRect, point: NormalizedPoint) -> bool:
    return (
        rect.x - _BOUNDARY_TOLERANCE
        <= point.x
        <= rect.x + rect.width + _BOUNDARY_TOLERANCE
        and rect.y - _BOUNDARY_TOLERANCE
        <= point.y
        <= rect.y + rect.height + _BOUNDARY_TOLERANCE
    )


def _rects_close(left: NormalizedRect, right: NormalizedRect) -> bool:
    return all(
        math.isclose(
            left_value,
            right_value,
            rel_tol=0,
            abs_tol=_BOUNDARY_TOLERANCE,
        )
        for left_value, right_value in zip(
            (left.x, left.y, left.width, left.height),
            (right.x, right.y, right.width, right.height),
            strict=True,
        )
    )


def _aspect_close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=_ASPECT_RELATIVE_TOLERANCE,
        abs_tol=0,
    )


def _require_optional_instance(
    name: str,
    value: object | None,
    expected: type[object],
) -> None:
    if value is not None:
        _require_instance(name, value, expected)


_FULL_RECT = NormalizedRect(x=0, y=0, width=1, height=1)


__all__ = [
    "ImageTargetBox",
    "IntrinsicImageMetadata",
    "NormalizedPoint",
    "NormalizedRect",
    "ResolvedImageGeometry",
    "resolve_image_geometry",
]
