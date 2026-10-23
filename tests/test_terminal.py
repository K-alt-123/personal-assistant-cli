import io
import os
from pathlib import Path
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from personal_assistant import assistant
from personal_assistant.errors import StorageError


def without_colour(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TerminalBuffer(io.StringIO):
    def isatty(self):
        return True


class TerminalPresentationTests(unittest.TestCase):
    def run_app(self, commands, *, tty=True, environment=None, options=None):
        output = TerminalBuffer() if tty else io.StringIO()
        errors = io.StringIO()
        settings = {"TERM": "xterm-256color", "NO_COLOR": "",
                    "COLUMNS": "95"}
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

    def test_counts_follow_commits_and_recover_from_errors(self):
        code, output, errors, prompt = self.run_app([
            "add Alice 0501234567", 'note-add "Read Python"',
            "add Bob 123", "all", "exit",
        ])
        self.assertEqual(code, 0, errors)
        prompts = [without_colour(call.args[0])
                   for call in prompt.call_args_list]
        for index, contacts, notes, status in (
            (0, 0, 0, "READY"), (1, 1, 0, "SAVED"),
            (2, 1, 1, "SAVED"), (3, 1, 1, "ERROR"),
            (4, 1, 1, "VIEW"),
        ):
            with self.subTest(index=index):
                self.assertIn(f"contacts: {contacts}", prompts[index])
                self.assertIn(f"notes: {notes}", prompts[index])
                self.assertIn(status, prompts[index])
        self.assertIn("(^_^)", prompts[1])
        self.assertIn("(!_!)", prompts[3])

    def test_save_failure_has_no_success_reaction_or_phantom_count(self):
        with patch.object(assistant, "save_data",
                          side_effect=StorageError("disk full")):
            code, output, errors, prompt = self.run_app([
                "add Alice 0501234567", "all", "exit",
            ])
        self.assertEqual(code, 0, errors)
        self.assertNotIn("Contact added.", output)
        self.assertNotIn("(^_^)", output)
        failed_prompt = without_colour(prompt.call_args_list[1].args[0])
        self.assertIn("NOT SAVED", failed_prompt)
        self.assertIn("contacts: 0", failed_prompt)
        self.assertIn("No contacts found.", output)

    def test_command_families_have_distinct_illustrations(self):
        captures = []
        for command, label in (("all", "CONTACTS"), ("notes", "NOTES"),
                               ("birthdays", "BIRTHDAYS"),
                               ("find Alice", "SEARCH")):
            code, output, errors, _ = self.run_app([command, "exit"])
            self.assertEqual(code, 0, errors)
            plain = without_colour(output)
            self.assertIn(f"{label} / {command.split()[0]}", plain)
            captures.append(plain.split(f"{label} /")[0].splitlines()[-1])
        self.assertEqual(len(set(captures)), 4)

    def test_cancelled_and_confirmed_delete_update_status_and_count(self):
        code, output, errors, prompt = self.run_app([
            "add Alice 0501234567", "delete Alice", "no",
            "delete Alice", "yes", "exit",
        ])
        self.assertEqual(code, 0, errors)
        prompts = [without_colour(call.args[0])
                   for call in prompt.call_args_list]
        self.assertIn("CONFIRM", without_colour(output))
        self.assertIn("CANCELLED", prompts[3])
        self.assertIn("contacts: 1", prompts[3])
        self.assertIn("SAVED", prompts[5])
        self.assertIn("contacts: 0", prompts[5])

    def test_quote_error_and_blank_input_keep_truthful_status(self):
        code, output, errors, prompt = self.run_app([
            'note-add "unclosed', "", "hello", "exit",
        ])
        self.assertEqual(code, 0, errors)
        prompts = [without_colour(call.args[0])
                   for call in prompt.call_args_list]
        self.assertIn("ERROR", prompts[1])
        self.assertEqual(prompts[1], prompts[2])
        self.assertIn("VIEW", prompts[3])

    def test_decoration_and_prompts_fit_small_and_large_terminals(self):
        for columns in (20, 35, 36, 71, 72, 95, 160):
            with self.subTest(columns=columns):
                code, output, errors, prompt = self.run_app(
                    ["hello", "exit"], environment={"COLUMNS": str(columns)},
                )
                self.assertEqual(code, 0, errors)
                lines = without_colour(output).splitlines()
                for call in prompt.call_args_list:
                    lines += without_colour(call.args[0]).splitlines()
                for line in lines:
                    self.assertLessEqual(len(line), columns - 1, line)

    def test_width_is_rechecked_after_resize(self):
        from personal_assistant.terminal import Terminal

        output = TerminalBuffer()
        settings = {"COLUMNS": "95", "TERM": "xterm-256color"}
        with redirect_stdout(output), patch.dict(os.environ, settings):
            terminal = Terminal(no_color=True)
            wide = terminal.prompt(contacts=123, notes=45)
            with patch.dict(os.environ, {"COLUMNS": "24"}):
                narrow = terminal.prompt(contacts=123, notes=45)
        self.assertGreater(max(map(len, wide.splitlines())), 23)
        self.assertTrue(all(len(line) <= 23 for line in narrow.splitlines()))
        self.assertIn("contacts: 123", narrow)

    def test_plain_and_dumb_terminal_have_no_decorations(self):
        for options, environment in (
            (["--plain"], {}), ([], {"TERM": "dumb"}),
        ):
            with self.subTest(options=options, environment=environment):
                code, output, errors, prompt = self.run_app(
                    ["hello", "exit"], options=options,
                    environment=environment,
                )
                self.assertEqual(code, 0, errors)
                self.assertNotIn("\x1b", output + errors)
                self.assertNotIn("|_|", output)
                self.assertNotIn("(o_o)", output)
                self.assertEqual(prompt.call_args_list[0].args[0], "> ")

    def test_reactions_do_not_move_cursor_erase_history_or_drop_unicode(self):
        code, output, errors, prompt = self.run_app([
            'note-add "Привіт 界 é 👋"', "notes", "exit",
        ])
        self.assertEqual(code, 0, errors)
        self.assertIn("Привіт 界 é 👋", output)
        visible = output + "".join(call.args[0]
                                   for call in prompt.call_args_list)
        self.assertNotIn("\x1b", without_colour(visible))
        self.assertNotIn("\r", visible)
        self.assertNotIn("\a", visible)

    def test_external_errors_cannot_emit_terminal_controls(self):
        unsafe = "bad\nFAKE SAVED\x1b[2J\x1b]2;title\a\r\x9b2J\u202e\ud800"
        for tty in (True, False):
            for operation, exception in (
                ("load_data", StorageError(unsafe)),
                ("save_data", StorageError(unsafe)),
                ("handle_command", RuntimeError(unsafe)),
            ):
                with self.subTest(tty=tty, operation=operation):
                    with patch.object(assistant, operation,
                                      side_effect=exception):
                        code, output, errors, _ = self.run_app(
                            ["add Alice 0501234567", "exit"], tty=tty,
                        )
                    self.assertEqual(code, 0 if operation == "save_data"
                                     else 1)
                    plain = without_colour(output + errors)
                    for control in ("\x1b", "\a", "\r", "\x9b",
                                    "\u202e", "\ud800"):
                        self.assertNotIn(control, plain)
                    self.assertIn(r"\x1b[2J", plain)
                    self.assertNotIn("bad\nFAKE SAVED", plain)
                    self.assertIn(r"bad\nFAKE SAVED", plain)

    @unittest.skipIf(os.name == "nt", "Windows rejects newline filenames")
    def test_newline_in_a_real_path_stays_on_one_diagnostic_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "denied\nFAKE SAVED"
            path.mkdir()
            errors = io.StringIO()
            with redirect_stderr(errors), redirect_stdout(io.StringIO()):
                code = assistant.main(["--data-file", str(path)])
            self.assertEqual(code, 1)
            self.assertTrue(path.is_dir())
            self.assertEqual(len(errors.getvalue().splitlines()), 1)
            self.assertIn(r"denied\nFAKE SAVED", errors.getvalue())

    def test_unknown_command_is_not_echoed_into_a_status_label(self):
        unsafe = "\x1b[2J" + "a" * 1000
        code, output, errors, prompt = self.run_app([unsafe, "exit"])
        self.assertEqual(code, 0, errors)
        self.assertIn("Unknown command", output)
        self.assertNotIn(unsafe, output)
        next_prompt = without_colour(prompt.call_args_list[1].args[0])
        self.assertIn("ERROR", next_prompt)


if __name__ == "__main__":
    unittest.main()
