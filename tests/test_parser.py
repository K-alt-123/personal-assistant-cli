import unittest

from personal_assistant import assistant
from personal_assistant.errors import InputError


class ParserTests(unittest.TestCase):
    def test_command_case_and_quoted_arguments(self):
        self.assertEqual(
            assistant.parse_input('  AdD "Олена Коваль" 0501234567  '),
            ("add", ["Олена Коваль", "0501234567"]),
        )

    def test_apostrophes_and_literal_shell_characters(self):
        self.assertEqual(
            assistant.parse_input('note-add "O\'Neil uses $(example); ok"'),
            ("note-add", ["O'Neil uses $(example); ok"]),
        )

    def test_blank_input_is_inert(self):
        for value in ("", " ", "\t"):
            with self.subTest(value=value):
                self.assertEqual(assistant.parse_input(value), ("", []))

    def test_unmatched_quotes_and_wrong_types_are_expected_errors(self):
        for value in ('add "unfinished', None, 123):
            with self.subTest(value=value), self.assertRaises(InputError):
                assistant.parse_input(value)

    def test_decorator_keeps_metadata_and_handles_only_input_errors(self):
        @assistant.input_error
        def expected():
            raise InputError("Phone must contain 10 digits.")

        @assistant.input_error
        def broken():
            raise TypeError("programming mistake")

        self.assertEqual(expected.__name__, "expected")
        result = expected()
        self.assertEqual(result.message, "Phone must contain 10 digits.")
        self.assertFalse(result.changed)
        self.assertFalse(result.exit_requested)
        with self.assertRaises(TypeError):
            broken()


if __name__ == "__main__":
    unittest.main()
