from dataclasses import FrozenInstanceError, fields, replace
from enum import StrEnum

import pytest

import slidejunction
from slidejunction import image_editing
from slidejunction.document import Diagnostic
from slidejunction.image_editing import (
    ImageResizeDriver,
    MaterializedImageSize,
    lock_image_aspect_ratio,
    reset_image_aspect_ratio_lock,
    reset_image_crop,
    reset_image_fit,
    reset_image_focal_point,
    resize_image_size,
    set_image_crop,
    set_image_fit,
    set_image_focal_point,
    unlock_image_aspect_ratio,
)
from slidejunction.image_geometry import (
    ImageTargetBox,
    IntrinsicImageMetadata,
    NormalizedPoint,
    NormalizedRect,
    resolve_image_geometry,
)
from slidejunction.layout import (
    Appearance,
    CodeConfig,
    Configuration,
    Crop,
    ElementKind,
    FocalPoint,
    ImageMedia,
    LayoutDocument,
    MediaFit,
    Outline,
    Placement,
    Size,
    Stacking,
    TextEffects,
    Theme,
    ThemePreset,
    Transform,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import validate_references
from slidejunction.resolver import ResolvedBlock, resolve_presentation

_CURRENT = MaterializedImageSize(width=40, height=25)
_OPERATIONS = (
    lock_image_aspect_ratio,
    unlock_image_aspect_ratio,
    reset_image_aspect_ratio_lock,
    resize_image_size,
    set_image_crop,
    reset_image_crop,
    set_image_focal_point,
    reset_image_focal_point,
    set_image_fit,
    reset_image_fit,
)
_RESETS = (
    (reset_image_aspect_ratio_lock, "aspect_ratio_locked", False),
    (reset_image_crop, "crop", Crop(x=10)),
    (reset_image_focal_point, "focal_point", FocalPoint(x=90)),
    (reset_image_fit, "fit", MediaFit.COVER),
)


def _layout(
    local: Configuration | None = None,
    media: ImageMedia | None = None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
            elements={ElementKind.IMAGE_BLOCK: Configuration(media=media)},
        ),
        configurations={3: Configuration() if local is None else local},
    )


def _resolve(document, layout):
    validation = validate_references(document, layout)
    assert not validation.diagnostics
    resolved = resolve_presentation(document, layout, validation.index)
    return resolved


def _resolved_image(media: ImageMedia | None = None) -> ResolvedBlock:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    return _resolve(document, _layout(media=media)).items[0].blocks[0]


def _geometry(block: ResolvedBlock):
    return resolve_image_geometry(
        block,
        IntrinsicImageMetadata(width=4, height=3),
        ImageTargetBox(width=4, height=3),
    )


def _rich_local() -> Configuration:
    return Configuration(
        placement=Placement(x=12, y=17),
        size=Size(width=33, height=22),
        transform=Transform(rotation=35),
        appearance=Appearance(opacity=0.75),
        typography=Typography(font_size=24),
        text_effects=TextEffects(outline=Outline(width=2)),
        code=CodeConfig(),
        stacking=Stacking(z_index=4),
        media=ImageMedia(
            aspect_ratio_locked=True,
            crop=Crop(x=10, y=20, width=50, height=60),
            focal_point=FocalPoint(x=90, y=5),
            fit=MediaFit.CONTAIN,
        ),
    )


def _arguments(operation, local, block):
    arguments = {"local_configuration": local}
    if operation.__name__.startswith("reset_"):
        return arguments
    arguments["resolved_image_block"] = block
    if operation in (unlock_image_aspect_ratio, resize_image_size):
        arguments["current_size"] = _CURRENT
    if operation is resize_image_size:
        arguments.update(driver=ImageResizeDriver.WIDTH, value=50)
    elif operation is set_image_crop:
        arguments["source_crop"] = NormalizedRect(x=0.2, y=0.1, width=0.5, height=0.7)
    elif operation is set_image_focal_point:
        arguments["point"] = NormalizedPoint(x=0.8, y=0.9)
    elif operation is set_image_fit:
        arguments["fit"] = MediaFit.COVER
    return arguments


def test_public_surface_and_resize_driver() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert set(image_editing.__all__) == {
        "ImageResizeDriver",
        "MaterializedImageSize",
        *(operation.__name__ for operation in _OPERATIONS),
    }
    assert len(image_editing.__all__) == 12
    assert issubclass(ImageResizeDriver, StrEnum)
    assert list(ImageResizeDriver) == [
        ImageResizeDriver.WIDTH,
        ImageResizeDriver.HEIGHT,
    ]
    assert [driver.value for driver in ImageResizeDriver] == ["width", "height"]


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (40, 25),
        (25, 40),
        (25, 25),
        (140, 125.5),
        (1e308, 5e-324),
        (5e-324, 1e308),
        (40.000000001, 25),
    ],
)
def test_materialized_size_canonicalizes_dimensions_without_ratio_constraint(
    width, height
) -> None:
    size = MaterializedImageSize(width=width, height=height)
    assert size.width == width
    assert size.height == height
    assert type(size.width) is float
    assert type(size.height) is float
    assert [field.name for field in fields(size)] == ["width", "height"]


@pytest.mark.parametrize("axis", ["width", "height"])
@pytest.mark.parametrize(
    ("value", "error"),
    [
        (True, TypeError),
        (False, TypeError),
        ("40", TypeError),
        (None, TypeError),
        (1 + 2j, TypeError),
        (0, ValueError),
        (-1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (float("-inf"), ValueError),
        (10**400, ValueError),
    ],
)
def test_materialized_size_rejects_invalid_dimensions(axis, value, error) -> None:
    with pytest.raises(error):
        MaterializedImageSize(**{"width": 40, "height": 25, axis: value})


def test_materialized_size_is_frozen_slotted_and_keyword_only() -> None:
    with pytest.raises(FrozenInstanceError):
        _CURRENT.width = 50
    assert not hasattr(_CURRENT, "__dict__")
    with pytest.raises(TypeError):
        MaterializedImageSize(40, 25)


def test_lock_on_only_sets_an_explicit_true_override() -> None:
    local = Configuration(size=Size(width=40), media=ImageMedia(fit=MediaFit.CONTAIN))
    result = lock_image_aspect_ratio(
        local, _resolved_image(ImageMedia(aspect_ratio_locked=False))
    )
    assert result == replace(
        local, media=replace(local.media, aspect_ratio_locked=True)
    )
    assert result.size is local.size
    assert reset_image_aspect_ratio_lock(result) == local


@pytest.mark.parametrize("local", [Configuration(), Configuration(media=ImageMedia())])
def test_lock_on_effective_true_is_identity_noop_without_pinning(local) -> None:
    assert lock_image_aspect_ratio(local, _resolved_image()) is local


@pytest.mark.parametrize("size", [None, Size(width=40), Size(width=70, height=90)])
def test_unlock_materializes_caller_visible_size(size) -> None:
    local = Configuration(size=size)
    result = unlock_image_aspect_ratio(local, _resolved_image(), _CURRENT)
    assert result.size == Size(width=40, height=25)
    assert result.media == ImageMedia(aspect_ratio_locked=False)
    reset = reset_image_aspect_ratio_lock(result)
    assert reset.media is None
    assert reset.size is result.size


def test_unlock_effective_false_does_not_materialize_size() -> None:
    local = Configuration(size=Size(width=40))
    block = _resolved_image(ImageMedia(aspect_ratio_locked=False))
    assert unlock_image_aspect_ratio(local, block, _CURRENT) is local
    assert local.size.height is None


@pytest.mark.parametrize("driver", list(ImageResizeDriver))
@pytest.mark.parametrize("other_value", [None, 17])
def test_unlocked_resize_changes_only_local_driver(driver, other_value) -> None:
    other_axis = "height" if driver is ImageResizeDriver.WIDTH else "width"
    local = Configuration(size=Size(**{other_axis: other_value}))
    result = resize_image_size(
        local,
        _resolved_image(ImageMedia(aspect_ratio_locked=False)),
        _CURRENT,
        driver=driver,
        value=150,
    )
    assert getattr(result.size, driver.value) == 150
    assert getattr(result.size, other_axis) == other_value
    assert result.media is None


@pytest.mark.parametrize("driver", list(ImageResizeDriver))
def test_unlocked_huge_integer_resize_preserves_value_and_int_type(driver) -> None:
    result = resize_image_size(
        Configuration(),
        _resolved_image(ImageMedia(aspect_ratio_locked=False)),
        _CURRENT,
        driver=driver,
        value=10**400,
    )
    stored = getattr(result.size, driver.value)
    assert stored == 10**400
    assert type(stored) is int
    other_axis = "height" if driver is ImageResizeDriver.WIDTH else "width"
    assert getattr(result.size, other_axis) is None


@pytest.mark.parametrize(
    ("driver", "value", "expected"),
    [
        (ImageResizeDriver.WIDTH, 50, Size(width=50, height=31.25)),
        (ImageResizeDriver.HEIGHT, 30, Size(width=48, height=30)),
        (ImageResizeDriver.WIDTH, 200, Size(width=200, height=125)),
    ],
)
def test_locked_resize_scales_visible_dimensions(driver, value, expected) -> None:
    local = Configuration(size=Size(width=7))
    result = resize_image_size(
        local, _resolved_image(), _CURRENT, driver=driver, value=value
    )
    assert result.size == expected
    assert type(getattr(result.size, driver.value)) is int
    assert result.media is None


@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("driver", list(ImageResizeDriver))
@pytest.mark.parametrize("as_float", [False, True])
def test_resize_exact_visible_value_is_identity_noop(locked, driver, as_float) -> None:
    local = Configuration()
    value = 40 if driver is ImageResizeDriver.WIDTH else 25
    if as_float:
        value = float(value)
    assert (
        resize_image_size(
            local,
            _resolved_image(ImageMedia(aspect_ratio_locked=locked)),
            _CURRENT,
            driver=driver,
            value=value,
        )
        is local
    )


@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("driver", list(ImageResizeDriver))
def test_resize_tiny_change_is_not_discarded(locked, driver) -> None:
    local = Configuration()
    value = getattr(_CURRENT, driver.value) + 1e-9
    result = resize_image_size(
        local,
        _resolved_image(ImageMedia(aspect_ratio_locked=locked)),
        _CURRENT,
        driver=driver,
        value=value,
    )
    assert result is not local
    assert getattr(result.size, driver.value) == value


@pytest.mark.parametrize("locked", [False, True])
def test_resize_compares_integer_request_before_float_conversion(locked) -> None:
    local = Configuration()
    result = resize_image_size(
        local,
        _resolved_image(ImageMedia(aspect_ratio_locked=locked)),
        MaterializedImageSize(width=float(2**53), height=25),
        driver=ImageResizeDriver.WIDTH,
        value=2**53 + 1,
    )
    assert result is not local
    assert result.size.width == 2**53 + 1
    assert type(result.size.width) is int


@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize(
    ("value", "error"),
    [
        (True, TypeError),
        (False, TypeError),
        ("40", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (float("-inf"), ValueError),
    ],
)
def test_resize_rejects_invalid_request(locked, value, error) -> None:
    with pytest.raises(error):
        resize_image_size(
            Configuration(),
            _resolved_image(ImageMedia(aspect_ratio_locked=locked)),
            _CURRENT,
            driver=ImageResizeDriver.WIDTH,
            value=value,
        )


@pytest.mark.parametrize("driver", list(ImageResizeDriver))
@pytest.mark.parametrize(
    ("current_driver", "current_other", "value"),
    [
        (5e-324, 25, 1e308),
        (1e308, 25, 5e-324),
        (2, 5e-324, 0.5),
        (1, 1e308, 2),
        (40, 25, 10**400),
    ],
)
def test_locked_resize_rejects_scale_and_derived_overflow_underflow(
    driver, current_driver, current_other, value
) -> None:
    other_axis = "height" if driver is ImageResizeDriver.WIDTH else "width"
    size = MaterializedImageSize(
        **{driver.value: current_driver, other_axis: current_other}
    )
    with pytest.raises(ValueError):
        resize_image_size(
            Configuration(), _resolved_image(), size, driver=driver, value=value
        )


def test_resize_driver_and_value_are_keyword_only() -> None:
    with pytest.raises(TypeError):
        resize_image_size(
            Configuration(), _resolved_image(), _CURRENT, ImageResizeDriver.WIDTH, 50
        )


@pytest.mark.parametrize(
    ("rect", "expected"),
    [
        (
            NormalizedRect(x=0.1, y=0.2, width=0.5, height=0.6),
            Crop(x=10, y=20, width=50, height=60),
        ),
        (
            NormalizedRect(x=0, y=0, width=1, height=1),
            Crop(x=0, y=0, width=100, height=100),
        ),
        (
            NormalizedRect(
                x=0.123456789012345, y=0.0123456789012345, width=0.2, height=0.3
            ),
            Crop(
                x=0.123456789012345 * 100,
                y=0.0123456789012345 * 100,
                width=20,
                height=30,
            ),
        ),
    ],
)
def test_set_crop_saves_complete_percentages_without_rounding(rect, expected) -> None:
    result = set_image_crop(
        Configuration(), _resolved_image(ImageMedia(crop=Crop(x=20))), rect
    )
    assert result.media.crop == expected
    assert all(
        getattr(result.media.crop, field.name) is not None for field in fields(Crop)
    )


def test_set_crop_preserves_exact_right_and_bottom_edges() -> None:
    rect = NormalizedRect(x=0.013, y=0.026, width=1 - 0.013, height=1 - 0.026)
    result = set_image_crop(Configuration(), _resolved_image(), rect)
    crop = result.media.crop
    assert crop.x == rect.x * 100
    assert crop.y == rect.y * 100
    assert crop.width == 100 - crop.x
    assert crop.height == 100 - crop.y
    assert crop.x + crop.width == 100
    assert crop.y + crop.height == 100


@pytest.mark.parametrize(
    ("crop", "rect"),
    [
        (None, NormalizedRect(x=0, y=0, width=1, height=1)),
        (Crop(), NormalizedRect(x=0, y=0, width=1, height=1)),
        (Crop(x=10), NormalizedRect(x=0.1, y=0, width=0.9, height=1)),
        (Crop(y=20), NormalizedRect(x=0, y=0.2, width=1, height=0.8)),
        (Crop(width=50, height=60), NormalizedRect(x=0, y=0, width=0.5, height=0.6)),
        (
            Crop(x=1.3, y=2.6, width=50, height=50),
            NormalizedRect(x=0.013, y=0.026, width=0.5, height=0.5),
        ),
    ],
)
def test_crop_canonical_persistent_equality_is_identity_noop_without_pinning(
    crop, rect
) -> None:
    local = Configuration()
    block = _resolved_image(ImageMedia(crop=crop))
    assert set_image_crop(local, block, rect) is local
    assert local.media is None


def test_non_binary_crop_noop_is_not_normalized_float_equality() -> None:
    block = _resolved_image(ImageMedia(crop=Crop(x=1.3, y=2.6, width=50, height=50)))
    requested = NormalizedRect(x=0.013, y=0.026, width=0.5, height=0.5)
    assert _geometry(block).source_crop != requested
    local = Configuration()
    assert set_image_crop(local, block, requested) is local


def test_crop_nearby_distinct_persistent_value_is_an_edit() -> None:
    local = Configuration()
    requested = NormalizedRect(x=0.013 + 1e-12, y=0.026, width=0.5, height=0.5)
    result = set_image_crop(
        local,
        _resolved_image(ImageMedia(crop=Crop(x=1.3, y=2.6, width=50, height=50))),
        requested,
    )
    assert result is not local
    assert result.media.crop.x == requested.x * 100


@pytest.mark.parametrize("fit", list(MediaFit))
@pytest.mark.parametrize(
    "point",
    [
        NormalizedPoint(x=0.9, y=0.1),
        NormalizedPoint(x=0, y=1),
        NormalizedPoint(x=0.123456789012345, y=0.0123456789012345),
    ],
)
def test_focal_saves_complete_original_asset_coordinates_without_clamp_or_fit_change(
    fit, point
) -> None:
    local = Configuration(
        media=ImageMedia(crop=Crop(x=20, y=20, width=50, height=50), fit=fit)
    )
    block = _resolved_image(local.media)
    result = set_image_focal_point(local, block, point)
    assert result.media.focal_point == FocalPoint(x=point.x * 100, y=point.y * 100)
    assert result.media.crop is local.media.crop
    assert result.media.fit is fit


@pytest.mark.parametrize(
    ("crop", "focal", "requested"),
    [
        (None, None, NormalizedPoint(x=0.5, y=0.5)),
        (Crop(x=25), FocalPoint(y=40), NormalizedPoint(x=0.625, y=0.4)),
        (Crop(y=25), FocalPoint(x=90), NormalizedPoint(x=0.9, y=0.625)),
        (Crop(x=9, width=50), None, NormalizedPoint(x=0.34, y=0.5)),
        (None, FocalPoint(x=1.3, y=2.6), NormalizedPoint(x=0.013, y=0.026)),
    ],
)
def test_focal_completed_candidate_canonical_equality_is_identity_noop(
    crop, focal, requested
) -> None:
    local = Configuration()
    block = _resolved_image(ImageMedia(crop=crop, focal_point=focal))
    assert set_image_focal_point(local, block, requested) is local
    assert local.media is None


def test_non_binary_focal_noop_is_not_normalized_float_equality() -> None:
    assert 1.3 / 100 != 0.013
    assert 0.09 + 0.5 / 2 != 0.34
    local = Configuration()
    assert (
        set_image_focal_point(
            local,
            _resolved_image(ImageMedia(focal_point=FocalPoint(x=1.3, y=2.6))),
            NormalizedPoint(x=0.013, y=0.026),
        )
        is local
    )
    assert (
        set_image_focal_point(
            local,
            _resolved_image(ImageMedia(crop=Crop(x=9, width=50))),
            NormalizedPoint(x=0.34, y=0.5),
        )
        is local
    )


def test_focal_nearby_distinct_persistent_value_is_an_edit() -> None:
    local = Configuration()
    requested = NormalizedPoint(x=0.013 + 1e-12, y=0.026)
    result = set_image_focal_point(
        local,
        _resolved_image(ImageMedia(focal_point=FocalPoint(x=1.3, y=2.6))),
        requested,
    )
    assert result is not local
    assert result.media.focal_point.x == requested.x * 100


def test_focal_noop_compares_unclamped_intent_instead_of_rendered_point() -> None:
    local = Configuration()
    block = _resolved_image(
        ImageMedia(
            crop=Crop(x=20, width=50), focal_point=FocalPoint(x=90), fit=MediaFit.COVER
        )
    )
    assert _geometry(block).effective_focal_point == NormalizedPoint(x=0.7, y=0.5)
    assert set_image_focal_point(local, block, NormalizedPoint(x=0.9, y=0.5)) is local
    result = set_image_focal_point(local, block, NormalizedPoint(x=0.7, y=0.5))
    assert result is not local
    assert result.media.focal_point == FocalPoint(x=70, y=50)


def test_focal_candidate_does_not_snap_through_a_normalized_point_before_comparison() -> (
    None
):
    local = Configuration()
    block = _resolved_image(ImageMedia(focal_point=FocalPoint(x=5e-14, y=50)))
    result = set_image_focal_point(local, block, NormalizedPoint(x=0, y=0.5))
    assert result is not local
    assert result.media.focal_point == FocalPoint(x=0, y=50)


@pytest.mark.parametrize("fit", list(MediaFit))
def test_set_fit_writes_requested_enum(fit) -> None:
    current_fit = MediaFit.CONTAIN if fit is MediaFit.STRETCH else MediaFit.STRETCH
    result = set_image_fit(
        Configuration(), _resolved_image(ImageMedia(fit=current_fit)), fit
    )
    assert result.media == ImageMedia(fit=fit)


@pytest.mark.parametrize("fit", list(MediaFit))
def test_set_effective_fit_is_identity_noop_without_pinning(fit) -> None:
    local = Configuration()
    assert set_image_fit(local, _resolved_image(ImageMedia(fit=fit)), fit) is local


@pytest.mark.parametrize(("reset", "leaf", "value"), _RESETS)
def test_reset_only_removes_target_leaf_and_preserves_siblings(
    reset, leaf, value
) -> None:
    local = _rich_local()
    result = reset(local)
    assert getattr(result.media, leaf) is None
    for field in fields(ImageMedia):
        if field.name != leaf:
            assert getattr(result.media, field.name) is getattr(local.media, field.name)
    for field in fields(Configuration):
        if field.name != "media":
            assert getattr(result, field.name) is getattr(local, field.name)
    assert reset(result) is result


@pytest.mark.parametrize(("reset", "leaf", "value"), _RESETS)
def test_reset_compacts_only_newly_emptied_media(reset, leaf, value) -> None:
    local = Configuration(
        media=ImageMedia(**{leaf: value}), size=Size(), code=CodeConfig()
    )
    result = reset(local)
    assert result.media is None
    assert result.size is local.size
    assert result.code is local.code


@pytest.mark.parametrize(("reset", "leaf", "value"), _RESETS)
@pytest.mark.parametrize("media", [None, ImageMedia()])
def test_reset_missing_leaf_is_identity_noop_and_keeps_empty_media(
    reset, leaf, value, media
) -> None:
    local = Configuration(media=media)
    assert reset(local) is local
    assert local.media is media


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_edits_are_deterministic_preserve_inputs_and_unrelated_container_identity(
    operation,
) -> None:
    local = _rich_local()
    if operation is lock_image_aspect_ratio:
        local = replace(local, media=replace(local.media, aspect_ratio_locked=False))
    block = _resolved_image(local.media)
    block_before = replace(block)
    local_before = replace(local)
    arguments = _arguments(operation, local, block)
    result = operation(**arguments)
    assert isinstance(result, Configuration)
    assert result is not local
    assert result == operation(**arguments)
    assert local == local_before
    assert block == block_before
    changed = {"size"} if operation is resize_image_size else {"media"}
    if operation is unlock_image_aspect_ratio:
        changed.add("size")
    for field in fields(Configuration):
        if field.name not in changed:
            assert getattr(result, field.name) is getattr(local, field.name)
    if "media" in changed:
        affected_leaf = {
            lock_image_aspect_ratio: "aspect_ratio_locked",
            unlock_image_aspect_ratio: "aspect_ratio_locked",
            reset_image_aspect_ratio_lock: "aspect_ratio_locked",
            set_image_crop: "crop",
            reset_image_crop: "crop",
            set_image_focal_point: "focal_point",
            reset_image_focal_point: "focal_point",
            set_image_fit: "fit",
            reset_image_fit: "fit",
        }[operation]
        for field in fields(ImageMedia):
            if field.name != affected_leaf:
                assert getattr(result.media, field.name) is getattr(
                    local.media, field.name
                )


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_transactions_do_not_open_files_or_generate_diagnostics(
    operation, monkeypatch
) -> None:
    local = _rich_local()
    if operation is lock_image_aspect_ratio:
        local = replace(local, media=replace(local.media, aspect_ratio_locked=False))
    arguments = _arguments(operation, local, _resolved_image(local.media))

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Image transactions must not open files or generate diagnostics"
        )

    with monkeypatch.context() as guard:
        guard.setattr("builtins.open", forbidden)
        guard.setattr("io.open", forbidden)
        guard.setattr(Diagnostic, "__post_init__", forbidden)
        result = operation(**arguments)
    assert isinstance(result, Configuration)
    assert result is not local


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_every_operation_rejects_wrong_local_configuration_type(operation) -> None:
    with pytest.raises(TypeError):
        operation(**_arguments(operation, None, _resolved_image()))


@pytest.mark.parametrize(
    "operation", [op for op in _OPERATIONS if not op.__name__.startswith("reset_")]
)
@pytest.mark.parametrize("wrong_block", [None, Configuration(), "image"])
def test_context_operations_reject_wrong_resolved_block_type(
    operation, wrong_block
) -> None:
    with pytest.raises(TypeError):
        operation(**_arguments(operation, Configuration(), wrong_block))


@pytest.mark.parametrize(
    "operation", [op for op in _OPERATIONS if not op.__name__.startswith("reset_")]
)
def test_context_operations_reject_non_image_blocks(operation) -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\nparagraph")
    block = _resolve(document, _layout()).items[0].blocks[0]
    with pytest.raises(ValueError):
        operation(**_arguments(operation, Configuration(), block))


@pytest.mark.parametrize(
    ("operation", "argument", "wrong", "media"),
    [
        (
            unlock_image_aspect_ratio,
            "current_size",
            Size(width=40, height=25),
            ImageMedia(aspect_ratio_locked=False),
        ),
        (resize_image_size, "current_size", Size(width=40, height=25), ImageMedia()),
        (resize_image_size, "driver", "width", ImageMedia()),
        (resize_image_size, "driver", MediaFit.COVER, ImageMedia()),
        (
            set_image_crop,
            "source_crop",
            Crop(x=0, y=0, width=100, height=100),
            ImageMedia(),
        ),
        (set_image_focal_point, "point", FocalPoint(x=50, y=50), ImageMedia()),
        (set_image_fit, "fit", "stretch", ImageMedia()),
    ],
)
def test_other_public_types_are_validated_even_when_effective_state_would_noop(
    operation, argument, wrong, media
) -> None:
    arguments = _arguments(operation, Configuration(), _resolved_image(media))
    if operation is resize_image_size:
        arguments["value"] = 40
    arguments[argument] = wrong
    with pytest.raises(TypeError):
        operation(**arguments)


@pytest.mark.parametrize(
    ("operation", "local", "media"),
    [
        (
            lock_image_aspect_ratio,
            Configuration(media=ImageMedia(aspect_ratio_locked=True)),
            ImageMedia(aspect_ratio_locked=False),
        ),
        (
            unlock_image_aspect_ratio,
            Configuration(
                size=Size(width=40, height=25),
                media=ImageMedia(aspect_ratio_locked=False),
            ),
            ImageMedia(aspect_ratio_locked=True),
        ),
        (
            resize_image_size,
            Configuration(size=Size(width=50)),
            ImageMedia(aspect_ratio_locked=False),
        ),
        (
            set_image_crop,
            Configuration(media=ImageMedia(crop=Crop(x=20, y=10, width=50, height=70))),
            ImageMedia(),
        ),
        (
            set_image_focal_point,
            Configuration(media=ImageMedia(focal_point=FocalPoint(x=80, y=90))),
            ImageMedia(),
        ),
        (
            set_image_fit,
            Configuration(media=ImageMedia(fit=MediaFit.COVER)),
            ImageMedia(),
        ),
    ],
)
def test_equal_constructed_configuration_reuses_original_without_ownership_validation(
    operation, local, media
) -> None:
    assert operation(**_arguments(operation, local, _resolved_image(media))) is local


@pytest.mark.parametrize(("reset", "leaf", "value"), _RESETS)
def test_reset_reresolves_upstream_values_with_a_fresh_reference_index(
    reset, leaf, value
) -> None:
    upstream = ImageMedia(
        aspect_ratio_locked=False,
        crop=Crop(x=5, y=10, width=60, height=70),
        focal_point=FocalPoint(x=80, y=90),
        fit=MediaFit.COVER,
    )
    local = _rich_local()
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    original_layout = _layout(local, upstream)
    before = _resolve(document, original_layout).items[0].blocks[0]
    edited = reset(local)
    updated_layout = replace(original_layout, configurations={3: edited})
    after = _resolve(document, updated_layout).items[0].blocks[0]
    assert getattr(after.configuration.media, leaf) == getattr(upstream, leaf)
    assert getattr(before.configuration.media, leaf) == getattr(local.media, leaf)
    assert original_layout.configurations[3] is local
    assert document.presentation.items[0].blocks[0].config_ref == 3
    assert edited.size is local.size


def test_reset_fit_and_lock_restore_builtins_without_inventing_local_values() -> None:
    local = Configuration(
        media=ImageMedia(fit=MediaFit.COVER, aspect_ratio_locked=False)
    )
    edited = reset_image_aspect_ratio_lock(reset_image_fit(local))
    assert edited.media is None
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    block = _resolve(document, _layout(edited)).items[0].blocks[0]
    assert block.configuration.media.fit is MediaFit.STRETCH
    assert block.configuration.media.aspect_ratio_locked is True


def test_full_crop_set_and_reset_have_distinct_reresolved_meanings() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    upstream = ImageMedia(
        crop=Crop(x=20, y=10, width=50, height=70), fit=MediaFit.COVER
    )
    local = Configuration(media=ImageMedia(focal_point=FocalPoint(x=95, y=0)))
    layout = _layout(local, upstream)
    block = _resolve(document, layout).items[0].blocks[0]
    full = set_image_crop(local, block, NormalizedRect(x=0, y=0, width=1, height=1))
    full_block = (
        _resolve(document, replace(layout, configurations={3: full})).items[0].blocks[0]
    )
    assert _geometry(full_block).source_crop == NormalizedRect(
        x=0, y=0, width=1, height=1
    )
    reset = reset_image_crop(full)
    reset_block = (
        _resolve(document, replace(layout, configurations={3: reset}))
        .items[0]
        .blocks[0]
    )
    assert reset_block.configuration.media.crop == upstream.crop
    assert reset.media.focal_point is local.media.focal_point
    assert _geometry(reset_block).effective_focal_point == NormalizedPoint(x=0.7, y=0.1)


def test_reset_focal_without_upstream_uses_dynamic_crop_center() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    local = Configuration(
        media=ImageMedia(
            crop=Crop(x=20, y=10, width=50, height=70),
            focal_point=FocalPoint(x=95),
            fit=MediaFit.COVER,
        )
    )
    reset = reset_image_focal_point(local)
    layout = _layout(reset)
    block = _resolve(document, layout).items[0].blocks[0]
    assert block.configuration.media.focal_point is None
    assert _geometry(block).effective_focal_point == NormalizedPoint(
        x=0.2 + 0.5 / 2, y=0.1 + 0.7 / 2
    )
    changed = set_image_crop(
        reset, block, NormalizedRect(x=0.1, y=0.2, width=0.4, height=0.6)
    )
    changed_block = (
        _resolve(document, replace(layout, configurations={3: changed}))
        .items[0]
        .blocks[0]
    )
    geometry = _geometry(changed_block)
    assert geometry.effective_focal_point == NormalizedPoint(
        x=geometry.source_crop.x + geometry.source_crop.width / 2,
        y=geometry.source_crop.y + geometry.source_crop.height / 2,
    )


def test_unlock_and_locked_resize_persist_size_through_m3_m4_and_lock_reset() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    local = Configuration(size=Size(width=40))
    layout = _layout(local)
    initial = _resolve(document, layout).items[0].blocks[0]
    resized = resize_image_size(
        local, initial, _CURRENT, driver=ImageResizeDriver.WIDTH, value=50
    )
    resized_layout = replace(layout, configurations={3: resized})
    resized_block = _resolve(document, resized_layout).items[0].blocks[0]
    assert resized_block.configuration.size == Size(width=50, height=31.25)
    unlocked = unlock_image_aspect_ratio(
        resized, resized_block, MaterializedImageSize(width=50, height=31.25)
    )
    unlocked_block = (
        _resolve(document, replace(layout, configurations={3: unlocked}))
        .items[0]
        .blocks[0]
    )
    assert unlocked_block.configuration.size == Size(width=50, height=31.25)
    assert unlocked_block.configuration.media.aspect_ratio_locked is False
    reset = reset_image_aspect_ratio_lock(unlocked)
    reset_block = (
        _resolve(document, replace(layout, configurations={3: reset}))
        .items[0]
        .blocks[0]
    )
    assert reset_block.configuration.media.aspect_ratio_locked is True
    assert reset_block.configuration.size == Size(width=50, height=31.25)
    assert _geometry(unlocked_block) == _geometry(reset_block)


def test_shared_image_and_text_configuration_retains_stored_capability_fields() -> None:
    document = parse_markdown(
        "<!-- sj:ref=3 -->\n![image](image.png)\n\n<!-- sj:ref=3 -->\ntext"
    )
    local = _rich_local()
    layout = _layout(local)
    before = _resolve(document, layout)
    image_before, text_before = before.items[0].blocks
    edited = set_image_focal_point(local, image_before, NormalizedPoint(x=0.7, y=0.8))
    after = _resolve(document, replace(layout, configurations={3: edited}))
    image_after, text_after = after.items[0].blocks
    assert edited.typography is local.typography
    assert edited.text_effects is local.text_effects
    assert edited.code is local.code
    assert text_after.configuration == text_before.configuration
    assert image_after.configuration.media.focal_point == FocalPoint(x=70, y=80)
    assert image_after.configuration.typography is None
    assert layout.configurations[3] is local


def test_crop_boundary_snap_precedes_focal_candidate_completion() -> None:
    media = ImageMedia(crop=Crop(x=5e-14, width=40), fit=MediaFit.COVER)
    block = _resolved_image(media)
    geometry = _geometry(block)
    assert geometry.source_crop.x == 0
    assert geometry.effective_focal_point == NormalizedPoint(x=0.2, y=0.5)
    local = Configuration()
    assert set_image_focal_point(local, block, NormalizedPoint(x=0.2, y=0.5)) is local


def test_geometry_clamps_focal_before_constructing_normalized_point() -> None:
    media = ImageMedia(
        crop=Crop(x=2e-13, width=50),
        focal_point=FocalPoint(x=5e-14),
        fit=MediaFit.COVER,
    )
    geometry = _geometry(_resolved_image(media))
    assert geometry.source_crop.x == 2e-15
    assert geometry.effective_focal_point.x == 2e-15
    assert geometry.effective_focal_point.y == 0.5


def test_geometry_constructs_normalized_point_after_clamp_to_a_near_zero_edge() -> None:
    media = ImageMedia(
        crop=Crop(width=5e-14),
        focal_point=FocalPoint(x=90),
        fit=MediaFit.COVER,
    )
    geometry = _geometry(_resolved_image(media))
    assert geometry.source_crop.width == 5e-16
    assert geometry.effective_focal_point.x == 0


def test_geometry_keeps_raw_focal_candidate_until_near_right_crop_clamp() -> None:
    x_percent = 99.99999999999989
    block = _resolved_image(
        ImageMedia(crop=Crop(x=x_percent, width=100 - x_percent), fit=MediaFit.COVER)
    )
    geometry = _geometry(block)
    crop = geometry.source_crop
    assert crop.x == 0.9999999999999989
    assert crop.width == 1.1102230246251565e-15
    assert NormalizedPoint(x=crop.x + crop.width / 2, y=0.5).x == 1
    assert geometry.effective_focal_point.x == crop.x


def test_crop_combined_edge_snap_precedes_focal_center_completion() -> None:
    media = ImageMedia(crop=Crop(x=20, width=79.99999999999996), fit=MediaFit.COVER)
    block = _resolved_image(media)
    geometry = _geometry(block)
    assert geometry.source_crop.width == 0.8
    assert geometry.effective_focal_point.x == 0.2 + 0.8 / 2
    local = Configuration()
    assert (
        set_image_focal_point(local, block, NormalizedPoint(x=0.2 + 0.8 / 2, y=0.5))
        is local
    )


def test_crop_and_focal_edits_feed_geometry_with_original_asset_semantics() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    local = Configuration(media=ImageMedia(fit=MediaFit.COVER))
    layout = _layout(local)
    block = _resolve(document, layout).items[0].blocks[0]
    cropped = set_image_crop(
        local, block, NormalizedRect(x=0.2, y=0.1, width=0.5, height=0.7)
    )
    crop_block = (
        _resolve(document, replace(layout, configurations={3: cropped}))
        .items[0]
        .blocks[0]
    )
    focused = set_image_focal_point(cropped, crop_block, NormalizedPoint(x=0.9, y=0))
    focused_block = (
        _resolve(document, replace(layout, configurations={3: focused}))
        .items[0]
        .blocks[0]
    )
    geometry = _geometry(focused_block)
    assert focused.media.focal_point == FocalPoint(x=90, y=0)
    assert geometry.source_crop == NormalizedRect(x=0.2, y=0.1, width=0.5, height=0.7)
    assert geometry.effective_focal_point == NormalizedPoint(x=0.7, y=0.1)
    assert geometry.visible_source_rect.x == geometry.source_crop.x
    assert geometry.visible_source_rect.y == geometry.source_crop.y
