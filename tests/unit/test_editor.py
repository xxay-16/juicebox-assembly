from __future__ import annotations

import unittest

from juicebox_assembly import (
    AssemblyDocument,
    AssemblyEditError,
    AssemblyFile,
    AssemblyEditor,
    ComponentNotFound,
    MoveOrder,
    Ref,
    Target,
    dumps,
    loads,
)


MOVE_SAMPLE = """>a 1 10
>b 2 20
>c 3 30
>d 4 40
>e 5 50
1 -2 3 4
-5
"""


def block_source_ids(document: AssemblyDocument) -> list[list[int]]:
    components = {component.key: component for component in document.components}
    return [
        [
            placement.orientation.sign * components[placement.component].source_serial_id
            for placement in block.placements
        ]
        for block in document.blocks
    ]


class EditorTests(unittest.TestCase):
    def test_move_uses_input_order_and_preserves_orientation(self) -> None:
        document = loads(MOVE_SAMPLE)
        result = (
            AssemblyEditor(document)
            .move_components(
                [Ref.name("d"), Ref.serial_id(2)],
                target=Target.last_new_block(),
            )
            .commit()
        )

        self.assertEqual(block_source_ids(result.document), [[1], [3], [-5], [4, -2]])
        self.assertEqual(result.document.components, document.components)
        self.assertEqual(result.document.metadata, document.metadata)
        self.assertTrue(result.validation.is_valid)
        self.assertEqual(dict(result.id_map), {1: 1, 2: 2, 3: 3, 4: 4, 5: 5})

        change = result.changeset.changes[0]
        self.assertEqual([key.value for key in change.component_keys], [4, 2])
        self.assertEqual([key.value for key in change.source_block_keys], [1])
        self.assertEqual(change.target_block_key, result.document.blocks[-1].key)
        self.assertIs(change.order, MoveOrder.INPUT)

    def test_move_can_use_assembly_order(self) -> None:
        result = (
            AssemblyEditor(loads(MOVE_SAMPLE))
            .move_components(
                [Ref.name("d"), Ref.name("b")],
                target=Target.last_new_block(),
                order="assembly",
            )
            .commit()
        )

        self.assertEqual(block_source_ids(result.document)[-1], [-2, 4])
        self.assertIs(result.changeset.changes[0].order, MoveOrder.ASSEMBLY)

    def test_middle_extraction_splits_survivors_into_separate_blocks(self) -> None:
        result = (
            AssemblyEditor(loads(MOVE_SAMPLE))
            .move_components(
                [Ref.name("b")],
                target=Target.last_new_block(),
            )
            .commit()
        )

        self.assertEqual(block_source_ids(result.document), [[1], [3, 4], [-5], [-2]])
        block_keys = [block.key.value for block in result.document.blocks]
        self.assertEqual(len(block_keys), len(set(block_keys)))

    def test_move_all_members_does_not_leave_an_empty_block(self) -> None:
        result = (
            AssemblyEditor(loads(MOVE_SAMPLE))
            .move_components(
                [Ref.serial_id(5)],
                target=Target.last_new_block(),
            )
            .commit()
        )

        self.assertEqual(block_source_ids(result.document), [[1, -2, 3, 4], [-5]])
        self.assertTrue(all(block.placements for block in result.document.blocks))

    def test_failed_move_does_not_change_editor(self) -> None:
        document = loads(MOVE_SAMPLE)
        editor = AssemblyEditor(document)

        with self.assertRaises(ComponentNotFound):
            editor.move_components(
                [Ref.name("missing")],
                target=Target.last_new_block(),
            )

        self.assertIs(editor.document, document)
        self.assertEqual(len(editor.commit().changeset), 0)

    def test_duplicate_selection_is_rejected(self) -> None:
        editor = AssemblyEditor(loads(MOVE_SAMPLE))

        with self.assertRaises(AssemblyEditError) as caught:
            editor.move_components(
                [Ref.name("b"), Ref.serial_id(2)],
                target=Target.last_new_block(),
            )

        self.assertEqual(caught.exception.code, "E_DUPLICATE_SELECTION")

    def test_empty_selection_is_rejected(self) -> None:
        with self.assertRaises(AssemblyEditError) as caught:
            AssemblyEditor(loads(MOVE_SAMPLE)).move_components(
                [],
                target=Target.last_new_block(),
            )

        self.assertEqual(caught.exception.code, "E_EMPTY_SELECTION")

    def test_committed_editor_is_closed(self) -> None:
        editor = AssemblyEditor(loads(MOVE_SAMPLE))
        editor.commit()

        with self.assertRaises(AssemblyEditError) as caught:
            editor.commit()

        self.assertEqual(caught.exception.code, "E_EDITOR_CLOSED")

    def test_moved_document_round_trips_canonically(self) -> None:
        result = (
            AssemblyEditor(loads(MOVE_SAMPLE))
            .move_components(
                [Ref.key(4), Ref.key(2)],
                target=Target.last_new_block(),
            )
            .commit()
        )
        rendered = dumps(result.document)

        self.assertEqual(dumps(loads(rendered)), rendered)


    def test_sequential_moves_keep_block_keys_unique(self) -> None:
        editor = AssemblyEditor(loads(MOVE_SAMPLE))
        editor.move_components(
            [Ref.name("b")],
            target=Target.last_new_block(),
        )
        editor.move_components(
            [Ref.name("d")],
            target=Target.last_new_block(),
        )
        result = editor.commit()

        self.assertEqual(block_source_ids(result.document)[-2:], [[-2], [4]])
        block_keys = [block.key.value for block in result.document.blocks]
        self.assertEqual(len(block_keys), len(set(block_keys)))
        self.assertEqual(len(result.changeset), 2)

    def test_move_every_component_creates_one_final_block(self) -> None:
        result = (
            AssemblyEditor(loads(MOVE_SAMPLE))
            .move_components(
                [
                    Ref.name("e"),
                    Ref.name("d"),
                    Ref.name("c"),
                    Ref.name("b"),
                    Ref.name("a"),
                ],
                target=Target.last_new_block(),
            )
            .commit()
        )

        self.assertEqual(block_source_ids(result.document), [[-5, 4, 3, -2, 1]])

    def test_invalid_move_order_is_rejected(self) -> None:
        with self.assertRaises(AssemblyEditError) as caught:
            AssemblyEditor(loads(MOVE_SAMPLE)).move_components(
                [Ref.name("a")],
                target=Target.last_new_block(),
                order="unknown",
            )

        self.assertEqual(caught.exception.code, "E_INVALID_MOVE_ORDER")

    def test_facade_and_diagnostic_id_map(self) -> None:
        document = loads(">a 10 10\n>b 20 20\n10 -20\n", strict=False)
        result = (
            AssemblyFile.edit(document)
            .move_components(
                [Ref.serial_id(20)],
                target=Target.last_new_block(),
            )
            .commit()
        )

        self.assertEqual(dict(result.id_map), {10: 1, 20: 2})
        self.assertEqual(dumps(result.document), ">a 1 10\n>b 2 20\n1\n-2\n")

if __name__ == "__main__":
    unittest.main()
