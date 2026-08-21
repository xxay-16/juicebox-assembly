from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from ...exceptions import AssemblyValidationError, AssemblyWriteError
from ...model import AssemblyDocument
from ...validation import validate
from .id_allocator import allocate_serial_ids


def dumps(document: AssemblyDocument, *, validate_document: bool = True) -> str:
    """Serialize a document using canonical Juicebox-compatible formatting."""

    if validate_document:
        report = validate(document, source_compatibility=False)
        if not report.is_valid:
            raise AssemblyValidationError(report)

    serial_ids = allocate_serial_ids(document)
    lines: list[str] = []

    for serial_id, component in enumerate(document.components, start=1):
        lines.append(f">{component.name} {serial_id} {component.length}")

    for block in document.blocks:
        signed_ids: list[str] = []
        for placement in block.placements:
            try:
                serial_id = serial_ids[placement.component]
            except KeyError as exc:
                raise AssemblyWriteError(
                    f"Block {block.key.value} references an undefined component",
                    code="E_UNDEFINED_REFERENCE",
                    context={
                        "block_key": block.key.value,
                        "component_key": placement.component.value,
                    },
                ) from exc
            signed_ids.append(str(placement.orientation.sign * serial_id))
        lines.append(" ".join(signed_ids))

    return "\n".join(lines) + "\n"


def dump(
    document: AssemblyDocument,
    path: str | Path,
    *,
    overwrite: bool = False,
    atomic: bool = True,
    validate_document: bool = True,
) -> Path:
    """Write a canonical assembly file, atomically by default."""

    destination = Path(path)
    if not destination.parent.is_dir():
        raise AssemblyWriteError(
            f"Output directory does not exist: {destination.parent}",
            code="E_OUTPUT_DIRECTORY",
        )
    if destination.exists() and not overwrite:
        raise AssemblyWriteError(
            f"Output already exists: {destination}",
            code="E_OUTPUT_EXISTS",
        )
    if destination.is_symlink():
        raise AssemblyWriteError(
            f"Refusing to replace symbolic link: {destination}",
            code="E_OUTPUT_SYMLINK",
        )

    text = dumps(document, validate_document=validate_document)
    if not atomic:
        try:
            destination.write_text(text, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise AssemblyWriteError(f"Could not write {destination}: {exc}") from exc
        return destination

    file_descriptor = -1
    temporary: Path | None = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=str(destination.parent),
        )
        temporary = Path(temporary_name)
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            file_descriptor = -1
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        if destination.exists():
            mode = stat.S_IMODE(destination.stat().st_mode)
            os.chmod(temporary, mode)
        os.replace(temporary, destination)
    except OSError as exc:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        raise AssemblyWriteError(f"Could not write {destination}: {exc}") from exc

    return destination
