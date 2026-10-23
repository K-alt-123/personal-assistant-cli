# Personal Assistant

A solo Python final project: a command-line address book and notebook.
Contacts can have several phone numbers, an address, an email, and a birthday.
Notes have stable IDs and optional tags. Data is saved after each change.

## Install and run

Requires Python 3.11 or newer. Installation includes Colorama for terminal
colours, including Windows console support.
Extract the project ZIP, then open a terminal in the extracted folder.

Linux/macOS:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
personal-assistant
```

Windows PowerShell (activation is optional):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\personal-assistant.exe
```

With the environment activated, `personal-assistant` works from any folder.
Without activation, use the full path to that environment's executable.
`python -m personal_assistant` is another way to launch the installed app.

Interactive terminals show a two-tone PA wordmark and illustrated command
responses: a contact card, notebook, birthday cake, search lens, or deletion
bin. The little face and status change after each command. The prompt shows
the current contact and note counts; `SAVED` appears only after saving succeeds.
Errors show `ERROR` or `NOT SAVED`, and cancelled deletions show `CANCELLED`.

Artwork adapts to the current terminal width: a large logo in wide windows,
a compact logo in medium windows, and text in narrow windows. New output
uses the latest width; previous output is left in the terminal history.
There are no animation delays or screen-clearing effects. User text, including
Ukrainian and emoji, is printed intact and wraps normally in the terminal.

Successful changes are green, errors red, and deletion confirmations yellow.
Every status also has a text label. Use `personal-assistant --no-color` or a
nonempty `NO_COLOR` environment variable to keep the artwork without colours.
Use `personal-assistant --plain` to remove all decoration and status prompts.
Redirected output and `TERM=dumb` automatically use plain output.

## Example

Enter these commands **inside the app**, after its `>` prompt:

```text
add "Олена Коваль" 0501234567
add "Олена Коваль" 0123456789
set-address "Олена Коваль" "Київ, вул. Липова 4"
set-email "Олена Коваль" olena@example.org
add-birthday "Олена Коваль" 29.02.2000
show "Олена Коваль"
find "київ" address
birthdays 30
note-add "Prepare the project demo"
tag-add 1 study
notes-tag study
exit
```

Run the app again and enter `all` or `notes` to see the saved data.
Try `add Bob 123`: the app explains the phone format and returns to the prompt.

## Commands

Use `help` to see the syntax. Commands are case-insensitive; contact names
are exact and case-sensitive. Quote arguments containing spaces, for example
`note-add "Read about OOP"`. Double quotes also allow apostrophes:
`add "O'Connor" 0501234567`. To include a double quote inside double-quoted
text, escape it with `\"`. These are the app's quoting rules on every OS.
Commands are parsed as text and never executed by a system shell.

| Command | Purpose |
| --- | --- |
| `hello`, `help` | Greeting and command list |
| `exit`, `close` | Leave the app |
| `add "name" phone` | Create a contact or add a phone to that exact name |
| `all`, `show "name"`, `phone "name"` | List contacts, one contact, or its phones |
| `change "name" old-phone new-phone` | Replace one phone number |
| `remove-phone "name" phone` | Remove one phone number |
| `rename "old name" "new name"` | Rename a contact without overwriting another |
| `set-address "name" "address"` | Set or replace an address |
| `set-email "name" email` | Set or replace an email |
| `add-birthday "name" DD.MM.YYYY` | Set or replace a birthday |
| `show-birthday "name"` | Display a birthday |
| `clear-field "name" address/email/birthday` | Clear one optional field |
| `find "query" [name/phone/email/address]` | Substring search, optionally in one field |
| `delete "name"` | Display the contact and ask before deleting |
| `birthdays [days]` | Upcoming birthdays; default 7 days |
| `note-add "text"`, `notes`, `note-show id` | Create, list, or read notes |
| `note-find "query"` | Search note text |
| `note-edit id "text"` | Replace note text |
| `note-delete id` | Display the note and ask before deleting |
| `tag-add id "tag"`, `tag-remove id "tag"` | Add or remove a note tag |
| `notes-tag "tag"` | Find notes with an exact tag |
| `notes-sort-tags` | Sort notes by tags, with untagged notes last |

Deletion accepts `yes` or `y`; anything else cancels. Ctrl+C or EOF during
confirmation cancels that deletion. At the main prompt they exit the app.

## Input rules

- Names, addresses, notes, and tags must be nonempty text. Outer whitespace
  is trimmed; terminal control characters are rejected. Notes are single-line.
- Phone numbers contain exactly **10 ASCII digits**. Leading zeroes are kept.
  Spaces, `+`, letters, and other lengths are rejected. This follows the local
  phone format used in the homework; international numbers are not supported.
- Email accepts a common ASCII subset: letters, digits, `._%+-` before `@`,
  and dot-separated letters/digits/hyphens after it. Empty local dot segments
  and domain labels starting/ending with `-` are rejected. Limits are 64
  characters for the local part, 253 for the domain, and 254 overall.
  For example, `Mary+work@Example.org` becomes `Mary+work@example.org`.
  `a..b@example.org` and `a@-example.org` are rejected. The app checks syntax,
  not whether a mailbox exists; it does not accept every RFC email form.
- Birthdays must be real dates in `DD.MM.YYYY`, no later than today.
  `birthdays N` accepts 1–366 and includes today through N−1 days from today.
  It displays the next birthday once per contact, keeps weekends unchanged,
  and uses February 28 for February 29 in a non-leap year.
- An exact contact name is unique. Use distinct names for different people.
  Search is case-insensitive. Renaming to an existing name is rejected.
- Note IDs are positive integers and are never reused after deletion.
  Tags are trimmed and casefolded; duplicate tags are rejected.

## Saved data and errors

The default file is `.personal_assistant/data.json` inside your home folder,
for example `C:\Users\YourName\.personal_assistant\data.json` on Windows.
The working directory does not change this location. For a separate demo:

```sh
personal-assistant --data-file demo-data.json
```

The file contains versioned UTF-8 JSON. Each change is made on a copy of the
current data, validated, written to a temporary file, and then replaces the
previous save. Only after replacement succeeds does the app report success.
If saving fails, the previous in-memory data and save file are retained.
Read commands and exiting do not rewrite the save file.

A missing file starts an empty collection. An existing unreadable, malformed,
or incompatible file stops startup with an error and is left untouched.
Keep a backup before editing a save manually. Restore a valid backup or use
`--data-file` with a new filename to start a separate collection. A disk or
permission error during a change reports `Change not saved`; resolve the
cause before entering the change again.
Control characters in system error messages are displayed as escaped text,
so a problematic filename cannot clear the terminal or change its title.

Use **one running instance per data file**. Concurrent editing, encrypted
storage, and recovery from hardware failure are outside this project.

## Tests

Install the app first, then run from the project folder:

```sh
python -m pip install . -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m pycodestyle personal_assistant tests scripts
python -m coverage run --branch --source=personal_assistant -m unittest discover -s tests
python -m coverage report -m
python scripts/check_installation.py
```

The tests use synthetic data and temporary folders. They cover field rules,
failed edits, birthday boundaries, contacts, notes, tags, malformed saves,
injected write/flush/replace failures, deletion confirmation, Unicode, and
separate-process restarts. The installation check requires a normal install
(`pip install .`, not `pip install -e .`): it checks import locations and runs
the suite and console command outside the source folder.
Presentation tests also cover status/count changes, failed-save reactions,
20–160-column layouts, resizing, plain mode, and control characters in errors.

The release was tested on Linux with Python 3.12. Windows, macOS, and Python
3.11 have not yet been executed. The Windows commands above are provided for
setup; they are not evidence of a completed Windows test run.

## Code layout

- `address_book.py`: validated field classes, `Record`, and `AddressBook`.
- `notes.py`: `Note`, `Notebook`, IDs, and tag operations.
- `assistant.py`: parsing, commands, prompts, and save orchestration.
- `storage.py`: JSON validation, loading, and file replacement.
- `errors.py`: expected input, missing-item, duplicate, and storage errors.
- `terminal.py`: ASCII artwork, colours, outcome feedback, counts, and help.

`Phone`, `Email`, and `Birthday` inherit from `Field`. A `Record` contains
field objects and a list of phones (composition). Collections use `UserDict`.
Models do not read terminal input or write files. Expected input errors return
to the prompt; unexpected programming errors stop the process with a nonzero
exit code instead of being treated as invalid user input.
