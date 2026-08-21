from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from juicebox_assembly import (
    AssemblyFile,
    AssemblyWriteError,
    dumps,
    load,
    loads,
)
from tests.unit.test_parser import SAMPLE


class WriterTests(unittest.TestCase):
    def test_round_trip_is_canonical(self) -> None:
        document = loads(SAMPLE)
        rendered = dumps(document)

        self.assertEqual(rendered, SAMPLE)
        self.assertEqual(loads(rendered), document)

    def test_writer_repairs_noncanonical_source_ids(self) -> None:
        source = ">a 10 10\n>b 20 20\n10 -20\n"
        document = loads(source, strict=False)

        self.assertEqual(dumps(document), ">a 1 10\n>b 2 20\n1 -2\n")

    def test_atomic_dump_and_reload(self) -> None:
        document = AssemblyFile.loads(SAMPLE)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "output.assembly"
            result = AssemblyFile.dump(document, destination)

            self.assertEqual(result, destination)
            reloaded = load(destination)
            self.assertEqual(reloaded.components, document.components)
            self.assertEqual(reloaded.blocks, document.blocks)

    def test_dump_refuses_existing_output_by_default(self) -> None:
        document = loads(SAMPLE)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "output.assembly"
            destination.write_text("existing", encoding="utf-8")

            with self.assertRaises(AssemblyWriteError) as caught:
                AssemblyFile.dump(document, destination)
            self.assertEqual(caught.exception.code, "E_OUTPUT_EXISTS")
            self.assertEqual(destination.read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
