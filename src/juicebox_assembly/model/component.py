from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class ComponentKey:
    """Stable in-memory component identity, distinct from serialized file IDs."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("ComponentKey.value must be positive")


@dataclass(frozen=True, slots=True)
class Component:
    key: ComponentKey
    name: str
    length: int
    source_serial_id: int | None = None

    @property
    def is_fragment(self) -> bool:
        return ":::fragment_" in self.name

    @property
    def is_debris(self) -> bool:
        return ":::debris" in self.name

    @property
    def original_name(self) -> str:
        return self.name.split(":::fragment_", 1)[0]
