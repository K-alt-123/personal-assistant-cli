from datetime import date
import unittest

from personal_assistant.address_book import (
    Address,
    AddressBook,
    Birthday,
    Email,
    Name,
    Record,
)
from personal_assistant.errors import DuplicateError, InputError, NotFoundError


def contact_with_birthday(name, birthday):
    contact = Record(name)
    contact.add_phone("0123456789")
    contact.birthday = Birthday(birthday, today=date(2024, 12, 31))
    return contact


class EmailBoundaryTests(unittest.TestCase):
    def test_documented_local_domain_and_total_boundaries(self):
        longest_domain = ".".join(
            ("a" * 63, "b" * 63, "c" * 63, "d" * 60)
        )
        too_long_domain = ".".join(
            ("a" * 63, "b" * 63, "c" * 63, "d" * 61)
        )

        self.assertEqual(len(longest_domain), 252)
        self.assertEqual(len(too_long_domain), 253)
        self.assertEqual(
            Email(("a" * 64) + "@example.com").value[:64],
            "a" * 64,
        )
        self.assertEqual(
            Email("a@" + longest_domain).value,
            "a@" + longest_domain,
        )

        values = (("a" * 65) + "@example.com", "a@" + too_long_domain)
        for value in values:
            with self.subTest(length=len(value)):
                with self.assertRaises(InputError):
                    Email(value)


class TextAndRecordBoundaryTests(unittest.TestCase):
    def test_text_fields_reject_control_and_format_characters(self):
        for value in ("Name\x7f", "Name\u200e", "Name\ud800"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(InputError):
                    Name(value)
                with self.assertRaises(InputError):
                    Address(value)

    def test_rejected_optional_replacements_preserve_prior_values(self):
        record = Record("Alice")
        record.set_address("Kyiv")
        record.set_email("alice@example.com")
        record.add_birthday("01.01.2000")

        with self.assertRaises(InputError):
            record.set_address("Kyiv\nCenter")
        with self.assertRaises(InputError):
            record.set_email("alice.example.com")
        with self.assertRaises(InputError):
            record.add_birthday("31.04.2000")

        self.assertEqual(record.address.value, "Kyiv")
        self.assertEqual(record.email.value, "alice@example.com")
        self.assertEqual(str(record.birthday), "01.01.2000")

    def test_failed_phone_edits_preserve_phone_order(self):
        record = Record("Alice")
        record.add_phone("0123456789")
        record.add_phone("9876543210")
        before = [phone.value for phone in record.phones]

        with self.assertRaises(DuplicateError):
            record.edit_phone("0123456789", "9876543210")
        with self.assertRaises(NotFoundError):
            record.edit_phone("1111111111", "2222222222")

        self.assertEqual([phone.value for phone in record.phones], before)

    def test_records_do_not_share_phone_or_optional_field_state(self):
        first = Record("Alice")
        second = Record("Bob")
        first.add_phone("0123456789")
        second.add_phone("9876543210")
        first.set_address("Kyiv")

        first.add_phone("1111111111")
        self.assertEqual(
            [phone.value for phone in first.phones],
            ["0123456789", "1111111111"],
        )
        self.assertEqual(
            [phone.value for phone in second.phones],
            ["9876543210"],
        )
        self.assertIsNone(second.address)


class BirthdayBoundaryTests(unittest.TestCase):
    def test_one_day_window_keeps_weekend_date_and_orders_same_day_names(self):
        book = AddressBook()
        book.add_record(contact_with_birthday("Bob", "15.06.2000"))
        book.add_record(contact_with_birthday("alice", "15.06.2000"))

        self.assertEqual(
            book.get_upcoming_birthdays(days=1, today=date(2024, 6, 15)),
            [
                {"name": "alice", "birthday_date": "2024-06-15"},
                {"name": "Bob", "birthday_date": "2024-06-15"},
            ],
        )

    def test_three_hundred_sixty_six_day_window_includes_next_leap_day(self):
        book = AddressBook()
        book.add_record(contact_with_birthday("Leap", "29.02.2024"))

        self.assertEqual(
            book.get_upcoming_birthdays(days=366, today=date(2023, 3, 1)),
            [{"name": "Leap", "birthday_date": "2024-02-29"}],
        )


if __name__ == "__main__":
    unittest.main()
