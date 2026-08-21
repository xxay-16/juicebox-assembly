from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from .validation import ValidationReport


class AssemblyError(Exception):
    """Base exception for the package."""

    code = "E_ASSEMBLY"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code or self.code
        self.context = dict(context or {})


class AssemblyParseError(AssemblyError):
    """Raised when text cannot be represented as an assembly document."""

    code = "E_PARSE"

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        source: str | Path | None = None,
        code: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        details = dict(context or {})
        if line is not None:
            details["line"] = line
        if source is not None:
            details["source"] = str(source)

        location = ""
        if source is not None:
            location = str(source)
        if line is not None:
            location = f"{location}:{line}" if location else f"line {line}"
        rendered = f"{location}: {message}" if location else message
        super().__init__(rendered, code=code, context=details)
        self.line = line
        self.source = None if source is None else str(source)


class AssemblyValidationError(AssemblyError):
    """Raised when an invalid document is passed to a strict operation."""

    code = "E_VALIDATION"

    def __init__(self, report: ValidationReport) -> None:
        errors = "; ".join(f"{issue.code}: {issue.message}" for issue in report.errors)
        super().__init__(
            f"Assembly validation failed: {errors}",
            context={"error_count": len(report.errors)},
        )
        self.report = report


class AssemblyWriteError(AssemblyError):
    """Raised when canonical serialization or file output fails."""

    code = "E_WRITE"


class ComponentNotFound(AssemblyError):
    """Raised when a component key or name cannot be resolved."""

    code = "E_COMPONENT_NOT_FOUND"
