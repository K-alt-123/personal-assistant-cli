import unittest

from personal_assistant.address_book import AddressBook, Record
from personal_assistant.errors import DuplicateError, InputError, NotFoundError


class RecordTests(unittest.TestCase):
    def test_phone_changes_preserve_order_and_reject_duplicates(self):
        record = Record("Ірина")
        record.add_phone("0123456789")
        record.add_phone("9876543210")

        record.edit_phone("0123456789", "1111111111")
        self.assertEqual(
            [phone.value for phone in record.phones],
            ["1111111111", "9876543210"],
        )
        self.assertEqual(record.find_phone("9876543210").value, "9876543210")
        self.assertIsNone(record.find_phone("0123456789"))

        with self.assertRaises(DuplicateError):
            record.add_phone("1111111111")
        with self.assertRaises(NotFoundError):
            record.remove_phone("0123456789")
        before = [phone.value for phone in record.phones]
        with self.assertRaises(InputError):
            record.edit_phone("1111111111", "short")
        self.assertEqual([phone.value for phone in record.phones], before)

    def test_optional_fields_set_and_clear_explicitly(self):
        record = Record("Марія")
        record.set_address("  Київ  ")
        record.set_email("maria@EXAMPLE.com")
        record.add_birthday("01.01.2000")

        self.assertEqual(record.address.value, "Київ")
        self.assertEqual(record.email.value, "maria@example.com")
        self.assertEqual(str(record.birthday), "01.01.2000")
        record.clear_field("email")
        self.assertIsNone(record.email)
        for field in ("phones", []):
            with self.subTest(field=field):
                with self.assertRaises(InputError):
                    record.clear_field(field)


class AddressBookTests(unittest.TestCase):
    def _record(self, name, phone):
        record = Record(name)
        record.add_phone(phone)
        return record

    def test_add_find_delete_and_rename_keep_exact_name_keys(self):
        book = AddressBook()
        maria = self._record("Марія", "0123456789")
        other = self._record("Олена", "9876543210")
        book.add_record(maria)
        book.add_record(other)

        self.assertIs(book.find("Марія"), maria)
        self.assertIsNone(book.find("марія"))
        for name in (None, []):
            with self.subTest(name=name):
                with self.assertRaises(InputError):
                    book.find(name)
        with self.assertRaises(DuplicateError):
            book.add_record(self._record("Марія", "1111111111"))
        with self.assertRaises(DuplicateError):
            book.rename(" Марія ", " Олена ")
        book.rename(" Марія ", " Марія ")
        self.assertIs(book.find("Марія"), maria)
        book.rename(" Марія ", " Марічка ")
        self.assertIsNone(book.find("Марія"))
        self.assertIs(book.find("Марічка"), maria)
        book.rename("Марічка", "Марічка")
        book.delete(" Олена ")
        self.assertIsNone(book.find("Олена"))
        with self.assertRaises(NotFoundError):
            book.delete("Олена")

    def test_searches_substrings_across_requested_field_in_name_order(self):
        book = AddressBook()
        anna = self._record("Анна", "0123456789")
        anna.set_email("anna@Example.com")
        anna.set_address("Львів")
        zoe = self._record("Zoë", "9876543210")
        zoe.set_address("Київ")
        book.add_record(zoe)
        book.add_record(anna)

        self.assertEqual(
            [record.name.value for record in book.search("АН")], ["Анна"]
        )
        self.assertEqual(
            [record.name.value for record in book.search("example", "email")],
            ["Анна"],
        )
        self.assertEqual(
            [record.name.value for record in book.search("КИЇВ", "address")],
            ["Zoë"],
        )
        self.assertEqual(
            [record.name.value for record in book.search("210", "phone")],
            ["Zoë"],
        )
        self.assertEqual(
            [record.name.value for record in book.search("z")], ["Zoë"]
        )
        with self.assertRaises(InputError):
            book.search("", "name")
        with self.assertRaises(InputError):
            book.search("anna", "birthday")
        with self.assertRaises(InputError):
            book.search("anna", [])


if __name__ == "__main__":
    unittest.main()
