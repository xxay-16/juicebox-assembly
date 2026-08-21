from __future__ import annotations

from ...model import AssemblyDocument, ComponentKey


def allocate_serial_ids(document: AssemblyDocument) -> dict[ComponentKey, int]:
    """Assign canonical Juicebox IDs from component header order."""

    return {
        component.key: serial_id
        for serial_id, component in enumerate(document.components, start=1)
    }
