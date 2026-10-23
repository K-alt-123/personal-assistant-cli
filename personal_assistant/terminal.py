"""Small terminal presentation helpers; domain objects stay plain text."""

import os
import sys

from colorama import Fore, Style


BANNER = r"""
  ____   _
 |  _ \ / \       PERSONAL ASSISTANT
 | |_) / _ \      Contacts. Notes. Birthdays.
 |  __/ ___ \
 |_| /_/   \_\
"""

HELP_GROUPS = {
    "CONTACTS": (
        "add", "all", "show", "phone", "change", "remove-phone", "rename",
        "set-address", "set-email", "clear-field", "find", "delete",
    ),
    "BIRTHDAYS": ("add-birthday", "show-birthday", "birthdays"),
    "NOTES & TAGS": (
        "note-add", "notes", "note-show", "note-find", "note-edit",
        "note-delete", "tag-add", "tag-remove", "notes-tag", "notes-sort-tags",
    ),
    "SESSION": ("hello", "help", "exit", "close"),
}


def format_help(commands):
    sections = []
    for heading, names in HELP_GROUPS.items():
        lines = [heading] + ["  " + commands[name][0] for name in names]
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


class Terminal:
    def __init__(self, no_color=False):
        self.interactive = sys.stdout.isatty()
        self.color = (
            self.interactive
            and not no_color
            and not os.environ.get("NO_COLOR")
            and os.environ.get("TERM") != "dumb"
        )

    def paint(self, text, kind="info"):
        colors = {
            "heading": Style.BRIGHT + Fore.CYAN,
            "prompt": Style.BRIGHT + Fore.CYAN,
            "success": Fore.GREEN,
            "error": Fore.RED,
            "warning": Fore.YELLOW,
            "muted": Fore.LIGHTBLACK_EX,
        }
        if not self.color or kind not in colors:
            return text
        return colors[kind] + text + Style.RESET_ALL

    def write(self, text, kind="info"):
        print(self.paint(str(text), kind))

    def welcome(self):
        if self.interactive:
            self.write(BANNER, "heading")
            self.write("  Type help for commands. Changes save automatically.",
                       "muted")
            print()
        else:
            print("Welcome to Personal Assistant. Type help for commands.")

    def prompt(self):
        if self.interactive:
            return self.paint("assistant", "prompt") + " > "
        return "> "

    def help(self, text):
        for line in text.splitlines():
            if line in HELP_GROUPS:
                self.write(line, "heading")
            elif line.startswith("  "):
                command, separator, arguments = line[2:].partition(" ")
                print("  " + self.paint(command, "heading")
                      + separator + arguments)
            else:
                self.write(line)
