from datetime import date
import unittest

from personal_assistant.address_book import AddressBook, Birthday, Record
from personal_assistant.errors import InputError


def record_with_birthday(name, birthday):
    record = Record(name)
    record.add_phone("0123456789")
    record.birthday = Birthday(birthday, today=date(2024, 12, 31))
    return record


class BirthdayWindowTests(unittest.TestCase):
    def test_window_includes_today_last_day_and_new_year_rollover(self):
        book = AddressBook()
        birthdays = (
            ("Today", "28.12.2000"),
            ("New year", "01.01.2000"),
            ("Last", "03.01.2000"),
            ("Outside", "04.01.2000"),
        )
        for name, birthday in birthdays:
            book.add_record(record_with_birthday(name, birthday))

        result = book.get_upcoming_birthdays(days=7, today=date(2024, 12, 28))
        self.assertEqual(
            result,
            [
                {"name": "Today", "birthday_date": "2024-12-28"},
                {"name": "New year", "birthday_date": "2025-01-01"},
                {"name": "Last", "birthday_date": "2025-01-03"},
            ],
        )

    def test_leap_day_uses_february_twenty_eighth_in_a_nonleap_year(self):
        book = AddressBook()
        book.add_record(record_with_birthday("Leap", "29.02.2024"))

        self.assertEqual(
            book.get_upcoming_birthdays(days=2, today=date(2023, 2, 27)),
            [{"name": "Leap", "birthday_date": "2023-02-28"}],
        )

    def test_days_must_be_an_integer_window_from_one_through_366(self):
        book = AddressBook()
        for days in (False, 0, 367, "7", 2.5):
            with self.subTest(days=days):
                with self.assertRaises(InputError):
                    book.get_upcoming_birthdays(
                        days=days,
                        today=date(2024, 1, 1),
                    )

    def test_long_window_handles_leap_year_and_last_supported_year(self):
        book = AddressBook()
        book.add_record(record_with_birthday("Leap", "29.02.2024"))
        self.assertEqual(
            book.get_upcoming_birthdays(days=366, today=date(2023, 3, 1)),
            [{"name": "Leap", "birthday_date": "2024-02-29"}],
        )

        last_year = AddressBook()
        last_year.add_record(record_with_birthday("Later", "01.01.2000"))
        self.assertEqual(last_year.get_upcoming_birthdays(today=date.max), [])


if __name__ == "__main__":
    unittest.main()
