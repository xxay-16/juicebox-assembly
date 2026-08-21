from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from ..exceptions import AssemblyEditError
from ..model import AssemblyDocument
from ..operations import MoveOrder, Ref, Target, move_components
from ..validation import ValidationReport, validate
from .changeset import ChangeSet, MoveComponentsChange


@dataclass(frozen=True, slots=True)
class EditResult:
    document: AssemblyDocument
    changeset: ChangeSet
    validation: ValidationReport
    id_map: Mapping[int, int]


class AssemblyEditor:
    """Transaction-style editor for immutable assembly documents."""

    def __init__(self, document: AssemblyDocument) -> None:
        validate(document, source_compatibility=False).raise_for_errors()
        self._original = document
        self._working = document
        self._changes: list[MoveComponentsChange] = []
        self._closed = False

    @property
    def original(self) -> AssemblyDocument:
        return self._original

    @property
    def document(self) -> AssemblyDocument:
        return self._working

    def move_components(
        self,
        refs: Iterable[Ref],
        *,
        target: Target,
        order: MoveOrder | str = MoveOrder.INPUT,
    ) -> AssemblyEditor:
        self._ensure_open()
        outcome = move_components(
            self._working,
            refs,
            target=target,
            order=order,
        )
        change = MoveComponentsChange(
            outcome.component_keys,
            outcome.source_block_keys,
            outcome.target_block_key,
            outcome.order,
        )
        self._working = outcome.document
        self._changes.append(change)
        return self

    def commit(self) -> EditResult:
        self._ensure_open()
        report = validate(self._working, source_compatibility=False)
        report.raise_for_errors()
        id_map = _build_id_map(self._working)
        result = EditResult(
            self._working,
            ChangeSet(tuple(self._changes)),
            report,
            MappingProxyType(id_map),
        )
        self._closed = True
        return result

    def _ensure_open(self) -> None:
        if self._closed:
            raise AssemblyEditError(
                "This editor has already been committed",
                code="E_EDITOR_CLOSED",
            )


def _build_id_map(document: AssemblyDocument) -> dict[int, int]:
    result: dict[int, int] = {}
    for new_serial_id, component in enumerate(document.components, start=1):
        old_serial_id = component.source_serial_id
        if old_serial_id is None:
            continue
        if old_serial_id in result:
            raise AssemblyEditError(
                f"Source serial ID {old_serial_id} is ambiguous",
                code="E_DUPLICATE_SOURCE_ID",
                context={"source_serial_id": old_serial_id},
            )
        result[old_serial_id] = new_serial_id
    return result
