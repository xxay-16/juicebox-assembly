from __future__ import annotations

import unittest

from juicebox_assembly import AssemblyParseError, Orientation, loads


SAMPLE = """>seq1 1 100
>seq2:::fragment_1 2 200
>seq3:::debris 3 300
1 2
-3
"""


class ParserTests(unittest.TestCase):
    def test_parse_canonical_document(self) -> None:
        document = loads(SAMPLE)

        self.assertEqual([component.name for component in document.components], [
            "seq1",
            "seq2:::fragment_1",
            "seq3:::debris",
        ])
        self.assertEqual(document.total_length, 600)
        self.assertEqual(len(document.blocks), 2)
        self.assertIs(
            document.blocks[1].placements[0].orientation,
            Orientation.REVERSE,
        )
        self.assertTrue(document.metadata.parsed_strictly)
        self.assertIsNotNone(document.metadata.source_sha256)

    def test_strict_parser_rejects_noncanonical_whitespace(self) -> None:
        text = ">seq1  1 100\n1\n"
        with self.assertRaises(AssemblyParseError) as caught:
            loads(text)
        self.assertEqual(caught.exception.code, "E_PARSE_HEADER")

    def test_diagnostic_parser_accepts_general_whitespace(self) -> None:
        text = ">seq1\t10\t100\n10\n"
        document = loads(text, strict=False)

        self.assertEqual(document.components[0].source_serial_id, 10)
        self.assertFalse(document.metadata.parsed_strictly)

    def test_strict_parser_requires_ids_to_match_header_order(self) -> None:
        text = ">seq1 2 100\n2\n"
        with self.assertRaises(AssemblyParseError) as caught:
            loads(text)
        self.assertEqual(caught.exception.code, "E_ID_NOT_CONTIGUOUS")

    def test_parser_rejects_undefined_reference(self) -> None:
        text = ">seq1 1 100\n2\n"
        with self.assertRaises(AssemblyParseError) as caught:
            loads(text)
        self.assertEqual(caught.exception.code, "E_UNDEFINED_REFERENCE")

    def test_parser_rejects_header_after_body(self) -> None:
        text = ">seq1 1 100\n1\n>seq2 2 200\n"
        with self.assertRaises(AssemblyParseError) as caught:
            loads(text)
        self.assertEqual(caught.exception.code, "E_HEADER_AFTER_BODY")


if __name__ == "__main__":
    unittest.main()
