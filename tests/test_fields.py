from datetime import date
import unittest

from personal_assistant.address_book import (
    Address,
    Birthday,
    Email,
    Name,
    Phone,
)
from personal_assistant.errors import InputError


class FieldValidationTests(unittest.TestCase):
    def test_text_fields_trim_outer_spaces_and_preserve_unicode(self):
        self.assertEqual(Name("  Ірина Коваль  ").value, "Ірина Коваль")
        self.assertEqual(
            Address("  Київ, вул. Миру 1  ").value,
            "Київ, вул. Миру 1",
        )

    def test_text_fields_reject_blank_wrong_type_and_control_characters(self):
        for field_class in (Name, Address):
            for value in ("", "   ", None, 42, "name\nother"):
                with self.subTest(field=field_class.__name__, value=value):
                    with self.assertRaises(InputError):
                        field_class(value)

    def test_phone_accepts_exactly_ten_ascii_digits_without_trimming(self):
        self.assertEqual(Phone("0123456789").value, "0123456789")
        values = (
            "123456789",
            "12345678901",
            "01234 6789",
            " 0123456789",
            "٠١٢٣٤٥٦٧٨٩",
            1234567890,
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(InputError):
                    Phone(value)

    def test_email_normalizes_only_domain_and_rejects_bad_shape(self):
        self.assertEqual(
            Email("Mary+test@EXAMPLE.Com").value,
            "Mary+test@example.com",
        )
        values = (
            "maryexample.com",
            "mary@@example.com",
            "@example.com",
            "mary@-example.com",
            "mary@example..com",
            "mary @example.com",
            None,
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(InputError):
                    Email(value)

    def test_birthday_has_strict_calendar_format_and_no_future_dates(self):
        birthday = Birthday("29.02.2024", today=date(2024, 3, 1))
        self.assertEqual(birthday.value, date(2024, 2, 29))
        self.assertEqual(str(birthday), "29.02.2024")
        values = (
            "29.02.2023",
            "1.01.2020",
            "2020-01-01",
            "31.04.2020",
            "02.03.2024",
            None,
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(InputError):
                    Birthday(value, today=date(2024, 3, 1))

    def test_birthday_keeps_a_four_digit_year_for_year_one(self):
        birthday = Birthday("01.01.0001", today=date(1, 1, 1))
        self.assertEqual(str(birthday), "01.01.0001")


if __name__ == "__main__":
    unittest.main()
