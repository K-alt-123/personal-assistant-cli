import unittest

from personal_assistant.errors import DuplicateError, InputError, NotFoundError
from personal_assistant.notes import Note, Notebook


class NoteTests(unittest.TestCase):
    def test_note_keeps_its_id_and_text(self):
        note = Note(1, "Buy milk")

        self.assertEqual(note.id, 1)
        self.assertEqual(note.text, "Buy milk")
        self.assertEqual(note.tags, [])
        self.assertIn("1", str(note))
        self.assertIn("Buy milk", str(note))
        self.assertIn("tags", str(note))

    def test_note_trims_text_and_edits_only_after_validation(self):
        note = Note(1, "  Купити молоко  ")

        self.assertEqual(note.text, "Купити молоко")
        note.edit("  Купити хліб  ")
        self.assertEqual(note.text, "Купити хліб")

        invalid_texts = ("", "   ", "line\nbreak", "bad\u200eformat", None, 3)
        for invalid_text in invalid_texts:
            with self.subTest(invalid_text=invalid_text):
                before = note.text
                with self.assertRaises(InputError):
                    note.edit(invalid_text)
                self.assertEqual(note.text, before)

    def test_note_rejects_invalid_ids_and_text(self):
        for invalid_id in (0, -1, True, 1.0, "1", None):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(InputError):
                    Note(invalid_id, "valid")

        for invalid_text in ("", " \t ", "bad\x00text", [], None):
            with self.subTest(invalid_text=invalid_text):
                with self.assertRaises(InputError):
                    Note(1, invalid_text)


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.notebook = Notebook()

    def test_add_find_edit_delete_and_never_reuse_ids(self):
        first = self.notebook.add("First")
        second = self.notebook.add("Second")

        self.assertEqual((first.id, second.id), (1, 2))
        self.assertIs(self.notebook.find(1), first)
        self.assertIsNone(self.notebook.find(99))

        self.notebook.edit(2, "  Changed  ")
        self.assertEqual(second.text, "Changed")
        self.assertEqual(first.text, "First")

        self.notebook.delete(1)
        self.assertIsNone(self.notebook.find(1))
        self.assertEqual(self.notebook.add("Third").id, 3)

    def test_invalid_operations_preserve_data_and_next_id(self):
        first = self.notebook.add("First")
        initial_next_id = self.notebook.next_id

        for invalid_text in ("", "bad\ntext", None):
            with self.subTest(invalid_text=invalid_text):
                with self.assertRaises(InputError):
                    self.notebook.add(invalid_text)
                self.assertEqual(self.notebook.next_id, initial_next_id)
                self.assertEqual(self.notebook.all_items(), [first])

        for invalid_id in (0, True, "1", None):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(InputError):
                    self.notebook.find(invalid_id)

        with self.assertRaises(NotFoundError):
            self.notebook.edit(99, "Changed")
        with self.assertRaises(NotFoundError):
            self.notebook.delete(99)

        with self.assertRaises(InputError):
            self.notebook.edit(True, "Changed")
        with self.assertRaises(InputError):
            self.notebook.edit(first.id, None)
        with self.assertRaises(InputError):
            self.notebook.delete("1")
        self.assertEqual(first.text, "First")

    def test_search_and_listing_are_casefolded_and_sorted_by_id(self):
        third = self.notebook.add("Київський торт")
        first = self.notebook.add("Buy Milk")
        second = self.notebook.add("milk and bread")

        self.assertEqual(self.notebook.search("MILK"), [first, second])
        self.assertEqual(self.notebook.search("КИЇВСЬКИЙ"), [third])
        self.assertEqual(self.notebook.all_items(), [third, first, second])

        for invalid_query in ("", "  ", None, 1, "bad\x00query"):
            with self.subTest(invalid_query=invalid_query):
                with self.assertRaises(InputError):
                    self.notebook.search(invalid_query)


class NoteTagTests(unittest.TestCase):
    def test_tags_are_normalized_and_rejected_changes_preserve_them(self):
        note = Note(1, "Plan trip")

        note.add_tag("  Travel  ")
        note.add_tag("Україна")
        self.assertEqual(note.tags, ["travel", "україна"])

        for invalid_tag in ("", "  ", "bad\nlabel", None, 5):
            with self.subTest(invalid_tag=invalid_tag):
                before = note.tags.copy()
                with self.assertRaises(InputError):
                    note.add_tag(invalid_tag)
                self.assertEqual(note.tags, before)

        with self.assertRaises(DuplicateError):
            note.add_tag("TRAVEL")
        self.assertEqual(note.tags, ["travel", "україна"])

        note.remove_tag(" УКРАЇНА ")
        self.assertEqual(note.tags, ["travel"])
        with self.assertRaises(NotFoundError):
            note.remove_tag("missing")
        self.assertEqual(note.tags, ["travel"])

        for invalid_tag in ("", None, 5, "bad\x00tag"):
            with self.subTest(invalid_tag=invalid_tag):
                before = note.tags.copy()
                with self.assertRaises(InputError):
                    note.remove_tag(invalid_tag)
                self.assertEqual(note.tags, before)

    def test_tag_filter_is_exact_and_tag_sort_is_deterministic(self):
        notebook = Notebook()
        beta = notebook.add("Beta")
        alpha = notebook.add("Alpha")
        untagged = notebook.add("Untagged")
        gamma = notebook.add("Gamma")

        beta.add_tag(" work ")
        beta.add_tag("urgent")
        alpha.add_tag("urgent")
        gamma.add_tag("Work")

        self.assertEqual(notebook.by_tag("URGENT"), [beta, alpha])
        self.assertEqual(notebook.by_tag("urge"), [])
        self.assertEqual(
            notebook.sorted_by_tags(),
            [alpha, beta, gamma, untagged],
        )

        for invalid_tag in ("", "\t", None, 4, "bad\x00tag"):
            with self.subTest(invalid_tag=invalid_tag):
                with self.assertRaises(InputError):
                    notebook.by_tag(invalid_tag)


if __name__ == "__main__":
    unittest.main()
