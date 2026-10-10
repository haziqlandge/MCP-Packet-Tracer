"""The one home of OS facts (CONSTRAINTS C1, PLAN/INTERFACES.md §1).

Ask `current()` for the host, the state directory and the clipboard instead of
checking `sys.platform` elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import Clipboard, HostInfo, OsName, Platform, detect_os
from .clipboard import clipboard_for
from .host import host_info, pt_processes, responsible_app, responsible_bundle
from .output import output_dir, output_root
from .paths import mailbox_candidates, state_dir

__all__ = [
    "Clipboard", "HostInfo", "OsName", "Platform", "clipboard_for", "current", "detect_os",
    "host_info", "mailbox_candidates", "output_dir", "output_root", "pt_processes",
    "reset_current", "responsible_app", "responsible_bundle", "state_dir",
]

_current: Platform | None = None


def current() -> Platform:
    """The running host's platform, built once per process."""
    global _current
    if _current is None:
        info = host_info()
        _current = Platform(host=info, state_dir=state_dir(info.os, os.environ, Path.home()),
                            clipboard=clipboard_for(info.os))
    return _current


def reset_current() -> None:
    """Drop the cached platform. For tests only."""
    global _current
    _current = None
