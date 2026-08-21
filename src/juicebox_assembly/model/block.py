from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from .placement import Placement


@dataclass(frozen=True, slots=True, order=True)
class BlockKey:
    """Stable in-memory block identity."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("BlockKey.value must be positive")


@dataclass(frozen=True, slots=True)
class AssemblyBlock:
    key: BlockKey
    placements: tuple[Placement, ...]

    def __init__(self, key: BlockKey, placements: Iterable[Placement]) -> None:
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "placements", tuple(placements))

    def __iter__(self) -> Iterator[Placement]:
        return iter(self.placements)

    def __len__(self) -> int:
        return len(self.placements)
