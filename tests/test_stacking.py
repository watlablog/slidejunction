from dataclasses import fields, replace

import pytest

import slidejunction
from slidejunction import stacking
from slidejunction.document import Diagnostic
from slidejunction.layout import (
    Appearance,
    CodeConfig,
    Configuration,
    ImageMedia,
    LayoutDocument,
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
from slidejunction.resolver import ResolvedPlacementMode, resolve_presentation
from slidejunction.stacking import (
    order_blocks_for_paint,
    reset_stacking_z_index,
    set_stacking_z_index,
)


def _layout(configurations=None):
    return LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
    )


def _resolve(source, layout):
    index = validate_references(source, layout).index
    return resolve_presentation(source, layout, index)


def _blocks(*z_indices):
    source = parse_markdown(
        "\n\n".join(
            f"<!-- sj:ref={i + 1} -->\nBlock {i}" for i in range(len(z_indices))
        )
    )
    layout = _layout(
        {
            i + 1: Configuration(stacking=Stacking(z_index=z_index))
            for i, z_index in enumerate(z_indices)
        }
    )
    return _resolve(source, layout).items[0].blocks


def _rich_local(z_index=4):
    return Configuration(
        placement=Placement(x=12, y=17),
        size=Size(width=33, height=22),
        transform=Transform(rotation=35),
        typography=Typography(font_size=24),
        text_effects=TextEffects(),
        appearance=Appearance(opacity=0.75),
        media=ImageMedia(aspect_ratio_locked=False),
        stacking=Stacking(z_index=z_index),
        code=CodeConfig(),
    )


def test_public_surface() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert stacking.__all__ == [
        "order_blocks_for_paint",
        "reset_stacking_z_index",
        "set_stacking_z_index",
    ]


def test_empty_and_singleton_order_preserve_identity() -> None:
    assert order_blocks_for_paint(()) == ()
    blocks = _blocks(100)
    assert order_blocks_for_paint(blocks) is blocks
    assert order_blocks_for_paint(blocks)[0] is blocks[0]


@pytest.mark.parametrize(
    ("z_indices", "expected_indices"),
    [
        ((0, 5, 0, -1), (3, 0, 2, 1)),
        ((0, 0, 0), (0, 1, 2)),
        ((100, -100, 20, -3), (1, 3, 2, 0)),
        ((10**400, 0, -(10**400)), (2, 1, 0)),
        ((-10, -100, -10), (1, 0, 2)),
    ],
)
def test_paint_order_is_stable_back_to_front(z_indices, expected_indices) -> None:
    blocks = _blocks(*z_indices)
    original = tuple(blocks)
    expected = tuple(blocks[i] for i in expected_indices)
    ordered = order_blocks_for_paint(blocks)
    assert ordered == expected
    assert all(a is b for a, b in zip(ordered, expected, strict=True))
    assert all(a is b for a, b in zip(blocks, original, strict=True))
    assert order_blocks_for_paint(blocks) == ordered


def test_ties_use_input_order_even_when_source_spans_suggest_otherwise() -> None:
    first, second = _blocks(0, 0)
    assert first.node.source_binding.syntax_span.start_offset < (
        second.node.source_binding.syntax_span.start_offset
    )
    blocks = (second, first)
    assert order_blocks_for_paint(blocks) is blocks


def test_slide_title_can_be_passed_as_an_ordinary_direct_sibling() -> None:
    source = parse_markdown("<!-- sj:ref=1 -->\n## Title\n\nBody\n")
    layout = _layout({1: Configuration(stacking=Stacking(z_index=5))})
    slide = _resolve(source, layout).items[0]
    blocks = (slide.title, *slide.blocks)
    assert order_blocks_for_paint(blocks) == (*slide.blocks, slide.title)
    assert order_blocks_for_paint(blocks)[-1] is slide.title


@pytest.mark.parametrize("container_source", ["- child", "> child"])
def test_nested_children_do_not_escape_parent_stacking_unit(container_source) -> None:
    source = parse_markdown(f"{container_source}\n\nother\n")
    parent, other = _resolve(source, _layout()).items[0].blocks
    if parent.list_items:
        item = parent.list_items[0]
        child = item.blocks[0]
    else:
        child = parent.blocks[0]
    child = replace(
        child,
        configuration=replace(child.configuration, stacking=Stacking(z_index=10**400)),
    )
    if parent.list_items:
        parent = replace(parent, list_items=(replace(item, blocks=(child,)),))
    else:
        parent = replace(parent, blocks=(child,))
    blocks = (parent, other)
    ordered = order_blocks_for_paint(blocks)
    assert ordered is blocks
    assert all(block is not child for block in ordered)
    assert ordered[0] is parent


@pytest.mark.parametrize(
    "blocks", [None, [], {}, "", (None,), (1,), (Configuration(),)]
)
def test_order_rejects_wrong_tuple_and_item_types(blocks) -> None:
    with pytest.raises(TypeError):
        order_blocks_for_paint(blocks)


@pytest.mark.parametrize("requested", [-7, 0, 12, 10**400, -(10**400)])
def test_set_writes_signed_integer_and_preserves_every_other_leaf(requested) -> None:
    local = _rich_local()
    block = _blocks(4)[0]
    updated = set_stacking_z_index(local, block, requested)
    assert updated is not local
    assert updated.stacking.z_index == requested
    assert type(updated.stacking.z_index) is int
    assert local.stacking.z_index == 4
    assert block.configuration.stacking.z_index == 4
    for field in fields(Configuration):
        if field.name != "stacking":
            assert getattr(updated, field.name) is getattr(local, field.name)
    assert set_stacking_z_index(local, block, requested) == updated


@pytest.mark.parametrize("effective", [0, 4, -8])
@pytest.mark.parametrize("local_stacking", [None, Stacking(), Stacking(z_index=12)])
def test_effective_same_set_is_identity_no_op_without_pinning(
    effective, local_stacking
) -> None:
    local = Configuration(stacking=local_stacking)
    block = _blocks(effective)[0]
    assert set_stacking_z_index(local, block, effective) is local


def test_builtin_zero_set_does_not_materialize_configuration() -> None:
    source = parse_markdown("Body")
    block = _resolve(source, _layout()).items[0].blocks[0]
    local = Configuration()
    assert set_stacking_z_index(local, block, 0) is local


def test_equal_result_reuses_local_even_if_effective_differs() -> None:
    local = _rich_local(z_index=4)
    assert set_stacking_z_index(local, _blocks(0)[0], 4) is local


@pytest.mark.parametrize("local_stacking", [None, Stacking()])
def test_reset_missing_does_not_clean_existing_empty_containers(local_stacking) -> None:
    local = Configuration(stacking=local_stacking, media=ImageMedia())
    assert reset_stacking_z_index(local) is local
    assert local.stacking is local_stacking


@pytest.mark.parametrize("z_index", [-8, 0, 12, 10**400])
def test_reset_compacts_only_touched_stacking_and_preserves_other_leaves(
    z_index,
) -> None:
    local = _rich_local(z_index=z_index)
    updated = reset_stacking_z_index(local)
    assert updated is not local
    assert updated.stacking is None
    assert local.stacking.z_index == z_index
    for field in fields(Configuration):
        if field.name != "stacking":
            assert getattr(updated, field.name) is getattr(local, field.name)


@pytest.mark.parametrize("value", [True, False, 0.0, 5.0, "5", None])
def test_set_rejects_wrong_z_index_type_before_no_op(value) -> None:
    with pytest.raises(TypeError):
        set_stacking_z_index(Configuration(), _blocks(0)[0], value)


@pytest.mark.parametrize("operation", [set_stacking_z_index, reset_stacking_z_index])
@pytest.mark.parametrize("local", [None, {}, Stacking(), 0])
def test_transaction_rejects_wrong_local_type(operation, local) -> None:
    with pytest.raises(TypeError):
        if operation is set_stacking_z_index:
            operation(local, _blocks(0)[0], 0)
        else:
            operation(local)


@pytest.mark.parametrize("block", [None, {}, Configuration(), Stacking()])
def test_set_rejects_wrong_resolved_block_type(block) -> None:
    with pytest.raises(TypeError):
        set_stacking_z_index(Configuration(), block, 0)


def test_stacking_edits_re_resolve_without_materializing_flow_placement() -> None:
    source = parse_markdown("<!-- sj:ref=1 -->\nFirst\n\nSecond")
    local = Configuration(placement=Placement())
    layout = _layout({1: local})
    first, second = _resolve(source, layout).items[0].blocks
    assert first.configuration.placement.mode is ResolvedPlacementMode.FLOW
    updated = set_stacking_z_index(local, first, 5)
    assert updated.placement is local.placement
    assert updated.placement.x is None and updated.placement.y is None
    new_layout = replace(layout, configurations={1: updated})
    new_first, new_second = _resolve(source, new_layout).items[0].blocks
    assert new_first.configuration.placement.mode is ResolvedPlacementMode.FLOW
    assert order_blocks_for_paint((new_first, new_second)) == (new_second, new_first)
    reset_layout = replace(
        new_layout, configurations={1: reset_stacking_z_index(updated)}
    )
    reset_first, reset_second = _resolve(source, reset_layout).items[0].blocks
    assert reset_first.configuration.stacking.z_index == 0
    assert order_blocks_for_paint((reset_first, reset_second)) == (
        reset_first,
        reset_second,
    )
    assert source.presentation.items[0].blocks[0] is first.node
    assert layout.configurations[1] is local
    assert second.configuration.stacking.z_index == 0


def test_operations_do_not_perform_io_or_generate_diagnostics(monkeypatch) -> None:
    blocks = _blocks(5, 0)
    local = _rich_local()

    def forbidden(*args, **kwargs):
        pytest.fail("stacking operation performed I/O or created a Diagnostic")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("pathlib.Path.open", forbidden)
    monkeypatch.setattr(Diagnostic, "__init__", forbidden)
    assert order_blocks_for_paint(blocks) == (blocks[1], blocks[0])
    assert set_stacking_z_index(local, blocks[0], -1).stacking.z_index == -1
    assert reset_stacking_z_index(local).stacking is None
