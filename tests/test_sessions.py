import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class SessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.filename = self.directory / "saved" / "data.json"
        self.other_directory = self.directory / "elsewhere"
        self.other_directory.mkdir()

    def session(self, commands, *, cwd=None, env=None, default_path=False):
        arguments = [sys.executable, "-m", "personal_assistant"]
        if not default_path:
            arguments += ["--data-file", str(self.filename)]
        return subprocess.run(
            arguments, input=commands, text=True, encoding="utf-8",
            capture_output=True, timeout=10,
            cwd=cwd or self.directory, env=env,
        )

    def test_restart_elsewhere_preserves_all_fields_and_tags(self):
        first = self.session('\n'.join([
            'add "Олена Коваль" 0501234567',
            'add "Олена Коваль" 0123456789',
            'set-email "Олена Коваль" Olena@Example.org',
            'set-address "Олена Коваль" "Київ, Липова 4"',
            'add-birthday "Олена Коваль" 29.02.2000',
            'note-add "Підготувати захист"', 'tag-add 1 "Навчання"',
            'exit', '',
        ]))
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.session('all\nnotes\nexit\n', cwd=self.other_directory)
        self.assertEqual(second.returncode, 0, second.stderr)
        for value in ("Олена Коваль", "0501234567", "0123456789",
                      "Olena@example.org", "Київ, Липова 4", "29.02.2000",
                      "Підготувати захист", "навчання"):
            self.assertIn(value, second.stdout)

    def test_invalid_edits_then_valid_command_and_restart(self):
        first = self.session(
            'add Alice 0501234567\nset-email Alice wrong\n'
            'change Alice 0501234567 123\nadd-birthday Alice 31.02.2000\n'
            'note-add "Keep"\nnote-edit 1 ""\ntag-add 1 work\nexit\n'
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.session('show Alice\nnote-show 1\nclose\n')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("0501234567", second.stdout)
        self.assertIn("email: not set; birthday: not set", second.stdout)
        self.assertIn("1: Keep [tags: work]", second.stdout)

    def test_confirmed_deletion_and_monotonic_ids_after_restart(self):
        first = self.session(
            'add Alice 0501234567\nnote-add "First"\n'
            'delete Alice\nno\nnote-delete 1\nyes\nexit\n'
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.session('note-add "Second"\nall\nnotes\nexit\n')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("Name: Alice", second.stdout)
        self.assertIn("2: Second", second.stdout)
        self.assertNotIn("1: First", second.stdout)

    def test_default_file_uses_home_instead_of_working_directory(self):
        home = self.directory / "home"
        home.mkdir()
        environment = os.environ.copy()
        environment.update(HOME=str(home), USERPROFILE=str(home))
        first = self.session('add Alice 0501234567\nexit\n',
                             env=environment, default_path=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.session('phone Alice\nexit\n', env=environment,
                              default_path=True, cwd=self.other_directory)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("0501234567", second.stdout)
        self.assertTrue((home / ".personal_assistant" / "data.json").is_file())
        self.assertFalse((self.other_directory / "data.json").exists())

    def test_unicode_io_even_when_inherited_encoding_is_ascii(self):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "ascii"
        result = self.session('note-add "Привіт 👋"\nnotes\nexit\n',
                              env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Привіт 👋", result.stdout)
        data = json.loads(self.filename.read_text(encoding="utf-8"))
        self.assertEqual(data["notes"][0]["text"], "Привіт 👋")

    def test_eof_exits_cleanly_without_creating_a_file(self):
        result = self.session("")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Good bye", result.stdout)
        self.assertFalse(self.filename.exists())


if __name__ == "__main__":
    unittest.main()
