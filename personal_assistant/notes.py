"""Validated note models and their in-memory collection."""

import unicodedata
from collections import UserDict

from .errors import DuplicateError, InputError, NotFoundError


def _validate_note_id(note_id):
    if type(note_id) is not int or note_id <= 0:
        raise InputError("Note ID must be a positive integer.")
    return note_id


def _validate_text(text, field_name="Note text"):
    if not isinstance(text, str):
        raise InputError(f"{field_name} must be text.")
    if any(
        unicodedata.category(character) in {"Cc", "Cf", "Cs"}
        for character in text
    ):
        raise InputError(f"{field_name} cannot contain control characters.")

    cleaned = text.strip()
    if not cleaned:
        raise InputError(f"{field_name} cannot be blank.")
    return cleaned


def _validate_tag(tag):
    return _validate_text(tag, "Tag").casefold()


class Note:
    """One validated text note with a stable numeric identifier."""

    def __init__(self, note_id, text):
        self.id = _validate_note_id(note_id)
        self.text = _validate_text(text)
        self.tags = []

    def edit(self, text):
        """Replace this note's text after validating the replacement."""
        self.text = _validate_text(text)

    def add_tag(self, tag):
        """Attach one normalized tag to this note."""
        tag = _validate_tag(tag)
        if tag in self.tags:
            raise DuplicateError("Tag is already attached to this note.")
        self.tags.append(tag)

    def remove_tag(self, tag):
        """Remove one normalized tag from this note."""
        tag = _validate_tag(tag)
        if tag not in self.tags:
            raise NotFoundError("Tag is not attached to this note.")
        self.tags.remove(tag)

    def __str__(self):
        tags = ", ".join(self.tags) if self.tags else "none"
        return f"{self.id}: {self.text} [tags: {tags}]"


class Notebook(UserDict):
    """An in-memory collection that assigns stable, increasing note IDs."""

    def __init__(self):
        super().__init__()
        self.next_id = 1

    def add(self, text):
        """Create a note without consuming an ID when its text is invalid."""
        note = Note(self.next_id, text)
        self.data[note.id] = note
        self.next_id += 1
        return note

    def find(self, note_id):
        """Return a note by ID, or None if that valid ID is absent."""
        return self.data.get(_validate_note_id(note_id))

    def edit(self, note_id, text):
        """Replace the text of an existing note."""
        note = self.find(note_id)
        if note is None:
            raise NotFoundError("Note not found.")
        note.edit(text)
        return note

    def delete(self, note_id):
        """Delete and return an existing note without recycling its ID."""
        note_id = _validate_note_id(note_id)
        if note_id not in self.data:
            raise NotFoundError("Note not found.")
        return self.data.pop(note_id)

    def search(self, query):
        """Find notes whose text contains the casefolded query."""
        query = _validate_text(query, "Search query").casefold()
        return [
            note
            for note in self.all_items()
            if query in note.text.casefold()
        ]

    def all_items(self):
        """Return notes in stable identifier order."""
        return [self.data[note_id] for note_id in sorted(self.data)]

    def by_tag(self, tag):
        """Return ID-sorted notes that have one exact normalized tag."""
        tag = _validate_tag(tag)
        return [note for note in self.all_items() if tag in note.tags]

    def sorted_by_tags(self):
        """Return notes by tag tuple and ID, placing untagged notes last."""
        return sorted(
            self.data.values(),
            key=lambda note: (
                not note.tags,
                tuple(sorted(note.tags)),
                note.id,
            ),
        )

    def __str__(self):
        return "\n".join(str(note) for note in self.all_items())
