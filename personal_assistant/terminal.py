"""Small terminal presentation helpers; domain objects stay plain text."""

import os
import shutil
import sys
import textwrap
import unicodedata

from colorama import Fore, Style


# Original, fixed ASCII lettering. No font engine is needed for two initials.
LOGO_P = (
    r" .--------.", r" | .----.  \ ", r" | |    |  |",
    r" | '----' /", r" | .-----'", r" | |", r" |_|",
)
LOGO_A = (
    r"      .----.", r"     / .--. \ ", r"    / /    \ \ ",
    r"   / '------' \ ", r"  / .------.  \ ", r" / /        \  \ ",
    r"/_/          \__\ ",
)
COMPACT_LOGO = (
    r"  ____    _", r" |  _ \  / \ ", r" |  __/ / _ \ ",
    r" |_|   /_/ \_\ ",
)

ICONS = {
    "CONTACTS": (" .----.", " |o ==|", " '----'"),
    "NOTES": (" .---/|", " | ===|", " |___/|"),
    "BIRTHDAYS": (" i i i ", " |~~~| ", " |___| "),
    "SEARCH": (" .--.  ", " (  )  ", " '--'\\ "),
    "DELETE": (" .===. ", " | | | ", " '---' "),
    "HELP": (" .---. ", " | ? | ", " '---' "),
    "HOME": (" .---. ", " | PA| ", " '---' "),
    "ERROR": ("  /!\\  ", " / ! \\ ", " '---' "),
}

# Status, face and colour always describe an observed command outcome.
REACTIONS = {
    "READY": ("(o_o)", "heading"),
    "VIEW": ("(o_o)", "heading"),
    "SAVED": ("(^_^)", "success"),
    "ERROR": ("(!_!)", "error"),
    "NOT SAVED": ("(!_!)", "error"),
    "CONFIRM": ("(o_O)", "warning"),
    "CANCELLED": ("(-_-)", "warning"),
    "BYE": ("(u_u)", "muted"),
}

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


def safe_text(text, *, multiline=False):
    """Escape external controls; allow line breaks only when requested."""
    return "".join(
        repr(character)[1:-1]
        if unicodedata.category(character) in {"Cc", "Cf", "Cs"}
        and not (multiline and character == "\n") else character
        for character in str(text)
    )


class Terminal:
    def __init__(self, no_color=False, plain=False):
        self.interactive = (
            sys.stdout.isatty() and not plain
            and os.environ.get("TERM") != "dumb"
        )
        self.color = (
            self.interactive
            and not no_color
            and not os.environ.get("NO_COLOR")
            and os.environ.get("TERM") != "dumb"
        )
        self.status = "READY"
        self.section = "HOME"

    @property
    def width(self):
        # Leave the last column free; recheck on every new render for resizes.
        return max(1, min(88, shutil.get_terminal_size().columns - 1))

    def paint(self, text, kind="info"):
        colors = {
            "heading": Style.BRIGHT + Fore.CYAN,
            "prompt": Style.BRIGHT + Fore.CYAN,
            "success": Fore.GREEN,
            "error": Fore.RED,
            "warning": Fore.YELLOW,
            "muted": Fore.LIGHTBLACK_EX,
            "accent": Style.BRIGHT + Fore.BLUE,
            "notes": Style.BRIGHT + Fore.MAGENTA,
        }
        if not self.color or kind not in colors:
            return text
        return colors[kind] + text + Style.RESET_ALL

    def write(self, text, kind="info"):
        print(self.paint(safe_text(text, multiline=kind != "error"), kind))

    def welcome(self):
        if not self.interactive:
            print("Welcome to Personal Assistant. Type help for commands.")
            return
        width = self.width
        print()
        self.rule("PA / YOUR PERSONAL WORKSPACE", width)
        if width >= 72:
            captions = (
                "", "PERSONAL ASSISTANT", "CONTACTS / NOTES / BIRTHDAYS",
                "", "Less noise. More room to think.",
                "Your data, one command away.", "",
            )
            for p_row, a_row, caption in zip(LOGO_P, LOGO_A, captions):
                print("  " + self.paint(p_row.ljust(15), "heading")
                      + self.paint(a_row.ljust(20), "accent")
                      + "  " + caption)
        else:
            if width >= 36:
                for row in COMPACT_LOGO:
                    self.write(row, "heading")
            self.label("PA / PERSONAL ASSISTANT", "heading", width)
        print()
        self.label("[+] CONTACTS   [#] NOTES   [*] BIRTHDAYS",
                   "heading", width)
        self.label("Try: all | notes | birthdays | help", "muted", width)
        self.label("Changes save automatically. Type exit to leave.",
                   "muted", width)
        self.rule("READY WHEN YOU ARE", width)

    def rule(self, label, width):
        prefix = "-- " + label + " "
        self.write(prefix + "-" * (width - len(prefix))
                   if len(prefix) <= width else "-" * width, "muted")

    def label(self, text, kind, width):
        # Only wrap our ASCII labels. User content is printed intact below.
        for line in textwrap.wrap(text, width=width):
            self.write(line, kind)

    def prompt(self, contacts=0, notes=0):
        if self.interactive:
            face, kind = REACTIONS[self.status]
            summary = (f"PA {face} {self.section} / {self.status}"
                       f"  |  contacts: {contacts}  notes: {notes}")
            lines = textwrap.wrap(summary, width=self.width)
            status = "\n".join(self.paint(line, kind) for line in lines)
            name = "assistant" if self.width >= 14 else "pa"
            return "\n" + status + "\n" + self.paint(name, "prompt") + " > "
        return "> "

    def feedback(self, command, message, status="VIEW"):
        self.status = status
        self.section = command_section(command)
        face, kind = REACTIONS[status]
        if self.interactive:
            width = self.width
            known = any(command in names for names in HELP_GROUPS.values())
            title = self.section + (" / " + command if known else "")
            if width >= 36:
                icon = "ERROR" if kind == "error" else self.section
                captions = (title, f"{status}  {face}", "-" * (width - 11))
                for row, caption in zip(ICONS[icon], captions):
                    print(self.paint(row.ljust(9), kind)
                          + self.paint(caption, kind))
            else:
                self.label(title, kind, width)
                self.label(f"[{status}] {face}", kind, width)
        if command == "help" and status == "VIEW":
            self.help(message)
        elif message:
            self.write(message, kind if status != "VIEW" else "info")

    def help(self, text):
        for line in text.splitlines():
            if line in HELP_GROUPS:
                if self.interactive:
                    self.rule(line, self.width)
                self.write(line, "notes" if line == "NOTES & TAGS"
                           else "heading")
            elif line.startswith("  "):
                command, separator, arguments = line[2:].partition(" ")
                print("  " + self.paint(command, "heading")
                      + separator + arguments)
            else:
                self.write(line)


def command_section(command):
    if command in {"find", "note-find", "notes-tag"}:
        return "SEARCH"
    if command in {"delete", "note-delete"}:
        return "DELETE"
    if command == "help":
        return "HELP"
    for heading, names in HELP_GROUPS.items():
        if command in names and heading != "SESSION":
            return "NOTES" if heading == "NOTES & TAGS" else heading
    return "HOME"
