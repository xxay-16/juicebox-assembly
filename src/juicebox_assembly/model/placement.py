from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .component import ComponentKey


class Orientation(Enum):
    FORWARD = 1
    REVERSE = -1

    @property
    def sign(self) -> int:
        return int(self.value)

    def flipped(self) -> Orientation:
        return Orientation.REVERSE if self is Orientation.FORWARD else Orientation.FORWARD

    @classmethod
    def from_signed_id(cls, signed_id: int) -> Orientation:
        if signed_id == 0:
            raise ValueError("A placement ID cannot be zero")
        return cls.FORWARD if signed_id > 0 else cls.REVERSE


@dataclass(frozen=True, slots=True)
class Placement:
    component: ComponentKey
    orientation: Orientation = Orientation.FORWARD
