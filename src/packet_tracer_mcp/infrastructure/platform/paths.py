"""Where the token and the file mailbox live (PLAN/INTERFACES.md §5).

Both sides of the pairing must agree (CONSTRAINTS C5): the extension inside PT
derives the same directories from its user folder, and it cannot read
environment variables. That is why `XDG_STATE_HOME` is not honoured here.

Pure functions: the OS, environment and home are passed in, so every OS's
answer can be tested on any OS.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .base import OsName

_APP_DIR = "packet-tracer-mcp"
_MAILBOX = "bridge"


def state_dir(os_name: OsName, env: Mapping[str, str], home: Path) -> Path:
    """Per-user, machine-local state directory (token, mailbox, UI-mode setting).

    Windows uses %LOCALAPPDATA% and not %APPDATA%: the latter roams, and a loopback
    secret has no reason to travel to a file server. This branch must stay exactly
    what `bridge_token.token_dir()` returned before, or installed extensions lose
    their token.
    """
    if os_name == "windows":
        base = env.get("LOCALAPPDATA") or env.get("APPDATA")
        return Path(base) / _APP_DIR if base else home / f".{_APP_DIR}"
    return home / ".local" / "state" / _APP_DIR


def mailbox_candidates(os_name: OsName, env: Mapping[str, str], home: Path) -> list[Path]:
    """Mailbox directories in preference order.

    On macOS and Linux the released V5.2 extension polls a Windows-shaped
    directory under home (measured on a Mac, PREVIOUS_WORK 2.4 #4), so it is the
    second candidate until a fixed `.pts` is the one in Releases.
    """
    candidates = [state_dir(os_name, env, home) / _MAILBOX]
    if os_name in ("macos", "linux"):
        candidates.append(home / "AppData" / "Local" / _APP_DIR / _MAILBOX)
    return candidates
