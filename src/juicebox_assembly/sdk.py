from __future__ import annotations

from pathlib import Path

from .formats.juicebox import dump, dumps, load, loads
from .history import AssemblyEditor
from .model import AssemblyDocument
from .validation import ValidationReport, validate


class AssemblyFile:
    """Stable facade for the foundational Python SDK."""

    @staticmethod
    def edit(document: AssemblyDocument) -> AssemblyEditor:
        return AssemblyEditor(document)

    @staticmethod
    def load(path: str | Path, *, strict: bool = True) -> AssemblyDocument:
        return load(path, strict=strict)

    @staticmethod
    def loads(text: str, *, strict: bool = True) -> AssemblyDocument:
        return loads(text, strict=strict)

    @staticmethod
    def validate(
        document: AssemblyDocument,
        *,
        require_unique_placement: bool = True,
        source_compatibility: bool = True,
    ) -> ValidationReport:
        return validate(
            document,
            require_unique_placement=require_unique_placement,
            source_compatibility=source_compatibility,
        )

    @staticmethod
    def dump(
        document: AssemblyDocument,
        path: str | Path,
        *,
        overwrite: bool = False,
        atomic: bool = True,
        validate_document: bool = True,
    ) -> Path:
        return dump(
            document,
            path,
            overwrite=overwrite,
            atomic=atomic,
            validate_document=validate_document,
        )

    @staticmethod
    def dumps(
        document: AssemblyDocument,
        *,
        validate_document: bool = True,
    ) -> str:
        return dumps(document, validate_document=validate_document)
