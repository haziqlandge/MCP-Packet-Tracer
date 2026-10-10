"""One UI backend per OS, chosen at runtime (PLAN/INTERFACES.md §2).

Only this package and `infrastructure/platform/` look at the OS (CONSTRAINTS
C1). A backend's own OS packages (comtypes, pyobjc) are imported inside it,
never here, so every module imports on every OS (C2).
"""

from __future__ import annotations

import os
import sys
from typing import Mapping

from ...platform.base import OsName, detect_os
from ..backend import WindowBackend
from .null import NullBackend

ENV = "PT_MCP_UI_BACKEND"
CHOICES = ("null", "windows", "macos", "linux")

LINUX_REASON = "UI mode is not available on Linux yet; every tool works headless. See PHASE-08."
# What reinstalls a backend whose import failed.
_FIX = {"windows": "pip install packet-tracer-mcp[ui]", "macos": "pip install --upgrade packet-tracer-mcp"}


def load_backend(os_name: OsName | None = None, env: Mapping[str, str] = os.environ) -> WindowBackend:
    """The backend for `os_name` (default: this host). `PT_MCP_UI_BACKEND`
    overrides it; an unknown value, or a backend whose import fails, gives a
    NullBackend carrying the reason."""
    override = (env.get(ENV) or "").strip().lower()
    if override and override not in CHOICES:
        return NullBackend(f"{ENV}={override!r} is not a UI backend (choose one of: "
                           f"{', '.join(CHOICES)}); every tool works headless.")
    name = override or os_name or detect_os()
    if name == "null":
        return NullBackend(f"UI mode is turned off ({ENV}=null); every tool works headless.")
    if name == "windows":
        try:
            from .windows import WindowsBackend
        except ImportError as exc:
            return NullBackend(f"the windows UI backend failed to import ({exc}). "
                               f"Reinstall it with `{_FIX['windows']}`; every tool works headless.")
        return WindowsBackend()
    if name == "macos":
        try:
            from .macos import MacBackend
        except ImportError as exc:
            return NullBackend(f"the macos UI backend failed to import ({exc}). "
                               f"Reinstall it with `{_FIX['macos']}`; every tool works headless.")
        return MacBackend()
    if name == "linux":
        return NullBackend(LINUX_REASON)
    return NullBackend(f"UI mode is not available on this OS ({sys.platform}); "
                       "every tool works headless.")
