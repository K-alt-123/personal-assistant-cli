"""Contact domain models."""

from collections import UserDict
from datetime import date, datetime
import re
import unicodedata

from .errors import DuplicateError, InputError, NotFoundError


CONTROL_CATEGORIES = {"Cc", "Cf", "Cs"}


def has_control_characters(value):
    return any(
        unicodedata.category(char) in CONTROL_CATEGORIES for char in value
    )


def format_birthday(value):
    return f"{value.day:02}.{value.month:02}.{value.year:04}"


def validate_text(value, label):
    """Return nonempty, trimmed text without Unicode control characters."""
    if not isinstance(value, str):
        raise InputError(f"{label} must be text")
    if has_control_characters(value):
        raise InputError(f"{label} cannot contain control characters")
    value = value.strip()
    if not value:
        raise InputError(f"{label} cannot be empty")
    return value


class Field:
    def __init__(self, value):
        self.value = validate_text(value, self.__class__.__name__)

    def __str__(self):
        return str(self.value)


class Name(Field):
    pass


class Phone(Field):
    def __init__(self, value):
        if not isinstance(value, str):
            raise InputError("Phone must be text")
        if not re.fullmatch(r"[0-9]{10}", value):
            raise InputError("Phone must contain exactly 10 digits")
        self.value = value


class Email(Field):
    _pattern = re.compile(
        r"[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+)*@"
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+"
        r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    )

    def __init__(self, value):
        if not isinstance(value, str):
            raise InputError("Email must be text")
        if has_control_characters(value):
            raise InputError("Email cannot contain control characters")
        if len(value) > 254 or any(char.isspace() for char in value):
            raise InputError("Email has an invalid format")
        if value.count("@") != 1:
            raise InputError("Email has an invalid format")
        local, domain = value.split("@")
        if (
            not local
            or not domain
            or len(local) > 64
            or not self._pattern.fullmatch(value)
        ):
            raise InputError("Email has an invalid format")
        if len(domain) > 253:
            raise InputError("Email has an invalid format")
        self.value = f"{local}@{domain.lower()}"


class Address(Field):
    pass


class Birthday(Field):
    def __init__(self, value, today=None):
        if not isinstance(value, str):
            raise InputError("Birthday must be text")
        try:
            birthday = datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError as error:
            raise InputError("Birthday must be DD.MM.YYYY") from error
        if format_birthday(birthday) != value:
            raise InputError("Birthday must be DD.MM.YYYY")
        if birthday > (today or date.today()):
            raise InputError("Birthday cannot be in the future")
        self.value = birthday

    def __str__(self):
        return format_birthday(self.value)


class Record:
    def __init__(self, name):
        self.name = Name(name)
        self.phones = []
        self.address = None
        self.email = None
        self.birthday = None

    def add_phone(self, phone):
        new_phone = Phone(phone)
        if self.find_phone(new_phone.value):
            raise DuplicateError("This phone is already saved for the contact")
        self.phones.append(new_phone)

    def remove_phone(self, phone):
        existing_phone = self.find_phone(Phone(phone).value)
        if existing_phone is None:
            raise NotFoundError("Phone was not found")
        self.phones.remove(existing_phone)

    def edit_phone(self, old_phone, new_phone):
        replacement = Phone(new_phone)
        existing_phone = self.find_phone(Phone(old_phone).value)
        if existing_phone is None:
            raise NotFoundError("Phone was not found")
        if (
            replacement.value != existing_phone.value
            and self.find_phone(replacement.value)
        ):
            raise DuplicateError("This phone is already saved for the contact")
        existing_phone.value = replacement.value

    def find_phone(self, phone):
        for existing_phone in self.phones:
            if existing_phone.value == phone:
                return existing_phone
        return None

    def set_address(self, address):
        self.address = Address(address)

    def set_email(self, email):
        self.email = Email(email)

    def add_birthday(self, birthday):
        self.birthday = Birthday(birthday)

    def clear_field(self, field):
        if not isinstance(field, str) or field not in {
            "address",
            "email",
            "birthday",
        }:
            raise InputError("Only address, email, or birthday can be cleared")
        setattr(self, field, None)

    def __str__(self):
        phones = ", ".join(str(phone) for phone in self.phones) or "not set"
        address = self.address or "not set"
        email = self.email or "not set"
        birthday = self.birthday or "not set"
        return (
            f"Name: {self.name}; phones: {phones}; address: {address}; "
            f"email: {email}; birthday: {birthday}"
        )


class AddressBook(UserDict):
    def add_record(self, record):
        if not isinstance(record, Record):
            raise InputError("Record must be a Record object")
        name = record.name.value
        if name in self.data:
            raise DuplicateError("A contact with this name already exists")
        self.data[name] = record

    def find(self, name):
        return self.data.get(Name(name).value)

    def delete(self, name):
        record = self.find(name)
        if record is None:
            raise NotFoundError("Contact was not found")
        del self.data[record.name.value]
        return record

    def rename(self, old_name, new_name):
        record = self.find(old_name)
        if record is None:
            raise NotFoundError("Contact was not found")
        old_name = record.name.value
        new_name = Name(new_name).value
        if new_name == old_name:
            return
        if new_name in self.data:
            raise DuplicateError("A contact with this name already exists")
        del self.data[old_name]
        record.name = Name(new_name)
        self.data[new_name] = record

    def search(self, query, field=None):
        query = validate_text(query, "Search query").casefold()
        fields = {"name", "phone", "email", "address"}
        if field is not None and (
            not isinstance(field, str) or field not in fields
        ):
            raise InputError(
                "Search field must be name, phone, email, or address"
            )
        matched = []
        for record in self.data.values():
            values = self._search_values(record, field)
            if any(query in value.casefold() for value in values):
                matched.append(record)
        return sorted(
            matched,
            key=lambda record: (
                record.name.value.casefold(),
                record.name.value,
            ),
        )

    def get_upcoming_birthdays(self, days=7, today=None):
        if type(days) is not int or not 1 <= days <= 366:
            raise InputError("Days must be an integer from 1 through 366")
        if today is None:
            today = date.today()
        if not isinstance(today, date):
            raise InputError("Today must be a date")

        upcoming = []
        for record in self.data.values():
            if record.birthday is None:
                continue
            birthday_date = self._next_birthday(record.birthday.value, today)
            if birthday_date is None:
                continue
            offset = (birthday_date - today).days
            if 0 <= offset < days:
                upcoming.append((birthday_date, record.name.value))
        upcoming.sort(key=lambda item: (item[0], item[1].casefold(), item[1]))
        return [
            {"name": name, "birthday_date": birthday_date.isoformat()}
            for birthday_date, name in upcoming
        ]

    @staticmethod
    def _search_values(record, field):
        values = {
            "name": [record.name.value],
            "phone": [phone.value for phone in record.phones],
            "email": [record.email.value] if record.email else [],
            "address": [record.address.value] if record.address else [],
        }
        if field is not None:
            return values[field]
        return [value for group in values.values() for value in group]

    @staticmethod
    def _next_birthday(birthday, today):
        birthday_date = AddressBook._birthday_in_year(birthday, today.year)
        if birthday_date >= today:
            return birthday_date
        if today.year == date.max.year:
            return None
        return AddressBook._birthday_in_year(birthday, today.year + 1)

    @staticmethod
    def _birthday_in_year(birthday, year):
        if birthday.month == 2 and birthday.day == 29:
            try:
                return date(year, 2, 29)
            except ValueError:
                return date(year, 2, 28)
        return date(year, birthday.month, birthday.day)
