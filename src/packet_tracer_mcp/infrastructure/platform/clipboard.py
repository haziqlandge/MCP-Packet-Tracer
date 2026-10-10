"""The system clipboard, one small class per tool (PLAN/INTERFACES.md §1).

Every class takes the `run` callable (default `subprocess.run`) so tests check
the exact command and bytes without touching the real clipboard. `copy()` never
raises.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping

from .base import Clipboard, OsName

Run = Callable[..., object]
_TIMEOUT = 5
_ERRORS = (subprocess.SubprocessError, FileNotFoundError, OSError)


class ClipExe:
    """Windows. The call is byte-for-byte what `deploy_executor` always did."""

    name = "clip.exe"

    def __init__(self, run: Run):
        self._run = run

    def copy(self, text: str) -> bool:
        try:
            self._run("clip", input=text.encode("utf-16-le"), check=True, timeout=_TIMEOUT)
            return True
        except _ERRORS:
            return False


class Pbcopy:
    """macOS. A GUI-launched process can lack a locale, and pbcopy then mangles
    non-ASCII text, so LC_CTYPE is always set."""

    name = "pbcopy"

    def __init__(self, run: Run, env: Mapping[str, str]):
        self._run = run
        self._env = {**env, "LC_CTYPE": "UTF-8"}

    def copy(self, text: str) -> bool:
        try:
            self._run(["pbcopy"], input=text.encode("utf-8"), env=self._env,
                      check=True, timeout=_TIMEOUT)
            return True
        except _ERRORS:
            return False


class _Utf8Tool:
    """A Linux clipboard tool that reads UTF-8 on stdin."""

    def __init__(self, name: str, argv: list[str], run: Run):
        self.name = name
        self._argv = argv
        self._run = run

    def copy(self, text: str) -> bool:
        try:
            self._run(list(self._argv), input=text.encode("utf-8"), check=True, timeout=_TIMEOUT)
            return True
        except _ERRORS:
            return False


class NoClipboard:
    name = "none"

    def copy(self, text: str) -> bool:
        return False


def clipboard_for(os_name: OsName, *, which: Callable[[str], str | None] = shutil.which,
                  env: Mapping[str, str] = os.environ, run: Run = subprocess.run) -> Clipboard:
    """The clipboard for `os_name`: clip.exe, pbcopy, or on Linux wl-copy (Wayland
    only), xclip, xsel, in that order. NoClipboard when none is installed."""
    if os_name == "windows":
        return ClipExe(run)
    if os_name == "macos":
        return Pbcopy(run, env) if which("pbcopy") else NoClipboard()
    if env.get("WAYLAND_DISPLAY") and which("wl-copy"):
        return _Utf8Tool("wl-copy", ["wl-copy"], run)
    if which("xclip"):
        return _Utf8Tool("xclip", ["xclip", "-selection", "clipboard"], run)
    if which("xsel"):
        return _Utf8Tool("xsel", ["xsel", "--clipboard", "--input"], run)
    return NoClipboard()
