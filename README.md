# juicebox-assembly

A typed Python SDK for Juicebox/3D-DNA .assembly files.

This repository currently contains the foundational v0.1 core:

- immutable domain objects;
- strict and diagnostic parsers;
- structural and Juicebox compatibility validation;
- canonical UTF-8 serialization;
- atomic file writes;
- assembly statistics.

Move, split, break, join, and reverse operations will be built on this core.

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

The SDK treats body lines as assembly blocks or superscaffolds, not automatically as validated
biological chromosomes. It does not modify .hic files or nucleotide sequences.

## Project layout

~~~text
src/juicebox_assembly/
|-- model/               Immutable domain entities
|-- formats/juicebox/    Parser, ID allocator, and canonical writer
|-- validation/          Rules, metrics, and structured reports
|-- operations/          Pure structural edits (next milestone)
|-- history/             Transactions and change sets (next milestone)
|-- exceptions.py        Stable package exceptions
+-- sdk.py               Public facade
~~~

Architecture details are in docs/architecture.md.

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
