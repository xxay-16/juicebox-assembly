from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from ..model import BlockKey, ComponentKey
from ..operations import MoveOrder


@dataclass(frozen=True, slots=True)
class MoveComponentsChange:
    """Audit record for a component move."""

    component_keys: tuple[ComponentKey, ...]
    source_block_keys: tuple[BlockKey, ...]
    target_block_key: BlockKey
    order: MoveOrder


@dataclass(frozen=True, slots=True)
class ChangeSet:
    changes: tuple[MoveComponentsChange, ...] = ()

    def __iter__(self) -> Iterator[MoveComponentsChange]:
        return iter(self.changes)

    def __len__(self) -> int:
        return len(self.changes)
