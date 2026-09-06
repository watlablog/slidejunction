from dataclasses import FrozenInstanceError, replace

import pytest

import slidejunction
from slidejunction import image_geometry
from slidejunction.image_geometry import (
    ImageTargetBox,
    IntrinsicImageMetadata,
    NormalizedPoint,
    NormalizedRect,
    ResolvedImageGeometry,
    resolve_image_geometry,
)
from slidejunction.layout import (
    Configuration,
    Crop,
    ElementKind,
    FocalPoint,
    ImageMedia,
    LayoutDocument,
    MediaFit,
    Theme,
    ThemePreset,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import validate_references
from slidejunction.resolver import ResolvedBlock, resolve_presentation


def _layout(media: ImageMedia | None = None) -> LayoutDocument:
    elements = (
        {} if media is None else {ElementKind.IMAGE_BLOCK: Configuration(media=media)}
    )
    return LayoutDocument(
        format_version=1,
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
            elements=elements,
        ),
    )


def _resolved_image(media: ImageMedia | None = None) -> ResolvedBlock:
    document = parse_markdown("![image](image.png)")
    layout = _layout(media)
    index = validate_references(document, layout).index
    presentation = resolve_presentation(document, layout, index)
    return presentation.items[0].blocks[0]


def _resolve(
    *,
    media: ImageMedia | None = None,
    intrinsic: tuple[float, float] = (4, 3),
    target: tuple[float, float] = (4, 3),
) -> ResolvedImageGeometry:
    return resolve_image_geometry(
        _resolved_image(media),
        IntrinsicImageMetadata(width=intrinsic[0], height=intrinsic[1]),
        ImageTargetBox(width=target[0], height=target[1]),
    )


def _assert_rect(actual: NormalizedRect, expected: NormalizedRect) -> None:
    assert (actual.x, actual.y, actual.width, actual.height) == pytest.approx(
        (expected.x, expected.y, expected.width, expected.height)
    )


@pytest.mark.parametrize(
    ("model", "width", "height"),
    [
        (IntrinsicImageMetadata, 4032, 3024),
        (IntrinsicImageMetadata, 3024, 4032),
        (IntrinsicImageMetadata, 100, 100),
        (ImageTargetBox, 16, 9),
        (ImageTargetBox, 9, 16),
        (ImageTargetBox, 1.5, 1.5),
    ],
)
def test_dimension_models_accept_positive_finite_numbers(
    model,
    width: float,
    height: float,
) -> None:
    value = model(width=width, height=height)

    assert value.width == float(width)
    assert value.height == float(height)


@pytest.mark.parametrize("model", [IntrinsicImageMetadata, ImageTargetBox])
@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("width", 0, ValueError),
        ("height", 0, ValueError),
        ("width", -1, ValueError),
        ("height", -1, ValueError),
        ("width", True, TypeError),
        ("height", False, TypeError),
        ("width", float("nan"), ValueError),
        ("height", float("inf"), ValueError),
        ("width", float("-inf"), ValueError),
        ("width", 10**400, ValueError),
    ],
)
def test_dimension_models_reject_invalid_values(
    model,
    field: str,
    value,
    error: type[Exception],
) -> None:
    values = {"width": 1, "height": 1, field: value}

    with pytest.raises(error):
        model(**values)


@pytest.mark.parametrize("model", [IntrinsicImageMetadata, ImageTargetBox])
@pytest.mark.parametrize(
    ("width", "height"),
    [(1e308, 1e-308), (5e-324, 1e308)],
)
def test_dimension_models_reject_unrepresentable_aspect_ratios(
    model,
    width: float,
    height: float,
) -> None:
    with pytest.raises(ValueError, match="aspect ratio"):
        model(width=width, height=height)


def test_normalized_point_snaps_boundaries_then_stores_exact_unit_values() -> None:
    point = NormalizedPoint(x=-5e-16, y=1 + 5e-16)

    assert point.x == 0.0
    assert point.y == 1.0
    assert 0 <= point.x <= 1
    assert 0 <= point.y <= 1


@pytest.mark.parametrize("value", [-2e-15, 1 + 2e-15])
def test_normalized_point_rejects_values_beyond_boundary_tolerance(
    value: float,
) -> None:
    with pytest.raises(ValueError, match="unit square"):
        NormalizedPoint(x=value, y=0.5)


def test_normalized_rect_snaps_unit_and_combined_edges_exactly() -> None:
    full = NormalizedRect(x=-5e-16, y=0, width=1 + 5e-16, height=1)
    right_edge = NormalizedRect(
        x=0.2,
        y=0.25,
        width=0.8 + 5e-16,
        height=0.75 + 5e-16,
    )

    assert full == NormalizedRect(x=0, y=0, width=1, height=1)
    assert right_edge.x + right_edge.width == 1
    assert right_edge.y + right_edge.height == 1
    for rect in (full, right_edge):
        assert 0 <= rect.x <= 1
        assert 0 <= rect.y <= 1
        assert 0 < rect.width <= 1
        assert 0 < rect.height <= 1
        assert rect.x + rect.width <= 1
        assert rect.y + rect.height <= 1


@pytest.mark.parametrize(
    "values",
    [
        {"x": -2e-15, "y": 0, "width": 1, "height": 1},
        {"x": 0, "y": 0, "width": 1 + 2e-15, "height": 1},
        {"x": 0.2, "y": 0, "width": 0.81, "height": 1},
        {"x": 0, "y": 0, "width": 0, "height": 1},
        {"x": 0, "y": 0, "width": True, "height": 1},
        {"x": 0, "y": 0, "width": float("nan"), "height": 1},
    ],
)
def test_normalized_rect_rejects_invalid_values(values) -> None:
    error = TypeError if values["width"] is True else ValueError
    with pytest.raises(error):
        NormalizedRect(**values)


@pytest.mark.parametrize(
    ("crop", "expected"),
    [
        (None, NormalizedRect(x=0, y=0, width=1, height=1)),
        (
            Crop(x=0, y=0, width=100, height=100),
            NormalizedRect(x=0, y=0, width=1, height=1),
        ),
        (Crop(x=10), NormalizedRect(x=0.1, y=0, width=0.9, height=1)),
        (Crop(y=20), NormalizedRect(x=0, y=0.2, width=1, height=0.8)),
        (Crop(width=60), NormalizedRect(x=0, y=0, width=0.6, height=1)),
        (Crop(height=70), NormalizedRect(x=0, y=0, width=1, height=0.7)),
        (
            Crop(x=10, y=20, width=50, height=60),
            NormalizedRect(x=0.1, y=0.2, width=0.5, height=0.6),
        ),
    ],
)
def test_sparse_crop_is_completed_to_an_original_asset_rect(
    crop: Crop | None,
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(media=ImageMedia(crop=crop))

    assert geometry.source_crop == expected
    _assert_rect(geometry.visible_source_rect, expected)


@pytest.mark.parametrize(
    ("intrinsic", "target"),
    [((16, 9), (16, 9)), ((9, 16), (16, 9)), ((1, 1), (3, 2))],
)
def test_stretch_uses_crop_and_full_destination_without_preserving_ratio(
    intrinsic: tuple[float, float],
    target: tuple[float, float],
) -> None:
    crop = Crop(x=10, y=20, width=50, height=60)
    geometry = _resolve(
        media=ImageMedia(
            crop=crop,
            fit=MediaFit.STRETCH,
            focal_point=FocalPoint(x=100, y=0),
        ),
        intrinsic=intrinsic,
        target=target,
    )

    assert geometry.visible_source_rect == geometry.source_crop
    assert geometry.destination_rect == NormalizedRect(x=0, y=0, width=1, height=1)
    assert geometry.effective_focal_point is None


@pytest.mark.parametrize(
    ("intrinsic", "target", "expected"),
    [
        ((4, 3), (8, 6), NormalizedRect(x=0, y=0, width=1, height=1)),
        ((2, 1), (1, 2), NormalizedRect(x=0, y=0.375, width=1, height=0.25)),
        ((1, 2), (2, 1), NormalizedRect(x=0.375, y=0, width=0.25, height=1)),
        ((1, 1), (2, 1), NormalizedRect(x=0.25, y=0, width=0.5, height=1)),
    ],
)
def test_contain_centers_the_complete_source_crop(
    intrinsic: tuple[float, float],
    target: tuple[float, float],
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(
        media=ImageMedia(fit=MediaFit.CONTAIN),
        intrinsic=intrinsic,
        target=target,
    )

    assert geometry.visible_source_rect == geometry.source_crop
    assert geometry.destination_rect == expected
    assert geometry.effective_focal_point is None


def test_contain_uses_cropped_source_ratio_and_ignores_focal_point() -> None:
    media = ImageMedia(
        crop=Crop(x=25, width=50),
        fit=MediaFit.CONTAIN,
        focal_point=FocalPoint(x=100, y=0),
    )

    geometry = _resolve(media=media, intrinsic=(2, 1), target=(1, 1))
    without_focal = _resolve(
        media=replace(media, focal_point=None),
        intrinsic=(2, 1),
        target=(1, 1),
    )

    assert geometry.destination_rect == NormalizedRect(x=0, y=0, width=1, height=1)
    assert geometry == without_focal


def test_near_but_unequal_aspect_ratio_does_not_take_equal_branch() -> None:
    geometry = _resolve(
        media=ImageMedia(fit=MediaFit.CONTAIN),
        intrinsic=(1.0000000000001, 1),
        target=(1, 1),
    )

    assert geometry.destination_rect.width == 1
    assert geometry.destination_rect.height < 1
    assert geometry.destination_rect != NormalizedRect(x=0, y=0, width=1, height=1)


@pytest.mark.parametrize(
    ("intrinsic", "target", "expected"),
    [
        ((1, 1), (1, 1), NormalizedRect(x=0, y=0, width=1, height=1)),
        ((2, 1), (1, 2), NormalizedRect(x=0.375, y=0, width=0.25, height=1)),
        ((1, 2), (2, 1), NormalizedRect(x=0, y=0.375, width=1, height=0.25)),
    ],
)
def test_cover_selects_a_centered_maximal_viewport(
    intrinsic: tuple[float, float],
    target: tuple[float, float],
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(
        media=ImageMedia(fit=MediaFit.COVER),
        intrinsic=intrinsic,
        target=target,
    )

    _assert_rect(geometry.visible_source_rect, expected)
    assert geometry.destination_rect == NormalizedRect(x=0, y=0, width=1, height=1)
    assert geometry.effective_focal_point == NormalizedPoint(x=0.5, y=0.5)


@pytest.mark.parametrize(
    ("crop", "target", "expected"),
    [
        (
            Crop(x=10, y=40, width=80, height=20),
            (1, 1),
            NormalizedRect(x=0.4, y=0.4, width=0.2, height=0.2),
        ),
        (
            Crop(x=40, y=10, width=20, height=80),
            (1, 1),
            NormalizedRect(x=0.4, y=0.4, width=0.2, height=0.2),
        ),
        (
            Crop(x=25, y=0, width=50, height=100),
            (1, 2),
            NormalizedRect(x=0.25, y=0, width=0.5, height=1),
        ),
    ],
)
def test_cover_handles_wide_narrow_and_exact_ratio_partial_crops(
    crop: Crop,
    target: tuple[float, float],
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(
        media=ImageMedia(crop=crop, fit=MediaFit.COVER),
        intrinsic=(1, 1),
        target=target,
    )

    _assert_rect(geometry.visible_source_rect, expected)


@pytest.mark.parametrize(
    ("target", "focal", "expected"),
    [
        (
            (1, 2),
            FocalPoint(x=20, y=20),
            NormalizedRect(x=0.2, y=0.2, width=0.25, height=0.5),
        ),
        (
            (1, 2),
            FocalPoint(x=70, y=70),
            NormalizedRect(x=0.45, y=0.2, width=0.25, height=0.5),
        ),
        (
            (2, 1),
            FocalPoint(x=20, y=20),
            NormalizedRect(x=0.2, y=0.2, width=0.5, height=0.25),
        ),
        (
            (2, 1),
            FocalPoint(x=70, y=70),
            NormalizedRect(x=0.2, y=0.45, width=0.5, height=0.25),
        ),
    ],
)
def test_cover_places_viewport_at_focal_point_then_constrains_crop_edges(
    target: tuple[float, float],
    focal: FocalPoint,
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(
        media=ImageMedia(
            crop=Crop(x=20, y=20, width=50, height=50),
            fit=MediaFit.COVER,
            focal_point=focal,
        ),
        intrinsic=(1, 1),
        target=target,
    )

    _assert_rect(geometry.visible_source_rect, expected)


@pytest.mark.parametrize(
    ("focal", "expected"),
    [
        (None, NormalizedPoint(x=0.45, y=0.45)),
        (FocalPoint(x=30), NormalizedPoint(x=0.3, y=0.45)),
        (FocalPoint(y=40), NormalizedPoint(x=0.45, y=0.4)),
        (FocalPoint(x=90, y=0), NormalizedPoint(x=0.7, y=0.2)),
    ],
)
def test_cover_completes_and_clamps_effective_focal_point(
    focal: FocalPoint | None,
    expected: NormalizedPoint,
) -> None:
    geometry = _resolve(
        media=ImageMedia(
            crop=Crop(x=20, y=20, width=50, height=50),
            fit=MediaFit.COVER,
            focal_point=focal,
        ),
        intrinsic=(1, 1),
        target=(1, 2),
    )

    assert geometry.effective_focal_point == expected


@pytest.mark.parametrize(
    ("intrinsic", "crop"),
    [
        ((1e308, 1), Crop(width=100, height=0.1)),
        ((5e-324, 1), Crop(width=1, height=100)),
    ],
)
def test_effective_source_ratio_rejects_overflow_or_underflow(
    intrinsic: tuple[float, float],
    crop: Crop,
) -> None:
    with pytest.raises(ValueError, match="effective source aspect ratio"):
        _resolve(
            media=ImageMedia(crop=crop, fit=MediaFit.CONTAIN),
            intrinsic=intrinsic,
            target=(1, 1),
        )


def test_result_constructor_checks_structure_without_recomputing_position() -> None:
    intrinsic = IntrinsicImageMetadata(width=1, height=1)
    target = ImageTargetBox(width=1, height=1)
    full = NormalizedRect(x=0, y=0, width=1, height=1)

    off_center_contain = ResolvedImageGeometry(
        intrinsic=intrinsic,
        target_box=target,
        fit=MediaFit.CONTAIN,
        source_crop=full,
        effective_focal_point=None,
        visible_source_rect=full,
        destination_rect=NormalizedRect(x=0, y=0.25, width=0.5, height=0.5),
    )
    non_focal_cover = ResolvedImageGeometry(
        intrinsic=intrinsic,
        target_box=target,
        fit=MediaFit.COVER,
        source_crop=full,
        effective_focal_point=NormalizedPoint(x=1, y=1),
        visible_source_rect=NormalizedRect(x=0, y=0, width=0.5, height=0.5),
        destination_rect=full,
    )

    assert off_center_contain.destination_rect.x == 0
    assert non_focal_cover.visible_source_rect.x == 0


def test_result_constructor_rejects_fit_specific_inconsistency() -> None:
    intrinsic = IntrinsicImageMetadata(width=1, height=1)
    target = ImageTargetBox(width=1, height=1)
    full = NormalizedRect(x=0, y=0, width=1, height=1)
    half = NormalizedRect(x=0, y=0, width=0.5, height=1)

    with pytest.raises(ValueError, match="focal point"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit=MediaFit.STRETCH,
            source_crop=full,
            effective_focal_point=NormalizedPoint(x=0.5, y=0.5),
            visible_source_rect=full,
            destination_rect=full,
        )
    with pytest.raises(ValueError, match="aspect ratio"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit=MediaFit.CONTAIN,
            source_crop=full,
            effective_focal_point=None,
            visible_source_rect=full,
            destination_rect=half,
        )
    with pytest.raises(ValueError, match="requires an effective focal point"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit=MediaFit.COVER,
            source_crop=full,
            effective_focal_point=None,
            visible_source_rect=full,
            destination_rect=full,
        )
    with pytest.raises(ValueError, match="inside source crop"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit=MediaFit.COVER,
            source_crop=NormalizedRect(x=0.2, y=0.2, width=0.5, height=0.5),
            effective_focal_point=NormalizedPoint(x=0.5, y=0.5),
            visible_source_rect=NormalizedRect(x=0.1, y=0.2, width=0.2, height=0.2),
            destination_rect=full,
        )


def test_aspect_ratio_lock_does_not_affect_render_geometry() -> None:
    common = {
        "crop": Crop(x=10, y=20, width=60, height=50),
        "fit": MediaFit.COVER,
        "focal_point": FocalPoint(x=65, y=10),
    }

    locked = _resolve(media=ImageMedia(aspect_ratio_locked=True, **common))
    unlocked = _resolve(media=ImageMedia(aspect_ratio_locked=False, **common))

    assert locked == unlocked


def test_m4_default_image_media_integrates_without_local_fallback() -> None:
    block = _resolved_image()

    geometry = resolve_image_geometry(
        block,
        IntrinsicImageMetadata(width=4, height=3),
        ImageTargetBox(width=16, height=9),
    )

    assert block.configuration.media == ImageMedia(
        aspect_ratio_locked=True,
        fit=MediaFit.STRETCH,
    )
    assert geometry.fit is MediaFit.STRETCH
    assert geometry.source_crop == NormalizedRect(x=0, y=0, width=1, height=1)


def test_geometry_is_deterministic_and_does_not_mutate_inputs() -> None:
    media = ImageMedia(
        crop=Crop(x=10, width=50),
        fit=MediaFit.COVER,
        focal_point=FocalPoint(x=90),
    )
    block = _resolved_image(media)
    intrinsic = IntrinsicImageMetadata(width=4032, height=3024)
    target = ImageTargetBox(width=300, height=500)

    first = resolve_image_geometry(block, intrinsic, target)
    second = resolve_image_geometry(block, intrinsic, target)

    assert first == second
    assert block.configuration.media.crop == Crop(x=10, width=50)
    assert block.configuration.media.focal_point == FocalPoint(x=90)
    assert intrinsic == IntrinsicImageMetadata(width=4032, height=3024)
    assert target == ImageTargetBox(width=300, height=500)
    with pytest.raises(FrozenInstanceError):
        first.fit = MediaFit.CONTAIN  # type: ignore[misc]


def test_geometry_rejects_non_image_blocks_and_wrong_argument_types() -> None:
    document = parse_markdown("text")
    layout = _layout()
    index = validate_references(document, layout).index
    paragraph = resolve_presentation(document, layout, index).items[0].blocks[0]
    intrinsic = IntrinsicImageMetadata(width=1, height=1)
    target = ImageTargetBox(width=1, height=1)

    with pytest.raises(ValueError, match="ImageBlock"):
        resolve_image_geometry(paragraph, intrinsic, target)
    with pytest.raises(TypeError, match="ResolvedBlock"):
        resolve_image_geometry(None, intrinsic, target)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="IntrinsicImageMetadata"):
        resolve_image_geometry(_resolved_image(), None, target)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ImageTargetBox"):
        resolve_image_geometry(_resolved_image(), intrinsic, None)  # type: ignore[arg-type]


def test_result_models_reject_wrong_runtime_types() -> None:
    full = NormalizedRect(x=0, y=0, width=1, height=1)
    intrinsic = IntrinsicImageMetadata(width=1, height=1)
    target = ImageTargetBox(width=1, height=1)

    with pytest.raises(TypeError, match="MediaFit"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit="stretch",  # type: ignore[arg-type]
            source_crop=full,
            effective_focal_point=None,
            visible_source_rect=full,
            destination_rect=full,
        )
    with pytest.raises(TypeError, match="IntrinsicImageMetadata"):
        replace(
            _resolve(),
            intrinsic=None,  # type: ignore[arg-type]
        )


def test_image_geometry_module_is_public_without_expanding_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "resolve_image_geometry")
    assert {
        "ImageTargetBox",
        "IntrinsicImageMetadata",
        "NormalizedPoint",
        "NormalizedRect",
        "ResolvedImageGeometry",
        "resolve_image_geometry",
    } == set(image_geometry.__all__)


def test_geometry_does_not_include_rendering_or_persistent_color_state() -> None:
    geometry = _resolve()

    assert not hasattr(geometry, "css")
    assert not hasattr(geometry, "transform")
    assert not hasattr(geometry, "appearance")
    assert not hasattr(geometry, "aspect_ratio_locked")
