from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..exceptions import AssemblyValidationError


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: Severity
    context: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def create(
        cls,
        code: str,
        message: str,
        severity: Severity,
        **context: Any,
    ) -> ValidationIssue:
        return cls(code, message, severity, tuple(sorted(context.items())))


@dataclass(frozen=True, slots=True)
class AssemblyMetrics:
    components: int
    blocks: int
    multi_component_blocks: int
    component_uses: int
    forward_components: int
    reverse_components: int
    fragment_records: int
    debris_records: int
    total_bp: int
    scaffold_n50_bp: int
    scaffold_l50: int


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]
    metrics: AssemblyMetrics

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is Severity.WARNING)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            raise AssemblyValidationError(self)
