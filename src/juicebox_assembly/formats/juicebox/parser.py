from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ...exceptions import AssemblyParseError
from ...model import (
    AssemblyBlock,
    AssemblyDocument,
    BlockKey,
    Component,
    ComponentKey,
    DocumentMetadata,
    Orientation,
    Placement,
)

_CANONICAL_HEADER = re.compile(r"^>(\S+) ([1-9][0-9]*) ([1-9][0-9]*)$")
_CANONICAL_BODY = re.compile(r"^-?[1-9][0-9]*(?: -?[1-9][0-9]*)*$")


def load(path: str | Path, *, strict: bool = True) -> AssemblyDocument:
    """Load a Juicebox assembly file from disk."""

    source = Path(path)
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise AssemblyParseError(
            f"Could not read assembly file: {exc}",
            source=source,
            code="E_READ",
        ) from exc

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssemblyParseError(
            "Assembly file must be UTF-8 text",
            source=source,
            code="E_ENCODING",
        ) from exc

    return loads(
        text,
        strict=strict,
        source=source,
        source_sha256=hashlib.sha256(payload).hexdigest(),
    )


def loads(
    text: str,
    *,
    strict: bool = True,
    source: str | Path | None = None,
    source_sha256: str | None = None,
) -> AssemblyDocument:
    """Parse Juicebox assembly text into immutable domain objects."""

    if not text:
        raise AssemblyParseError("Assembly text is empty", source=source, code="E_EMPTY")

    header_rows: list[tuple[str, int, int, int]] = []
    body_rows: list[tuple[list[int], int]] = []
    serial_ids: set[int] = set()
    names: set[str] = set()
    body_started = False

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if raw_line == "":
            if strict:
                raise AssemblyParseError(
                    "Blank lines are not allowed in canonical assembly files",
                    line=line_number,
                    source=source,
                    code="E_BLANK_LINE",
                )
            continue

        if raw_line.startswith(">"):
            if body_started:
                raise AssemblyParseError(
                    "Header records must precede all body blocks",
                    line=line_number,
                    source=source,
                    code="E_HEADER_AFTER_BODY",
                )
            name, serial_id, length = _parse_header(
                raw_line,
                strict=strict,
                line_number=line_number,
                source=source,
            )
            if name in names:
                raise AssemblyParseError(
                    f"Duplicate component name {name!r}",
                    line=line_number,
                    source=source,
                    code="E_DUPLICATE_NAME",
                )
            if serial_id in serial_ids:
                raise AssemblyParseError(
                    f"Duplicate component ID {serial_id}",
                    line=line_number,
                    source=source,
                    code="E_DUPLICATE_ID",
                )
            expected = len(header_rows) + 1
            if strict and serial_id != expected:
                raise AssemblyParseError(
                    f"Expected component ID {expected}, found {serial_id}",
                    line=line_number,
                    source=source,
                    code="E_ID_NOT_CONTIGUOUS",
                )
            names.add(name)
            serial_ids.add(serial_id)
            header_rows.append((name, serial_id, length, line_number))
            continue

        body_started = True
        body_rows.append(
            (
                _parse_body(
                    raw_line,
                    strict=strict,
                    line_number=line_number,
                    source=source,
                ),
                line_number,
            )
        )

    if not header_rows:
        raise AssemblyParseError(
            "No component header records were found",
            source=source,
            code="E_NO_HEADERS",
        )
    if not body_rows:
        raise AssemblyParseError(
            "No assembly body blocks were found",
            source=source,
            code="E_NO_BLOCKS",
        )

    serial_to_key: dict[int, ComponentKey] = {}
    components: list[Component] = []
    for ordinal, (name, serial_id, length, _line) in enumerate(header_rows, start=1):
        key = ComponentKey(ordinal)
        serial_to_key[serial_id] = key
        components.append(Component(key, name, length, serial_id))

    blocks: list[AssemblyBlock] = []
    for ordinal, (signed_ids, line_number) in enumerate(body_rows, start=1):
        placements: list[Placement] = []
        for signed_id in signed_ids:
            serial_id = abs(signed_id)
            try:
                key = serial_to_key[serial_id]
            except KeyError as exc:
                raise AssemblyParseError(
                    f"Body references undefined component ID {serial_id}",
                    line=line_number,
                    source=source,
                    code="E_UNDEFINED_REFERENCE",
                    context={"component_id": serial_id},
                ) from exc
            placements.append(Placement(key, Orientation.from_signed_id(signed_id)))
        blocks.append(AssemblyBlock(BlockKey(ordinal), placements))

    metadata = DocumentMetadata(
        source=None if source is None else str(source),
        source_sha256=source_sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest(),
        parsed_strictly=strict,
    )
    return AssemblyDocument(components, blocks, metadata)


def _parse_header(
    line: str,
    *,
    strict: bool,
    line_number: int,
    source: str | Path | None,
) -> tuple[str, int, int]:
    if strict:
        match = _CANONICAL_HEADER.fullmatch(line)
        if match is None:
            raise AssemblyParseError(
                "Expected canonical header '>name ID length' with single spaces",
                line=line_number,
                source=source,
                code="E_PARSE_HEADER",
            )
        name, id_text, length_text = match.groups()
    else:
        fields = line[1:].split()
        if len(fields) != 3:
            raise AssemblyParseError(
                "Expected header '>name ID length'",
                line=line_number,
                source=source,
                code="E_PARSE_HEADER",
            )
        name, id_text, length_text = fields

    try:
        serial_id = int(id_text)
        length = int(length_text)
    except ValueError as exc:
        raise AssemblyParseError(
            "Component ID and length must be integers",
            line=line_number,
            source=source,
            code="E_PARSE_HEADER",
        ) from exc

    if not name or any(character.isspace() for character in name):
        raise AssemblyParseError(
            "Component names must be non-empty and contain no whitespace",
            line=line_number,
            source=source,
            code="E_INVALID_NAME",
        )
    if serial_id <= 0:
        raise AssemblyParseError(
            "Component ID must be positive",
            line=line_number,
            source=source,
            code="E_INVALID_ID",
        )
    if length <= 0:
        raise AssemblyParseError(
            "Component length must be positive",
            line=line_number,
            source=source,
            code="E_INVALID_LENGTH",
        )
    return name, serial_id, length


def _parse_body(
    line: str,
    *,
    strict: bool,
    line_number: int,
    source: str | Path | None,
) -> list[int]:
    if strict and _CANONICAL_BODY.fullmatch(line) is None:
        raise AssemblyParseError(
            "Expected signed component IDs separated by single spaces",
            line=line_number,
            source=source,
            code="E_PARSE_BODY",
        )

    fields = line.split() if not strict else line.split(" ")
    signed_ids: list[int] = []
    for field in fields:
        try:
            signed_id = int(field)
        except ValueError as exc:
            raise AssemblyParseError(
                f"Invalid body token {field!r}",
                line=line_number,
                source=source,
                code="E_PARSE_BODY",
            ) from exc
        if signed_id == 0:
            raise AssemblyParseError(
                "Body component ID cannot be zero",
                line=line_number,
                source=source,
                code="E_INVALID_ID",
            )
        signed_ids.append(signed_id)
    return signed_ids
