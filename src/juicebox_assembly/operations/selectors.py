from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..model import AssemblyDocument, Component, ComponentKey


class RefKind(Enum):
    NAME = "name"
    SERIAL_ID = "serial_id"
    KEY = "key"


@dataclass(frozen=True, slots=True)
class Ref:
    """An explicit, unambiguous component selector."""

    kind: RefKind
    value: str | int | ComponentKey

    def __post_init__(self) -> None:
        if self.kind is RefKind.NAME:
            if not isinstance(self.value, str) or not self.value:
                raise ValueError("A component name selector must be a non-empty string")
            return
        if self.kind is RefKind.SERIAL_ID:
            if (
                not isinstance(self.value, int)
                or isinstance(self.value, bool)
                or self.value <= 0
            ):
                raise ValueError("A serial ID selector must be a positive integer")
            return
        if self.kind is RefKind.KEY:
            if isinstance(self.value, ComponentKey):
                return
            if (
                not isinstance(self.value, int)
                or isinstance(self.value, bool)
                or self.value <= 0
            ):
                raise ValueError("A component key selector must be a positive integer")
            return
        raise ValueError(f"Unsupported component selector kind: {self.kind!r}")

    @classmethod
    def name(cls, value: str) -> Ref:
        return cls(RefKind.NAME, value)

    @classmethod
    def serial_id(cls, value: int) -> Ref:
        return cls(RefKind.SERIAL_ID, value)

    @classmethod
    def key(cls, value: ComponentKey | int) -> Ref:
        return cls(RefKind.KEY, value)

    def resolve(self, document: AssemblyDocument) -> Component:
        if self.kind is RefKind.NAME:
            assert isinstance(self.value, str)
            return document.component_by_name(self.value)
        if self.kind is RefKind.SERIAL_ID:
            assert isinstance(self.value, int)
            return document.component_by_source_id(self.value)

        key = self.value
        if isinstance(key, int):
            key = ComponentKey(key)
        assert isinstance(key, ComponentKey)
        return document.component_by_key(key)


class TargetKind(Enum):
    LAST_NEW_BLOCK = "last_new_block"


@dataclass(frozen=True, slots=True)
class Target:
    """Destination for a structural edit."""

    kind: TargetKind

    @classmethod
    def last_new_block(cls) -> Target:
        return cls(TargetKind.LAST_NEW_BLOCK)
