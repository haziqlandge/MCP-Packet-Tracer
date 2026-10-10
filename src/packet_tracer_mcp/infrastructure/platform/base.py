"""Shared types of the platform layer: which OS, the host facts, the clipboard contract.

PLAN/INTERFACES.md §1. Only this package and `infrastructure/ui/backends/` look at
`sys.platform` (CONSTRAINTS C1); everything else asks `platform.current()`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from ..ui.backend import WindowBackend

OsName = Literal["windows", "macos", "linux", "other"]


def detect_os(sys_platform: str | None = None) -> OsName:
    """Map `sys.platform` (or the given value) to the OS names the server uses."""
    raw = sys.platform if sys_platform is None else sys_platform
    if raw in ("win32", "cygwin"):
        return "windows"
    if raw == "darwin":
        return "macos"
    if raw.startswith("linux"):
        return "linux"
    return "other"


@dataclass(frozen=True)
class HostInfo:
    os: OsName
    os_version: str
    arch: str
    python: str


class Clipboard(Protocol):
    name: str  # "clip.exe" | "pbcopy" | "wl-copy" | "xclip" | "xsel" | "none"

    def copy(self, text: str) -> bool:
        """Never raises: False when there is no tool or it failed."""
        ...


@dataclass(frozen=True)
class Platform:
    host: HostInfo
    state_dir: Path
    clipboard: Clipboard
    _ui: object = field(default=None, init=False, repr=False, compare=False)

    def ui_backend(self) -> "WindowBackend":
        """The UI backend for this OS, built on first use and then reused."""
        if self._ui is None:
            from ..ui.backends import load_backend
            object.__setattr__(self, "_ui", load_backend(self.host.os))
        return self._ui
