class InputError(ValueError):
    """An expected error in a command or field value."""


class NotFoundError(InputError):
    """The requested contact, note, phone, or tag does not exist."""


class DuplicateError(InputError):
    """An operation would create a duplicate value."""


class StorageError(Exception):
    """Saved data could not be read or written safely."""
