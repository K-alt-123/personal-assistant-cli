"""Check the installed package and run its tests outside the source folder."""

import importlib
import os
from pathlib import Path
import pkgutil
import shutil
import subprocess
import sys
import tempfile
import unittest

import personal_assistant


def check_origins():
    prefix = Path(sys.prefix).resolve()
    for name, module in list(sys.modules.items()):
        if name == "personal_assistant" or name.startswith(
            "personal_assistant."
        ):
            origin = Path(module.__file__).resolve()
            if not origin.is_relative_to(prefix):
                raise RuntimeError(f"Package is not installed here: {origin}")
            print(f"{name}: {origin}")


def main():
    for module in pkgutil.iter_modules(personal_assistant.__path__):
        importlib.import_module(f"personal_assistant.{module.name}")
    check_origins()
    project = Path(__file__).resolve().parents[1]
    original_directory = Path.cwd()
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        shutil.copytree(project / "tests", directory / "tests",
                        ignore=shutil.ignore_patterns("__pycache__"))
        os.chdir(directory)
        try:
            executable = Path(sys.executable).parent / (
                "personal-assistant.exe" if os.name == "nt"
                else "personal-assistant"
            )
            result = subprocess.run(
                [str(executable), "--data-file", str(directory / "demo.json")],
                input='note-add "Installation check"\nnotes\nexit\n',
                capture_output=True, text=True, encoding="utf-8", timeout=10,
            )
            if result.returncode or (
                "1: Installation check" not in result.stdout
            ):
                raise RuntimeError(f"Console check failed: {result.stderr}")
            suite = unittest.defaultTestLoader.discover(
                str(directory / "tests"),
            )
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            check_origins()
            return 0 if result.wasSuccessful() else 1
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    raise SystemExit(main())
