from dataclasses import replace
from pathlib import Path

from slidejunction import Deck
from slidejunction.document import ImageBlock, Slide
from slidejunction.image_editing import set_image_crop
from slidejunction.image_geometry import (
    ImageTargetBox,
    IntrinsicImageMetadata,
    NormalizedRect,
    resolve_image_geometry,
)
from slidejunction.layout import (
    Configuration,
    ImageMedia,
    LayoutDocument,
    MediaFit,
    Stacking,
    Theme,
    ThemePreset,
    dump_layout,
)
from slidejunction.project import DeckSnapshot
from slidejunction.reference_editing import (
    detach_reference,
    edit_consumer_locally,
    set_consumer_reference,
)
from slidejunction.reference_gc import apply_reference_gc, plan_reference_gc
from slidejunction.resolver import ResolvedSlide
from slidejunction.stacking import order_blocks_for_paint, set_stacking_z_index


def test_no_ref_image_edit_closes_load_edit_save_resolve_geometry_loop(
    tmp_path: Path,
) -> None:
    deck, base = _project(tmp_path, "![photo](photo.png)")
    image = _source_blocks(base)[0]
    resolved_image = _resolved_blocks(base)[0]
    assert isinstance(image, ImageBlock)
    requested = NormalizedRect(x=0.1, y=0.2, width=0.6, height=0.5)

    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        image,
        editor=lambda local: set_image_crop(local, resolved_image, requested),
    )
    result = deck.save_reference_edit(base, edit)

    fresh = result.snapshot
    assert fresh is not None
    fresh_image = _source_blocks(fresh)[0]
    fresh_resolved = _resolved_blocks(fresh)[0]
    assert fresh_image.config_ref == 1
    geometry = resolve_image_geometry(
        fresh_resolved,
        IntrinsicImageMetadata(width=1600, height=900),
        ImageTargetBox(width=16, height=9),
    )
    assert geometry.source_crop == requested


def test_shared_image_local_edit_forks_only_selected_consumer(tmp_path: Path) -> None:
    source = (
        "<!-- sj:ref=3 -->\n"
        "![first](first.png)\n\n"
        "<!-- sj:ref=3 -->\n"
        "![second](second.png)"
    )
    original_definition = Configuration(media=ImageMedia(fit=MediaFit.CONTAIN))
    deck, base = _project(
        tmp_path,
        source,
        _layout(configurations={3: original_definition}),
    )
    selected, other = _source_blocks(base)
    requested = NormalizedRect(x=0.2, y=0.1, width=0.5, height=0.7)
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        selected,
        editor=lambda local: set_image_crop(
            local,
            _resolved_blocks(base)[0],
            requested,
        ),
    )

    assert (
        edit.layout_document.configurations[3] is base.layout_document.configurations[3]
    )
    assert edit.selected_ref_id == 4
    result = deck.save_reference_edit(base, edit)

    fresh = result.snapshot
    assert fresh is not None
    selected_after, other_after = _source_blocks(fresh)
    assert selected_after.config_ref == 4
    assert other_after.config_ref == 3
    assert fresh.layout_document.configurations[3] == original_definition
    assert fresh.layout_document.configurations[4].media.crop.x == 20
    assert other.config_ref == 3


def test_existing_reference_retarget_saves_source_only_and_reresolves(
    tmp_path: Path,
) -> None:
    deck, base = _project(
        tmp_path,
        "<!-- sj:ref=3 -->\r\nParagraph\r\n",
        _layout(
            configurations={
                3: Configuration(stacking=Stacking(z_index=1)),
                8: Configuration(stacking=Stacking(z_index=9)),
            }
        ),
    )
    layout_bytes = base.files.layout.path.read_bytes()
    edit = set_consumer_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _source_blocks(base)[0],
        ref_id=8,
    )

    saved = deck.save_reference_edit(base, edit)

    fresh = saved.snapshot
    assert fresh is not None
    assert saved.files.source.text == "<!-- sj:ref=8 -->\r\nParagraph\r\n"
    assert base.files.layout.path.read_bytes() == layout_bytes
    assert _source_blocks(fresh)[0].config_ref == 8
    assert _resolved_blocks(fresh)[0].configuration.stacking.z_index == 9


def test_detach_save_then_explicit_gc_and_layout_save(tmp_path: Path) -> None:
    deck, base = _project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        _layout(configurations={3: Configuration()}),
    )
    edit = detach_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _source_blocks(base)[0],
    )
    detached_result = deck.save_reference_edit(base, edit)
    detached = detached_result.snapshot
    assert detached is not None
    assert _source_blocks(detached)[0].config_ref is None
    assert 3 in detached.layout_document.configurations

    plan = plan_reference_gc(
        detached.source_document,
        detached.layout_document,
        detached.reference_validation.index,
    )
    collected = apply_reference_gc(
        detached.source_document,
        detached.layout_document,
        detached.reference_validation.index,
        plan,
    )
    saved = deck.save_layout(detached, collected)

    assert saved.snapshot is not None
    assert saved.snapshot.layout_document.configurations == {}
    assert saved.files.source.text == detached.files.source.text


def test_stacking_definition_edit_round_trips_to_fresh_paint_order(
    tmp_path: Path,
) -> None:
    source = "<!-- sj:ref=1 -->\nBack in source\n\n<!-- sj:ref=2 -->\nFront in source"
    deck, base = _project(
        tmp_path,
        source,
        _layout(configurations={1: Configuration(), 2: Configuration()}),
    )
    resolved_selected = _resolved_blocks(base)[0]
    updated = set_stacking_z_index(
        base.layout_document.configurations[1],
        resolved_selected,
        9,
    )
    candidate = replace(
        base.layout_document,
        configurations={**base.layout_document.configurations, 1: updated},
    )
    source_bytes = base.files.source.path.read_bytes()

    saved = deck.save_layout(base, candidate)

    fresh = saved.snapshot
    assert fresh is not None
    assert base.files.source.path.read_bytes() == source_bytes
    resolved = _resolved_blocks(fresh)
    ordered = order_blocks_for_paint(resolved)
    assert ordered == (resolved[1], resolved[0])
    assert fresh.layout_document.configurations[1].stacking == Stacking(z_index=9)


def _project(
    tmp_path: Path,
    source: str,
    layout: LayoutDocument | None = None,
) -> tuple[Deck, DeckSnapshot]:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / "slides.md").write_text(source, encoding="utf-8")
    if layout is not None:
        (deck.root / "layout.json").write_text(dump_layout(layout), encoding="utf-8")
    result = deck.load()
    assert result.snapshot is not None
    return deck, result.snapshot


def _layout(
    *,
    configurations: dict[int, Configuration],
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations=configurations,
    )


def _source_blocks(snapshot: DeckSnapshot) -> tuple:
    item = snapshot.source_document.presentation.items[0]
    assert isinstance(item, Slide)
    return item.blocks


def _resolved_blocks(snapshot: DeckSnapshot) -> tuple:
    item = snapshot.resolved_presentation.items[0]
    assert isinstance(item, ResolvedSlide)
    return item.blocks
