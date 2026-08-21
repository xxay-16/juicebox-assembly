# juicebox-assembly

[简体中文](README.zh-CN.md) | English

A typed Python SDK for Juicebox/3D-DNA .assembly files.

This repository currently contains the foundational v0.1 core:

- immutable domain objects;
- strict and diagnostic parsers;
- structural and Juicebox compatibility validation;
- canonical UTF-8 serialization;
- atomic file writes;
- assembly statistics;
- transactional component moves into a new final block.

Block moves, split, break, join, and reverse operations will be built on this core.

## Quick start

~~~python
from juicebox_assembly import AssemblyFile

document = AssemblyFile.load("genome.review.assembly")
report = AssemblyFile.validate(document)
report.raise_for_errors()

print(report.metrics.total_bp)
print(report.metrics.scaffold_n50_bp)

AssemblyFile.dump(
    document,
    "genome.review.canonical.assembly",
    overwrite=False,
)
~~~

Strict parsing requires canonical Juicebox whitespace and IDs. Diagnostic parsing accepts
general whitespace and non-contiguous source IDs so that the canonical writer can repair them:

~~~python
document = AssemblyFile.load("input.assembly", strict=False)
canonical_text = AssemblyFile.dumps(document)
~~~

## Move components

Use explicit selectors so names, source serial IDs, and stable in-memory keys cannot be confused:

~~~python
from juicebox_assembly import Ref, Target

refs = [
    Ref.name("ptg000123l"),
    Ref.serial_id(145),
]

result = (
    AssemblyFile.edit(document)
    .move_components(
        refs,
        target=Target.last_new_block(),
        order="input",
    )
    .commit()
)

print(result.validation.is_valid)
print(dict(result.id_map))

AssemblyFile.dump(
    result.document,
    "genome.review.moved.assembly",
)
~~~

The default `order="input"` preserves selector order. Use `order="assembly"` to retain the
components' order in the source assembly. Existing orientations are preserved. When a component is
extracted from the middle of a block, the remaining placements are split into contiguous runs so
the edit does not invent a new adjacency.

The SDK treats body lines as assembly blocks or superscaffolds, not automatically as validated
biological chromosomes. It does not modify .hic files or nucleotide sequences.

## Project layout

~~~text
src/juicebox_assembly/
|-- model/               Immutable domain entities
|-- formats/juicebox/    Parser, ID allocator, and canonical writer
|-- validation/          Rules, metrics, and structured reports
|-- operations/          Explicit selectors and pure component moves
|-- history/             Transaction editor and auditable change sets
|-- exceptions.py        Stable package exceptions
+-- sdk.py               Public facade
~~~

Architecture details are in docs/architecture.md. Practical recipes are in the
[Chinese Cookbook](docs/cookbook.md).

## Project relationship

This is an independent, unofficial interoperability project. It is not affiliated with or
endorsed by Aiden Lab or the Juicebox/3D-DNA projects. Product and project names belong to their
respective owners.

## License

Released under the [MIT License](LICENSE).

## Development

The base test suite uses the Python standard library:

~~~bash
python -m unittest discover -s tests -v
~~~

Build a source distribution and wheel after installing the optional development dependencies:

~~~bash
python -m build
~~~

The public API is exported from juicebox_assembly. Internal module paths are not yet stable while
the package remains alpha.
