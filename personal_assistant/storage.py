import json
import os
import tempfile
from pathlib import Path

from personal_assistant.address_book import AddressBook, Record
from personal_assistant.errors import InputError, StorageError
from personal_assistant.notes import Note, Notebook


def default_file():
    return Path.home() / ".personal_assistant" / "data.json"


def _check_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise InputError("The save file has missing or unexpected fields.")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("The save file contains duplicate keys.")
        result[key] = value
    return result


def _invalid_constant(value):
    raise InputError("The save file contains an invalid number.")


def from_data(data):
    """Validate the whole document before admitting any of it."""
    _check_keys(data, ("version", "contacts", "notes", "next_note_id"))
    if type(data["version"]) is not int or data["version"] != 1:
        raise InputError("Unsupported save file version.")
    if not isinstance(data["contacts"], list):
        raise InputError("Saved contacts must be a list.")
    if not isinstance(data["notes"], list):
        raise InputError("Saved notes must be a list.")
    book, notebook = AddressBook(), Notebook()
    for item in data["contacts"]:
        _check_keys(item, ("name", "phones", "address", "email", "birthday"))
        record = Record(item["name"])
        if not isinstance(item["phones"], list):
            raise InputError("Saved phone numbers must be a list.")
        for phone in item["phones"]:
            record.add_phone(phone)
        if item["address"] is not None:
            record.set_address(item["address"])
        if item["email"] is not None:
            record.set_email(item["email"])
        if item["birthday"] is not None:
            record.add_birthday(item["birthday"])
        book.add_record(record)
    for item in data["notes"]:
        _check_keys(item, ("id", "text", "tags"))
        note = Note(item["id"], item["text"])
        if note.id in notebook:
            raise InputError("The save file contains duplicate note IDs.")
        if not isinstance(item["tags"], list):
            raise InputError("Saved tags must be a list.")
        for tag in item["tags"]:
            note.add_tag(tag)
        notebook.data[note.id] = note
    next_id = data["next_note_id"]
    if type(next_id) is not int or next_id <= max(notebook, default=0):
        raise InputError("Invalid next note ID.")
    notebook.next_id = next_id
    return book, notebook


def to_data(book, notebook):
    if not isinstance(book, AddressBook) or not isinstance(notebook, Notebook):
        raise InputError("Expected an address book and notebook.")
    contacts = []
    for key, record in book.items():
        if key != record.name.value:
            raise InputError("A contact name does not match its stored key.")
        contacts.append({
            "name": record.name.value,
            "phones": [phone.value for phone in record.phones],
            "address": record.address.value if record.address else None,
            "email": record.email.value if record.email else None,
            "birthday": str(record.birthday) if record.birthday else None,
        })
    notes = []
    for key, note in notebook.items():
        if key != note.id:
            raise InputError("A note ID does not match its stored key.")
        notes.append({"id": note.id, "text": note.text, "tags": note.tags[:]})
    data = {"version": 1, "contacts": contacts, "notes": notes,
            "next_note_id": notebook.next_id}
    from_data(data)
    return data


def load_data(filename=None):
    path = default_file() if filename is None else Path(filename)
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file, object_pairs_hook=_unique_keys,
                             parse_constant=_invalid_constant)
        return from_data(data)
    except FileNotFoundError:
        return AddressBook(), Notebook()
    except (OSError, ValueError, TypeError, RecursionError) as error:
        raise StorageError(f"Could not load {path}: {error}") from error


def save_data(book, notebook, filename=None):
    """Replace the last save only after the new file has been completed."""
    path = default_file() if filename is None else Path(filename)
    temporary_path = None
    try:
        data = to_data(book, notebook)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(data, file, ensure_ascii=False, indent=2,
                      allow_nan=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except (OSError, ValueError, TypeError, RecursionError) as error:
        raise StorageError(f"Could not save {path}: {error}") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                # A cleanup failure must not hide the original save error.
                pass
