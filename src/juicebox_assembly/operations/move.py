from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from ..exceptions import AssemblyEditError
from ..model import (
    AssemblyBlock,
    AssemblyDocument,
    BlockKey,
    ComponentKey,
    Placement,
)
from ..validation import validate
from .selectors import Ref, Target, TargetKind


class MoveOrder(Enum):
    INPUT = "input"
    ASSEMBLY = "assembly"

    @classmethod
    def coerce(cls, value: MoveOrder | str) -> MoveOrder:
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except (TypeError, ValueError) as exc:
            raise AssemblyEditError(
                f"Unsupported move order {value!r}; expected 'input' or 'assembly'",
                code="E_INVALID_MOVE_ORDER",
                context={"order": value},
            ) from exc


@dataclass(frozen=True, slots=True)
class MoveOutcome:
    document: AssemblyDocument
    component_keys: tuple[ComponentKey, ...]
    source_block_keys: tuple[BlockKey, ...]
    target_block_key: BlockKey
    order: MoveOrder


def move_components(
    document: AssemblyDocument,
    refs: Iterable[Ref],
    *,
    target: Target,
    order: MoveOrder | str = MoveOrder.INPUT,
) -> MoveOutcome:
    """Move selected components into a new final block without changing orientation."""

    validate(document, source_compatibility=False).raise_for_errors()

    selected_refs = tuple(refs)
    if not selected_refs:
        raise AssemblyEditError(
            "At least one component selector is required",
            code="E_EMPTY_SELECTION",
        )
    if any(not isinstance(ref, Ref) for ref in selected_refs):
        raise AssemblyEditError(
            "Component selections must use explicit Ref selectors",
            code="E_INVALID_SELECTOR",
        )
    if not isinstance(target, Target) or target.kind is not TargetKind.LAST_NEW_BLOCK:
        raise AssemblyEditError(
            "The current release only supports Target.last_new_block()",
            code="E_UNSUPPORTED_TARGET",
        )

    move_order = MoveOrder.coerce(order)
    input_keys = tuple(ref.resolve(document).key for ref in selected_refs)
    if len(set(input_keys)) != len(input_keys):
        raise AssemblyEditError(
            "The component selection contains duplicates",
            code="E_DUPLICATE_SELECTION",
            context={"selection_count": len(input_keys)},
        )

    selected = set(input_keys)
    placement_by_key: dict[ComponentKey, Placement] = {}
    assembly_keys: list[ComponentKey] = []
    source_block_keys: list[BlockKey] = []

    for block in document.blocks:
        block_selected = False
        for placement in block.placements:
            if placement.component in selected:
                placement_by_key[placement.component] = placement
                assembly_keys.append(placement.component)
                block_selected = True
        if block_selected:
            source_block_keys.append(block.key)

    missing = [key.value for key in input_keys if key not in placement_by_key]
    if missing:
        raise AssemblyEditError(
            "Selected components are not placed in the assembly body",
            code="E_SELECTION_NOT_PLACED",
            context={"component_keys": tuple(missing)},
        )

    ordered_keys = input_keys if move_order is MoveOrder.INPUT else tuple(assembly_keys)
    target_placements = tuple(placement_by_key[key] for key in ordered_keys)

    next_key_value = max(block.key.value for block in document.blocks) + 1
    rebuilt_blocks: list[AssemblyBlock] = []

    for block in document.blocks:
        if not any(placement.component in selected for placement in block.placements):
            rebuilt_blocks.append(block)
            continue

        runs = _surviving_runs(block, selected)
        for run_index, run in enumerate(runs):
            if run_index == 0:
                block_key = block.key
            else:
                block_key = BlockKey(next_key_value)
                next_key_value += 1
            rebuilt_blocks.append(AssemblyBlock(block_key, run))

    target_block_key = BlockKey(next_key_value)
    rebuilt_blocks.append(AssemblyBlock(target_block_key, target_placements))

    result = AssemblyDocument(
        document.components,
        rebuilt_blocks,
        document.metadata,
    )
    validate(result, source_compatibility=False).raise_for_errors()
    return MoveOutcome(
        result,
        ordered_keys,
        tuple(source_block_keys),
        target_block_key,
        move_order,
    )


def _surviving_runs(
    block: AssemblyBlock,
    selected: set[ComponentKey],
) -> tuple[tuple[Placement, ...], ...]:
    runs: list[tuple[Placement, ...]] = []
    current: list[Placement] = []

    for placement in block.placements:
        if placement.component in selected:
            if current:
                runs.append(tuple(current))
                current = []
        else:
            current.append(placement)

    if current:
        runs.append(tuple(current))
    return tuple(runs)
