import argparse
from copy import deepcopy
from datetime import date
import shlex
import sys
from functools import wraps
from typing import NamedTuple

from personal_assistant.address_book import Record, format_birthday
from personal_assistant.errors import InputError, NotFoundError, StorageError
from personal_assistant.storage import load_data, save_data


# Syntax, minimum arguments, maximum arguments, and whether data changes.
COMMANDS = {
    "hello": ("hello", 0, 0, False),
    "help": ("help", 0, 0, False),
    "exit": ("exit", 0, 0, False),
    "close": ("close", 0, 0, False),
    "add": ('add "name" phone', 2, 2, True),
    "all": ("all", 0, 0, False),
    "show": ('show "name"', 1, 1, False),
    "phone": ('phone "name"', 1, 1, False),
    "change": ('change "name" old-phone new-phone', 3, 3, True),
    "remove-phone": ('remove-phone "name" phone', 2, 2, True),
    "rename": ('rename "old name" "new name"', 2, 2, True),
    "set-address": ('set-address "name" "address"', 2, 2, True),
    "set-email": ('set-email "name" email', 2, 2, True),
    "add-birthday": ('add-birthday "name" DD.MM.YYYY', 2, 2, True),
    "show-birthday": ('show-birthday "name"', 1, 1, False),
    "clear-field": ('clear-field "name" address/email/birthday', 2, 2, True),
    "find": ('find "query" [name/phone/email/address]', 1, 2, False),
    "delete": ('delete "name"', 1, 1, True),
    "birthdays": ("birthdays [days]", 0, 1, False),
    "note-add": ('note-add "text"', 1, 1, True),
    "notes": ("notes", 0, 0, False),
    "note-show": ("note-show id", 1, 1, False),
    "note-find": ('note-find "query"', 1, 1, False),
    "note-edit": ('note-edit id "text"', 2, 2, True),
    "note-delete": ("note-delete id", 1, 1, True),
    "tag-add": ('tag-add id "tag"', 2, 2, True),
    "tag-remove": ('tag-remove id "tag"', 2, 2, True),
    "notes-tag": ('notes-tag "tag"', 1, 1, False),
    "notes-sort-tags": ("notes-sort-tags", 0, 0, False),
}


class Result(NamedTuple):
    message: str
    changed: bool = False
    exit_requested: bool = False


def input_error(func):
    """Keep expected input errors inside the command loop."""
    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except InputError as error:
            return Result(str(error))
    return inner


def parse_input(user_input):
    if not isinstance(user_input, str):
        raise InputError("Enter a text command.")
    try:
        parts = shlex.split(user_input)
    except ValueError as error:
        raise InputError("Unclosed quote. Type help for examples.") from error
    if not parts:
        return "", []
    return parts[0].casefold(), parts[1:]


def positive_integer(value, label):
    if not value.isascii() or not value.isdecimal():
        raise InputError(f"{label} must be a positive integer.")
    try:
        number = int(value)
    except ValueError as error:
        raise InputError(f"{label} is too large.") from error
    if number <= 0:
        raise InputError(f"{label} must be a positive integer.")
    return number


def contact(book, name):
    record = book.find(name)
    if record is None:
        raise NotFoundError("Contact was not found.")
    return record


def display_items(items, empty_message):
    return "\n".join(str(item) for item in items) or empty_message


def handle_contact_command(command, args, book):
    if command == "add":
        record = book.find(args[0])
        if record is None:
            record = Record(args[0])
            record.add_phone(args[1])
            book.add_record(record)
            return "Contact added."
        record.add_phone(args[1])
        return "Phone added."
    if command == "all":
        records = sorted(book.values(), key=lambda r: (
            r.name.value.casefold(), r.name.value,
        ))
        return display_items(records, "No contacts found.")
    if command == "find":
        field = args[1] if len(args) == 2 else None
        return display_items(book.search(args[0], field), "No contacts found.")
    if command == "birthdays":
        days = positive_integer(args[0], "Days") if args else 7
        upcoming = book.get_upcoming_birthdays(days)
        lines = [
            f"{format_birthday(date.fromisoformat(item['birthday_date']))}: "
            f"{item['name']}" for item in upcoming
        ]
        return "\n".join(lines) or "No upcoming birthdays."

    record = contact(book, args[0])
    if command == "show":
        return str(record)
    if command == "phone":
        return ", ".join(str(p) for p in record.phones) or "No phones set."
    if command == "show-birthday":
        return str(record.birthday) if record.birthday else "Birthday not set."
    if command == "change":
        record.edit_phone(args[1], args[2])
        return "Phone changed."
    if command == "remove-phone":
        record.remove_phone(args[1])
        return "Phone removed."
    if command == "rename":
        book.rename(args[0], args[1])
        return "Contact renamed."
    if command == "set-address":
        record.set_address(args[1])
        return "Address saved."
    if command == "set-email":
        record.set_email(args[1])
        return "Email saved."
    if command == "add-birthday":
        record.add_birthday(args[1])
        return "Birthday saved."
    if command == "clear-field":
        record.clear_field(args[1])
        return "Field cleared."
    if command == "delete":
        book.delete(args[0])
        return "Contact deleted."
    raise RuntimeError(f"Missing contact handler: {command}")


def handle_note_command(command, args, notebook):
    if command == "note-add":
        return f"Note added: {notebook.add(args[0]).id}."
    if command == "notes":
        return display_items(notebook.all_items(), "No notes found.")
    if command == "note-find":
        return display_items(notebook.search(args[0]), "No notes found.")
    if command == "notes-tag":
        return display_items(notebook.by_tag(args[0]), "No notes found.")
    if command == "notes-sort-tags":
        return display_items(notebook.sorted_by_tags(), "No notes found.")

    note_id = positive_integer(args[0], "Note ID")
    note = notebook.find(note_id)
    if note is None:
        raise NotFoundError("Note was not found.")
    if command == "note-show":
        return str(note)
    if command == "note-edit":
        notebook.edit(note_id, args[1])
        return "Note updated."
    if command == "note-delete":
        notebook.delete(note_id)
        return "Note deleted."
    if command == "tag-add":
        note.add_tag(args[1])
        return "Tag added."
    if command == "tag-remove":
        note.remove_tag(args[1])
        return "Tag removed."
    raise RuntimeError(f"Missing note handler: {command}")


@input_error
def handle_command(command, args, book, notebook):
    if not command:
        return Result("")
    if command not in COMMANDS:
        raise InputError("Unknown command. Type help for the command list.")
    usage, minimum, maximum, changed = COMMANDS[command]
    if not minimum <= len(args) <= maximum:
        raise InputError(f"Usage: {usage}")
    if command in {"exit", "close"}:
        return Result("Good bye!", exit_requested=True)
    if command == "hello":
        return Result("How can I help you?")
    if command == "help":
        syntax = "\n".join(item[0] for item in COMMANDS.values())
        return Result(
            syntax + '\nUse double quotes for text containing spaces.\n'
            "Phones: 10 digits, e.g. 0501234567. Email: name@example.org.\n"
            "Birthdays: next 1–366 days including today; default 7.\n"
            "Deletion asks for confirmation. Changes save automatically."
        )
    if command.startswith(("note", "tag-")):
        message = handle_note_command(command, args, notebook)
    else:
        message = handle_contact_command(command, args, book)
    return Result(message, changed=changed)


def confirm_deletion(command, args, book, notebook):
    if command == "delete":
        print(contact(book, args[0]))
    else:
        print(notebook.find(positive_integer(args[0], "Note ID")))
    try:
        answer = input("Delete this item? [y/N]: ")
    except (EOFError, KeyboardInterrupt):
        answer = "no"
        print()
    if answer.strip().casefold() in {"yes", "y"}:
        return True
    print("Cancelled.")
    return False


def run_loop(book, notebook, filename):
    print("Welcome to Personal Assistant. Type help for commands.")
    while True:
        try:
            command, args = parse_input(input("> "))
        except (EOFError, KeyboardInterrupt):
            print("\nGood bye!")
            return 0
        except InputError as error:
            print(error)
            continue
        changes_data = COMMANDS.get(command, (None, 0, 0, False))[3]
        candidate = deepcopy((book, notebook)) if changes_data else (
            book, notebook,
        )
        result = handle_command(command, args, *candidate)
        if result.changed:
            if command in {"delete", "note-delete"}:
                if not confirm_deletion(command, args, book, notebook):
                    continue
            try:
                save_data(*candidate, filename)
            except StorageError as error:
                print(f"Change not saved: {error}")
                continue
            # Replacement succeeded. Publish once, before reporting success.
            book, notebook = candidate
        if result.message:
            print(result.message)
        if result.exit_requested:
            return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Contacts and notes.")
    parser.add_argument("--data-file", help="Use a different save file.")
    options = parser.parse_args(argv)
    # Piped input/output can inherit a non-Unicode encoding on Windows.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        book, notebook = load_data(options.data_file)
    except StorageError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        return run_loop(book, notebook, options.data_file)
    except Exception as error:
        print(f"Unexpected error ({type(error).__name__}): {error}",
              file=sys.stderr)
        return 1
