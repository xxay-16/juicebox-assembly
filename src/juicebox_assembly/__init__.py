"""Typed Python SDK for Juicebox/3D-DNA assembly files."""

from .exceptions import (
    AssemblyError,
    AssemblyParseError,
    AssemblyValidationError,
    AssemblyWriteError,
    ComponentNotFound,
)
from .formats.juicebox import dump, dumps, load, loads
from .model import (
    AssemblyBlock,
    AssemblyDocument,
    BlockKey,
    Component,
    ComponentKey,
    DocumentMetadata,
    Orientation,
    Placement,
)
from .sdk import AssemblyFile
from .validation import (
    AssemblyMetrics,
    Severity,
    ValidationIssue,
    ValidationReport,
    validate,
)

__all__ = [
    "AssemblyBlock",
    "AssemblyDocument",
    "AssemblyError",
    "AssemblyFile",
    "AssemblyMetrics",
    "AssemblyParseError",
    "AssemblyValidationError",
    "AssemblyWriteError",
    "BlockKey",
    "Component",
    "ComponentKey",
    "ComponentNotFound",
    "DocumentMetadata",
    "Orientation",
    "Placement",
    "Severity",
    "ValidationIssue",
    "ValidationReport",
    "dump",
    "dumps",
    "load",
    "loads",
    "validate",
]

__version__ = "0.1.0"
