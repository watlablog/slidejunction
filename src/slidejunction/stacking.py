"""Pure direct-sibling paint ordering and local stacking transactions."""

from dataclasses import replace

from .layout import Configuration, Stacking
from .resolver import ResolvedBlock


def order_blocks_for_paint(
    blocks: tuple[ResolvedBlock, ...],
) -> tuple[ResolvedBlock, ...]:
    """Order direct siblings back-to-front, using input order to break ties."""
    if not isinstance(blocks, tuple) or not all(
        isinstance(block, ResolvedBlock) for block in blocks
    ):
        raise TypeError("blocks must be a tuple of ResolvedBlock objects")
    ordered = tuple(sorted(blocks, key=_effective_z_index))
    return blocks if all(a is b for a, b in zip(blocks, ordered)) else ordered


def set_stacking_z_index(
    local_configuration: Configuration,
    resolved_block: ResolvedBlock,
    z_index: int,
) -> Configuration:
    """Set a local override only when it differs from the effective z-index."""
    _require_configuration(local_configuration)
    if not isinstance(resolved_block, ResolvedBlock):
        raise TypeError("resolved_block must be a ResolvedBlock")
    if not isinstance(z_index, int) or isinstance(z_index, bool):
        raise TypeError("z_index must be an integer")
    if z_index == _effective_z_index(resolved_block):
        return local_configuration
    stacking = replace(local_configuration.stacking or Stacking(), z_index=z_index)
    result = replace(local_configuration, stacking=stacking)
    return local_configuration if result == local_configuration else result


def reset_stacking_z_index(
    local_configuration: Configuration,
) -> Configuration:
    """Remove the local z-index override, preserving unrelated properties."""
    _require_configuration(local_configuration)
    stacking = local_configuration.stacking
    if stacking is None or stacking.z_index is None:
        return local_configuration
    updated_stacking = replace(stacking, z_index=None)
    return replace(
        local_configuration,
        stacking=None if updated_stacking == Stacking() else updated_stacking,
    )


def _effective_z_index(block: ResolvedBlock) -> int:
    stacking = block.configuration.stacking
    # ResolvedBlock construction already requires a complete stacking value.
    assert stacking is not None and stacking.z_index is not None
    return stacking.z_index


def _require_configuration(configuration: Configuration) -> None:
    if not isinstance(configuration, Configuration):
        raise TypeError("local_configuration must be a Configuration")


__all__ = [
    "order_blocks_for_paint",
    "reset_stacking_z_index",
    "set_stacking_z_index",
]
