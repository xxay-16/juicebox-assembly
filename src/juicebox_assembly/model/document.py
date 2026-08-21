from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..exceptions import ComponentNotFound
from .block import AssemblyBlock
from .component import Component, ComponentKey


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    source: str | None = None
    source_sha256: str | None = None
    parsed_strictly: bool = True


@dataclass(frozen=True, slots=True)
class AssemblyDocument:
    components: tuple[Component, ...]
    blocks: tuple[AssemblyBlock, ...]
    metadata: DocumentMetadata = DocumentMetadata()

    def __init__(
        self,
        components: Iterable[Component],
        blocks: Iterable[AssemblyBlock],
        metadata: DocumentMetadata | None = None,
    ) -> None:
        object.__setattr__(self, "components", tuple(components))
        object.__setattr__(self, "blocks", tuple(blocks))
        object.__setattr__(self, "metadata", metadata or DocumentMetadata())

    @property
    def total_length(self) -> int:
        return sum(component.length for component in self.components)

    @property
    def placement_count(self) -> int:
        return sum(len(block) for block in self.blocks)

    @property
    def source_path(self) -> Path | None:
        return None if self.metadata.source is None else Path(self.metadata.source)

    def component_by_key(self, key: ComponentKey) -> Component:
        for component in self.components:
            if component.key == key:
                return component
        raise ComponentNotFound(
            f"Component key {key.value} was not found",
            context={"component_key": key.value},
        )

    def component_by_name(self, name: str) -> Component:
        matches = [component for component in self.components if component.name == name]
        if not matches:
            raise ComponentNotFound(
                f"Component name {name!r} was not found",
                context={"component_name": name},
            )
        if len(matches) > 1:
            raise ComponentNotFound(
                f"Component name {name!r} is ambiguous",
                code="E_COMPONENT_AMBIGUOUS",
                context={"component_name": name, "matches": len(matches)},
            )
        return matches[0]

    def component_by_source_id(self, source_serial_id: int) -> Component:
        matches = [
            component
            for component in self.components
            if component.source_serial_id == source_serial_id
        ]
        if not matches:
            raise ComponentNotFound(
                f"Source serial ID {source_serial_id} was not found",
                context={"source_serial_id": source_serial_id},
            )
        if len(matches) > 1:
            raise ComponentNotFound(
                f"Source serial ID {source_serial_id} is ambiguous",
                code="E_COMPONENT_AMBIGUOUS",
                context={"source_serial_id": source_serial_id, "matches": len(matches)},
            )
        return matches[0]
