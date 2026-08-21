from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from ..model import AssemblyDocument, ComponentKey, Orientation
from .report import AssemblyMetrics, Severity, ValidationIssue, ValidationReport

_JAVA_INT_MAX = 2_147_483_647
_FRAGMENT_NAME = re.compile(r"^.+:::fragment_([1-9][0-9]*)(?::::debris)?$")


def validate(
    document: AssemblyDocument,
    *,
    require_unique_placement: bool = True,
    source_compatibility: bool = True,
) -> ValidationReport:
    """Validate a document and calculate assembly metrics."""

    issues: list[ValidationIssue] = []
    component_keys = [component.key for component in document.components]
    key_counts = Counter(component_keys)
    name_counts = Counter(component.name for component in document.components)
    component_map = {component.key: component for component in document.components}

    if not document.components:
        issues.append(_error("E_NO_COMPONENTS", "Document contains no components"))
    if not document.blocks:
        issues.append(_error("E_NO_BLOCKS", "Document contains no assembly blocks"))

    for key, count in key_counts.items():
        if count > 1:
            issues.append(
                _error(
                    "E_DUPLICATE_COMPONENT_KEY",
                    f"Component key {key.value} occurs {count} times",
                    component_key=key.value,
                    occurrences=count,
                )
            )

    for name, count in name_counts.items():
        if count > 1:
            issues.append(
                _error(
                    "E_DUPLICATE_NAME",
                    f"Component name {name!r} occurs {count} times",
                    component_name=name,
                    occurrences=count,
                )
            )

    for component in document.components:
        if (
            not component.name
            or component.name.startswith(">")
            or any(character.isspace() for character in component.name)
        ):
            issues.append(
                _error(
                    "E_INVALID_NAME",
                    f"Invalid component name {component.name!r}",
                    component_key=component.key.value,
                )
            )
        if component.length <= 0:
            issues.append(
                _error(
                    "E_INVALID_LENGTH",
                    f"Component {component.name!r} has non-positive length",
                    component_key=component.key.value,
                    length=component.length,
                )
            )
        elif component.length > _JAVA_INT_MAX:
            issues.append(
                _error(
                    "E_LENGTH_INT32_OVERFLOW",
                    f"Component {component.name!r} exceeds Juicebox importer integer range",
                    component_key=component.key.value,
                    length=component.length,
                )
            )

        if component.is_fragment and _FRAGMENT_NAME.fullmatch(component.name) is None:
            issues.append(
                _error(
                    "E_INVALID_FRAGMENT_NAME",
                    f"Fragment name {component.name!r} does not end in a positive number",
                    component_key=component.key.value,
                )
            )

    source_ids = [component.source_serial_id for component in document.components]
    present_source_ids = [value for value in source_ids if value is not None]
    if source_compatibility and present_source_ids:
        expected = list(range(1, len(document.components) + 1))
        if len(present_source_ids) != len(source_ids):
            issues.append(
                _error(
                    "E_PARTIAL_SOURCE_IDS",
                    "Only some components have source serial IDs",
                )
            )
        elif present_source_ids != expected:
            issues.append(
                _error(
                    "E_ID_NOT_CONTIGUOUS",
                    "Source IDs must match header order and be contiguous from 1 to N",
                    expected_count=len(expected),
                )
            )

    block_key_counts = Counter(block.key for block in document.blocks)
    placement_counts: Counter[ComponentKey] = Counter()
    forward = 0
    reverse = 0
    block_sizes: list[int] = []

    for block in document.blocks:
        if block_key_counts[block.key] > 1:
            issues.append(
                _error(
                    "E_DUPLICATE_BLOCK_KEY",
                    f"Block key {block.key.value} is not unique",
                    block_key=block.key.value,
                )
            )
        if not block.placements:
            issues.append(
                _error(
                    "E_EMPTY_BLOCK",
                    f"Block {block.key.value} contains no placements",
                    block_key=block.key.value,
                )
            )

        block_size = 0
        for placement in block.placements:
            placement_counts[placement.component] += 1
            component = component_map.get(placement.component)
            if component is None:
                issues.append(
                    _error(
                        "E_UNDEFINED_REFERENCE",
                        f"Block {block.key.value} references an undefined component",
                        block_key=block.key.value,
                        component_key=placement.component.value,
                    )
                )
            else:
                block_size += component.length

            if placement.orientation is Orientation.FORWARD:
                forward += 1
            elif placement.orientation is Orientation.REVERSE:
                reverse += 1
            else:
                issues.append(
                    _error(
                        "E_INVALID_ORIENTATION",
                        f"Block {block.key.value} has an invalid orientation",
                        block_key=block.key.value,
                    )
                )
        block_sizes.append(block_size)

    if require_unique_placement:
        for component in document.components:
            count = placement_counts[component.key]
            if count == 0:
                issues.append(
                    _error(
                        "E_MISSING_PLACEMENT",
                        f"Component {component.name!r} is absent from all blocks",
                        component_key=component.key.value,
                    )
                )
            elif count > 1:
                issues.append(
                    _error(
                        "E_DUPLICATE_PLACEMENT",
                        f"Component {component.name!r} occurs {count} times",
                        component_key=component.key.value,
                        occurrences=count,
                    )
                )

    total_bp = sum(component.length for component in document.components)
    n50, l50 = _n50_l50(block_sizes, total_bp)
    metrics = AssemblyMetrics(
        components=len(document.components),
        blocks=len(document.blocks),
        multi_component_blocks=sum(1 for block in document.blocks if len(block) > 1),
        component_uses=sum(placement_counts.values()),
        forward_components=forward,
        reverse_components=reverse,
        fragment_records=sum(component.is_fragment for component in document.components),
        debris_records=sum(component.is_debris for component in document.components),
        total_bp=total_bp,
        scaffold_n50_bp=n50,
        scaffold_l50=l50,
    )
    return ValidationReport(tuple(_deduplicate(issues)), metrics)


def _error(code: str, message: str, **context: Any) -> ValidationIssue:
    return ValidationIssue.create(code, message, Severity.ERROR, **context)


def _n50_l50(block_sizes: Iterable[int], total_bp: int) -> tuple[int, int]:
    cumulative = 0
    for rank, size in enumerate(sorted(block_sizes, reverse=True), start=1):
        cumulative += size
        if cumulative * 2 >= total_bp:
            return size, rank
    return 0, 0


def _deduplicate(issues: Iterable[ValidationIssue]) -> list[ValidationIssue]:
    result: list[ValidationIssue] = []
    seen: set[tuple[str, str, tuple[tuple[str, Any], ...]]] = set()
    for issue in issues:
        identity = (issue.code, issue.message, issue.context)
        if identity not in seen:
            seen.add(identity)
            result.append(issue)
    return result
