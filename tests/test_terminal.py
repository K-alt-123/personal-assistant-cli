import io
import os
from pathlib import Path
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from personal_assistant import assistant


class TerminalBuffer(io.StringIO):
    def isatty(self):
        return True


class TerminalPresentationTests(unittest.TestCase):
    def run_app(self, commands, *, tty=True, environment=None, options=None):
        output = TerminalBuffer() if tty else io.StringIO()
        errors = io.StringIO()
        settings = {"TERM": "xterm-256color", "NO_COLOR": ""}
        settings.update(environment or {})
        with tempfile.TemporaryDirectory() as directory:
            args = ["--data-file", str(Path(directory) / "data.json")]
            args += options or []
            with patch.dict(os.environ, settings):
                with patch("builtins.input", side_effect=commands) as prompt:
                    with redirect_stdout(output), redirect_stderr(errors):
                        code = assistant.main(args)
        return code, output.getvalue(), errors.getvalue(), prompt

    def test_interactive_banner_and_prompt_are_coloured(self):
        code, output, errors, prompt = self.run_app(["exit"])
        self.assertEqual(code, 0, errors)
        self.assertIn("PERSONAL ASSISTANT", output)
        self.assertIn("|_|", output)
        self.assertIn("\x1b[", output)
        self.assertIn("assistant", prompt.call_args_list[0].args[0])
        self.assertIn("\x1b[", prompt.call_args_list[0].args[0])

    def test_success_and_errors_have_different_reset_colours(self):
        code, output, errors, _ = self.run_app([
            "add Alice 123", "add Alice 0501234567", "exit",
        ])
        self.assertEqual(code, 0, errors)
        self.assertRegex(output, r"\x1b\[31mPhone must contain exactly "
                         r"10 digits\x1b\[0m")
        self.assertRegex(output, r"\x1b\[32mContact added\.\x1b\[0m")

    def test_help_groups_every_command_once(self):
        code, output, errors, _ = self.run_app(["help", "exit"])
        self.assertEqual(code, 0, errors)
        plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
        for heading in ("CONTACTS", "BIRTHDAYS", "NOTES & TAGS", "SESSION"):
            self.assertIn(heading, plain)
        listed = re.findall(r"^  ([a-z-]+)(?: |$)", plain, re.MULTILINE)
        self.assertCountEqual(listed, assistant.COMMANDS)

    def test_redirected_output_is_plain_and_has_no_banner(self):
        code, output, errors, prompt = self.run_app(
            ["help", "add Alice 123", "exit"], tty=False,
        )
        self.assertEqual(code, 0, errors)
        self.assertNotIn("\x1b", output + errors)
        self.assertNotIn("|_|", output)
        self.assertEqual(prompt.call_args_list[0].args[0], "> ")

    def test_no_color_flag_environment_and_dumb_terminal(self):
        cases = (
            ({"NO_COLOR": "1"}, []),
            ({"TERM": "dumb"}, []),
            ({}, ["--no-color"]),
        )
        for environment, options in cases:
            with self.subTest(environment=environment, options=options):
                code, output, errors, prompt = self.run_app(
                    ["help", "exit"], environment=environment,
                    options=options,
                )
                self.assertEqual(code, 0, errors)
                self.assertNotIn("\x1b", output + errors)
                self.assertNotIn("\x1b", prompt.call_args_list[0].args[0])

    def test_confirmation_and_cancel_are_distinct_from_success(self):
        code, output, errors, prompt = self.run_app([
            "add Alice 0501234567", "delete Alice", "no", "exit",
        ])
        self.assertEqual(code, 0, errors)
        question = prompt.call_args_list[2].args[0]
        self.assertIn("\x1b[33m", question)
        self.assertIn("\x1b[33mCancelled.\x1b[0m", output)


if __name__ == "__main__":
    unittest.main()
