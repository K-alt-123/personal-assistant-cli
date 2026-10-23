import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from personal_assistant.address_book import AddressBook, Record
from personal_assistant.errors import StorageError
from personal_assistant.notes import Notebook
from personal_assistant import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.filename = self.directory / "data.json"
        self.book = AddressBook()
        contact = Record("Олена Коваль")
        contact.add_phone("0501234567")
        contact.add_phone("0123456789")
        contact.set_address("Київ, вул. Липова 4")
        contact.set_email("olena+work@Example.org")
        contact.add_birthday("29.02.2000")
        self.book.add_record(contact)
        self.notes = Notebook()
        self.notes.add("Prepare the demo")

    def save(self):
        storage.save_data(self.book, self.notes, self.filename)

    def test_missing_file_is_a_fresh_independent_state(self):
        first_book, first_notes = storage.load_data(self.filename)
        second_book, second_notes = storage.load_data(self.filename)
        self.assertEqual(dict(first_book), {})
        self.assertEqual(dict(first_notes), {})
        self.assertIsNot(first_book, second_book)
        self.assertIsNot(first_notes, second_notes)
        self.assertFalse(self.filename.exists())

    def test_round_trip_restores_every_field_and_independent_objects(self):
        self.save()
        book, notes = storage.load_data(self.filename)
        record = book.find("Олена Коваль")
        self.assertEqual([p.value for p in record.phones],
                         ["0501234567", "0123456789"])
        self.assertEqual(record.address.value, "Київ, вул. Липова 4")
        self.assertEqual(record.email.value, "olena+work@example.org")
        self.assertEqual(str(record.birthday), "29.02.2000")
        self.assertEqual(notes.find(1).text, "Prepare the demo")
        self.assertEqual(notes.next_id, 2)
        record.edit_phone("0501234567", "0991234567")
        notes.edit(1, "Changed")
        self.assertEqual(self.book.find("Олена Коваль").phones[0].value,
                         "0501234567")
        self.assertEqual(self.notes.find(1).text, "Prepare the demo")

    def test_empty_optional_fields_and_deleted_ids_survive(self):
        self.book.add_record(Record("Empty"))
        self.notes.delete(1)
        self.save()
        book, notes = storage.load_data(self.filename)
        record = book.find("Empty")
        self.assertEqual(record.phones, [])
        self.assertIsNone(record.email)
        self.assertIsNone(record.address)
        self.assertIsNone(record.birthday)
        self.assertEqual(notes.add("Second").id, 2)

    def test_default_path_is_in_home_and_resolved_at_call_time(self):
        with patch("personal_assistant.storage.Path.home",
                   return_value=self.directory):
            expected = self.directory / ".personal_assistant" / "data.json"
            self.assertEqual(storage.default_file(), expected)
            storage.save_data(self.book, self.notes)
            self.assertTrue(expected.is_file())
            self.assertEqual(len(storage.load_data()[0]), 1)

    def test_parent_directory_is_created_only_when_saving(self):
        filename = self.directory / "nested" / "data.json"
        storage.load_data(filename)
        self.assertFalse(filename.parent.exists())
        storage.save_data(self.book, self.notes, filename)
        self.assertTrue(filename.is_file())

    def test_invalid_json_never_overwrites_original_bytes(self):
        cases = (b"", b"{", b"not json", b"[]", b"null", b"\xff",
                 b'{"version":1,"version":1}', b'{"value":NaN}')
        for content in cases:
            with self.subTest(content=content):
                self.filename.write_bytes(content)
                with self.assertRaises(StorageError):
                    storage.load_data(self.filename)
                self.assertEqual(self.filename.read_bytes(), content)

    def test_strict_saved_schema_and_domain_values(self):
        self.save()
        original = json.loads(self.filename.read_text(encoding="utf-8"))
        cases = []
        for key, value in (("version", 2), ("version", True),
                           ("contacts", {}), ("notes", None),
                           ("next_note_id", True), ("next_note_id", 1)):
            data = copy.deepcopy(original)
            data[key] = value
            cases.append(data)
        for key, value in (("name", ""), ("phones", ["123"]),
                           ("phones", ["0501234567", "0501234567"]),
                           ("address", 42), ("email", "bad"),
                           ("birthday", "31.02.2000")):
            data = copy.deepcopy(original)
            data["contacts"][0][key] = value
            cases.append(data)
        for key, value in (("id", True), ("id", 0), ("text", " "),
                           ("tags", "tag"), ("tags", ["x", "X"])):
            data = copy.deepcopy(original)
            data["notes"][0][key] = value
            cases.append(data)
        data = copy.deepcopy(original)
        del data["contacts"][0]["name"]
        cases.append(data)
        for key in ("contacts", "notes"):
            data = copy.deepcopy(original)
            data[key].append(copy.deepcopy(data[key][0]))
            cases.append(data)
        data = copy.deepcopy(original)
        data["extra"] = "unsupported"
        cases.append(data)
        for data in cases:
            with self.subTest(data=data):
                content = json.dumps(data).encode()
                self.filename.write_bytes(content)
                with self.assertRaises(StorageError):
                    storage.load_data(self.filename)
                self.assertEqual(self.filename.read_bytes(), content)

    def test_read_errors_are_not_treated_as_first_run(self):
        with patch("pathlib.Path.open", side_effect=PermissionError("denied")):
            with self.assertRaises(StorageError):
                storage.load_data(self.filename)
        with self.assertRaises(StorageError):
            storage.load_data(self.directory)

    def test_save_failures_preserve_previous_file_and_clean_temporary(self):
        self.save()
        original = self.filename.read_bytes()
        self.notes.add("Unsaved")
        for target in ("tempfile.NamedTemporaryFile", "json.dump",
                       "os.fsync", "os.replace"):
            with self.subTest(target=target):
                with patch("personal_assistant.storage." + target,
                           side_effect=OSError("disk error")):
                    with self.assertRaises(StorageError):
                        self.save()
                self.assertEqual(self.filename.read_bytes(), original)
                self.assertEqual(list(self.directory.iterdir()),
                                 [self.filename])

    def test_partial_write_failure_preserves_old_file(self):
        self.save()
        original = self.filename.read_bytes()

        def partial_write(data, file, **kwargs):
            file.write('{"version":')
            raise OSError("disk full")

        with patch("personal_assistant.storage.json.dump",
                   side_effect=partial_write):
            with self.assertRaisesRegex(StorageError, "disk full"):
                self.save()
        self.assertEqual(self.filename.read_bytes(), original)
        self.assertEqual(list(self.directory.iterdir()), [self.filename])

    def test_flush_failure_and_cleanup_failure_keep_primary_error(self):
        self.save()
        original = self.filename.read_bytes()
        factory = tempfile.NamedTemporaryFile

        def unflushable(*args, **kwargs):
            file = factory(*args, **kwargs)

            def fail_flush():
                raise OSError("flush failed")

            file.flush = fail_flush
            return file

        with patch("personal_assistant.storage.tempfile.NamedTemporaryFile",
                   side_effect=unflushable):
            with self.assertRaisesRegex(StorageError, "flush failed"):
                self.save()
        self.assertEqual(self.filename.read_bytes(), original)
        with patch("personal_assistant.storage.os.replace",
                   side_effect=OSError("replace failed")):
            with patch("pathlib.Path.unlink", side_effect=OSError("cleanup")):
                with self.assertRaisesRegex(StorageError, "replace failed"):
                    self.save()
        self.assertEqual(self.filename.read_bytes(), original)

    def test_bad_in_memory_state_is_rejected_before_replacement(self):
        self.save()
        original = self.filename.read_bytes()
        self.book.find("Олена Коваль").phones[0].value = "bad"
        with self.assertRaises(StorageError):
            self.save()
        self.assertEqual(self.filename.read_bytes(), original)

    def test_mkdir_failure_does_not_create_data(self):
        with patch("pathlib.Path.mkdir",
                   side_effect=PermissionError("denied")):
            with self.assertRaises(StorageError):
                self.save()
        self.assertFalse(self.filename.exists())


if __name__ == "__main__":
    unittest.main()
