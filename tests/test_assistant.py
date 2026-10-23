import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from personal_assistant import assistant, storage
from personal_assistant.address_book import AddressBook
from personal_assistant.errors import StorageError
from personal_assistant.notes import Notebook


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.book, self.notes = AddressBook(), Notebook()

    def command(self, text):
        command, args = assistant.parse_input(text)
        return assistant.handle_command(command, args, self.book, self.notes)

    def test_contact_commands(self):
        self.assertTrue(self.command('add "Олена Коваль" 0501234567').changed)
        for command in (
            'add "Олена Коваль" 0123456789',
            'set-address "Олена Коваль" "Київ, Липова 4"',
            'set-email "Олена Коваль" olena@Example.org',
            'add-birthday "Олена Коваль" 29.02.2000',
        ):
            self.assertTrue(self.command(command).changed)
        output = self.command('show "Олена Коваль"').message
        for value in ("0501234567", "0123456789", "Липова 4",
                      "olena@example.org", "29.02.2000"):
            self.assertIn(value, output)
        self.command('change "Олена Коваль" 0123456789 0991234567')
        self.command('remove-phone "Олена Коваль" 0501234567')
        self.assertEqual(self.command('phone "Олена Коваль"').message,
                         "0991234567")
        self.command('rename "Олена Коваль" "Олена"')
        self.assertIsNone(self.book.find("Олена Коваль"))
        self.assertIn("Олена", self.command('find "київ" address').message)
        self.command('clear-field "Олена" email')
        self.assertIsNone(self.book.find("Олена").email)
        self.assertIn("29.02.2000",
                      self.command('show-birthday "Олена"').message)

    def test_note_and_tag_commands(self):
        self.assertIn("1", self.command('note-add "Read Python"').message)
        self.command('tag-add 1 "Study"')
        for command in ('notes-tag "study"', "notes-sort-tags", "notes"):
            self.assertIn("Read Python", self.command(command).message)
        self.command('note-edit 1 "Read OOP"')
        for command in ('note-show 1', 'note-find "oop"'):
            self.assertIn("Read OOP", self.command(command).message)
        self.command('tag-remove 1 "STUDY"')
        self.assertEqual(self.notes.find(1).tags, [])
        self.assertIn("No notes", self.command('notes-tag "study"').message)

    def test_invalid_commands_leave_everything_unchanged(self):
        self.command("add Alice 0501234567")
        self.command('note-add "Keep me"')
        before = storage.to_data(self.book, self.notes)
        commands = (
            "unknown", "add Bob 123", "change Alice 0501234567 123",
            "set-email Alice broken", 'set-address Alice ""',
            "add-birthday Alice 31.02.2000", 'rename Alice ""',
            "phone Nobody", "delete Nobody", "note-show 999",
            'note-edit 1 ""', "note-delete 999", "note-show 0",
            "note-show -1", "note-show 1.0", "note-show ١",
            "note-show " + "9" * 5000, "birthdays 0", "birthdays 367",
            "birthdays 2.5", 'find ""', "find Alice unsupported",
            "clear-field Alice name", 'tag-add 1 ""',
            "tag-remove 1 missing", "exit extra",
        )
        for command in commands:
            with self.subTest(command=command[:80]):
                result = self.command(command)
                self.assertFalse(result.changed)
                self.assertFalse(result.exit_requested)
                self.assertTrue(result.message)
                self.assertEqual(
                    storage.to_data(self.book, self.notes), before,
                )

    def test_argument_counts_for_every_command(self):
        samples = {
            "hello": "", "help": "", "exit": "", "close": "",
            "all": "", "show": "Alice", "phone": "Alice",
            "add": "Alice 0501234567", "change": "Alice 1 2",
            "remove-phone": "Alice 1", "rename": "Alice Bob",
            "set-address": "Alice Kyiv", "set-email": "Alice a@b.co",
            "add-birthday": "Alice 01.01.2000", "show-birthday": "Alice",
            "clear-field": "Alice email", "delete": "Alice",
            "note-add": "text", "notes": "", "note-show": "1",
            "note-find": "text", "note-edit": "1 text", "note-delete": "1",
            "tag-add": "1 study", "tag-remove": "1 study",
            "notes-tag": "study", "notes-sort-tags": "",
            "birthdays": "7", "find": "Alice name",
        }
        for command, args in samples.items():
            with self.subTest(command=command):
                result = self.command(f"{command} {args} unexpected")
                self.assertIn("Usage:", result.message)
                self.assertFalse(result.changed)
                self.assertFalse(result.exit_requested)
            if args and command not in {"birthdays", "find"}:
                self.assertIn("Usage:", self.command(command).message)

    def test_read_commands_exit_flags_and_birthday_window(self):
        for command in ("hello", "help", "all", "notes", "birthdays"):
            result = self.command(command)
            self.assertTrue(result.message)
            self.assertFalse(result.changed)
        for command in ("exit", "close"):
            self.assertTrue(self.command(command).exit_requested)
        self.assertEqual(self.command("").message, "")
        with patch.object(self.book, "get_upcoming_birthdays", return_value=[
            {"name": "Alice", "birthday_date": "2026-10-24"},
        ]) as upcoming:
            self.assertIn("24.10.2026: Alice",
                          self.command("birthdays 14").message)
            upcoming.assert_called_once_with(14)


class LoopTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.filename = Path(temporary.name) / "data.json"

    def run_app(self, commands):
        output, errors = io.StringIO(), io.StringIO()
        with patch("builtins.input", side_effect=commands):
            with redirect_stdout(output), redirect_stderr(errors):
                code = assistant.main(["--data-file", str(self.filename)])
        return code, output.getvalue(), errors.getvalue()

    def test_bad_input_recovers_and_saved_data_survives(self):
        code, output, errors = self.run_app([
            "add Alice 123", 'note-add "unclosed', "",
            "add Alice 0501234567", "exit extra", "phone Alice", "exit",
        ])
        self.assertEqual(code, 0, errors)
        self.assertEqual(errors, "")
        self.assertIn("0501234567", output)
        self.assertIn("Unclosed quote", output)
        self.assertEqual(len(storage.load_data(self.filename)[0]), 1)

    def test_failed_save_keeps_old_live_state_and_file(self):
        self.run_app(["add Alice 0501234567", 'note-add "Keep"', "exit"])
        before = self.filename.read_bytes()
        with patch("personal_assistant.assistant.save_data",
                   side_effect=StorageError("disk full")):
            code, output, errors = self.run_app([
                "rename Alice Bob", "set-email Alice a@b.co",
                "delete Alice", "yes", "note-edit 1 changed",
                "note-delete 1", "yes", "tag-add 1 work",
                "add Bob 0991234567", 'note-add "Unsaved"',
                "all", "notes", "exit",
            ])
        self.assertEqual(code, 0, errors)
        self.assertIn("Name: Alice", output)
        self.assertIn("1: Keep", output)
        self.assertIn("disk full", output)
        self.assertNotIn("Contact added.", output)
        self.assertNotIn("Note added:", output)
        self.assertEqual(self.filename.read_bytes(), before)

    def test_cancel_and_confirm_deletions(self):
        code, output, errors = self.run_app([
            "add Alice 0501234567", "delete Alice", "no", "all",
            "delete Alice", "maybe", "all", "delete Alice", "yes",
            'note-add "Read"', "note-delete 1", "yes", "exit",
        ])
        self.assertEqual(code, 0, errors)
        self.assertIn("Cancelled", output)
        book, notes = storage.load_data(self.filename)
        self.assertEqual((len(book), len(notes)), (0, 0))

    def test_interrupts_cancel_confirmation_but_exit_at_prompt(self):
        for exception in (EOFError, KeyboardInterrupt):
            with self.subTest(exception=exception):
                self.run_app(["add Alice 0501234567", "exit"])
                code, output, errors = self.run_app([
                    "delete Alice", exception(), "all", exception(),
                ])
                self.assertEqual(code, 0, errors)
                self.assertIn("Cancelled", output)
                self.assertIn("Good bye", output)
                self.assertEqual(len(storage.load_data(self.filename)[0]), 1)

    def test_reads_do_not_save(self):
        with patch("personal_assistant.assistant.save_data") as save:
            self.run_app(["help", "", "all", "notes", "exit"])
        save.assert_not_called()

    def test_corrupt_startup_never_prompts_or_overwrites(self):
        self.filename.write_bytes(b"broken")
        with patch("personal_assistant.assistant.save_data") as save:
            code, output, errors = self.run_app([])
        self.assertEqual(code, 1)
        self.assertIn("Could not load", errors)
        self.assertNotIn("Welcome", output)
        self.assertEqual(self.filename.read_bytes(), b"broken")
        save.assert_not_called()

    def test_programming_bug_is_fatal_and_not_saved(self):
        with patch("personal_assistant.assistant.handle_command",
                   side_effect=TypeError("unexpected")):
            with patch("personal_assistant.assistant.save_data") as save:
                code, _, errors = self.run_app(["hello"])
        self.assertEqual(code, 1)
        self.assertIn("Unexpected error", errors)
        save.assert_not_called()

    def test_output_failure_after_commit_never_repeats_save(self):
        real_print = print

        def fail_on_success(*args, **kwargs):
            if args and args[0] == "Contact added.":
                raise OSError("output disconnected")
            return real_print(*args, **kwargs)

        with patch("builtins.print", side_effect=fail_on_success):
            with patch("personal_assistant.assistant.save_data",
                       wraps=storage.save_data) as save:
                code, _, _ = self.run_app(["add Alice 0501234567"])
        self.assertEqual(code, 1)
        self.assertEqual(save.call_count, 1)
        self.assertEqual(len(storage.load_data(self.filename)[0]), 1)


if __name__ == "__main__":
    unittest.main()
