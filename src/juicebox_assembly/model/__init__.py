"""Immutable domain model for assembly documents."""

from .block import AssemblyBlock, BlockKey
from .component import Component, ComponentKey
from .document import AssemblyDocument, DocumentMetadata
from .placement import Orientation, Placement

__all__ = [
    "AssemblyBlock",
    "AssemblyDocument",
    "BlockKey",
    "Component",
    "ComponentKey",
    "DocumentMetadata",
    "Orientation",
    "Placement",
]
