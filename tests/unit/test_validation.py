from __future__ import annotations

import unittest

from juicebox_assembly import (
    AssemblyBlock,
    AssemblyDocument,
    BlockKey,
    Component,
    ComponentKey,
    Orientation,
    Placement,
    loads,
    validate,
)
from tests.unit.test_parser import SAMPLE


class ValidationTests(unittest.TestCase):
    def test_valid_document_metrics(self) -> None:
        report = validate(loads(SAMPLE))

        self.assertTrue(report.is_valid)
        self.assertEqual(report.metrics.components, 3)
        self.assertEqual(report.metrics.blocks, 2)
        self.assertEqual(report.metrics.component_uses, 3)
        self.assertEqual(report.metrics.reverse_components, 1)
        self.assertEqual(report.metrics.total_bp, 600)
        self.assertEqual(report.metrics.scaffold_n50_bp, 300)
        self.assertEqual(report.metrics.scaffold_l50, 1)

    def test_duplicate_and_missing_placements_are_reported(self) -> None:
        document = loads(SAMPLE)
        first = document.components[0].key
        second = document.components[1].key
        bad = AssemblyDocument(
            document.components,
            [
                AssemblyBlock(
                    BlockKey(1),
                    [
                        Placement(first),
                        Placement(first, Orientation.REVERSE),
                        Placement(second),
                    ],
                )
            ],
        )

        codes = {issue.code for issue in validate(bad).errors}
        self.assertIn("E_DUPLICATE_PLACEMENT", codes)
        self.assertIn("E_MISSING_PLACEMENT", codes)

    def test_invalid_fragment_suffix_is_reported(self) -> None:
        component = Component(ComponentKey(1), "seq:::fragment_bad", 100)
        document = AssemblyDocument(
            [component],
            [AssemblyBlock(BlockKey(1), [Placement(component.key)])],
        )

        codes = {issue.code for issue in validate(document).errors}
        self.assertIn("E_INVALID_FRAGMENT_NAME", codes)

    def test_juicebox_int32_length_limit_is_reported(self) -> None:
        component = Component(ComponentKey(1), "huge", 2_147_483_648)
        document = AssemblyDocument(
            [component],
            [AssemblyBlock(BlockKey(1), [Placement(component.key)])],
        )

        codes = {issue.code for issue in validate(document).errors}
        self.assertIn("E_LENGTH_INT32_OVERFLOW", codes)

    def test_source_compatibility_can_be_checked_separately(self) -> None:
        document = loads(">a 10 10\n>b 20 20\n10 20\n", strict=False)

        strict_codes = {issue.code for issue in validate(document).errors}
        rewritten = validate(document, source_compatibility=False)

        self.assertIn("E_ID_NOT_CONTIGUOUS", strict_codes)
        self.assertTrue(rewritten.is_valid)


if __name__ == "__main__":
    unittest.main()
