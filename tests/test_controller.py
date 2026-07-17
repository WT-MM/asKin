"""Tests for platform-specific keyboard controller behavior."""

import subprocess
import sys

WINDOWS_IMPORT_SCRIPT = """
import asyncio
import builtins
import sys
import types

real_import = builtins.__import__


def import_without_termios(name, *args, **kwargs):
    if name == "termios":
        raise ModuleNotFoundError("No module named 'termios'")
    return real_import(name, *args, **kwargs)


fake_msvcrt = types.ModuleType("msvcrt")
fake_msvcrt.kbhit = lambda: True
fake_msvcrt.getwch = lambda: "a"

builtins.__import__ = import_without_termios
sys.modules["msvcrt"] = fake_msvcrt
sys.platform = "win32"

import askin
import askin.controller


async def handle_key(key):
    pass


askin.KeyboardController(handle_key)
assert askin.controller._read_key(0.001) == "a"
"""


def test_import_and_keyboard_controller_on_windows_without_termios() -> None:
    """The Windows backend must not import the Unix-only termios module."""
    result = subprocess.run(
        [sys.executable, "-c", WINDOWS_IMPORT_SCRIPT],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
