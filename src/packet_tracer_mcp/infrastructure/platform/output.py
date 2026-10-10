"""Where tool outputs land (CONSTRAINTS C11).

A GUI client may start the server with cwd `/`, which is read-only on macOS, and
every exporting tool then failed. A writable cwd is kept, so users whose cwd was
fine see no change; otherwise outputs go to a per-user folder.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from ...shared.utils import safe_name_component
from .base import OsName, detect_os

_ENV_VAR = "PT_MCP_OUTPUT_DIR"


def output_root(*, cwd: Path | None = None, env: Mapping[str, str] = os.environ,
                home: Path | None = None, os_name: OsName | None = None) -> Path:
    """`PT_MCP_OUTPUT_DIR` if set; else the cwd when it is writable and not a
    filesystem root; else a per-user folder. Creates nothing."""
    override = env.get(_ENV_VAR, "").strip()
    if override:
        return Path(override).expanduser()
    try:
        cwd = Path.cwd() if cwd is None else Path(cwd)
    except OSError:  # the cwd was deleted under us
        cwd = None
    # os.access, never a probe file: checking must not write anything.
    if cwd is not None and cwd != Path(cwd.anchor) and os.access(cwd, os.W_OK):
        return cwd
    home = Path.home() if home is None else home
    if (os_name or detect_os()) in ("windows", "macos"):
        return home / "Documents" / "Packet Tracer MCP"
    return home / "packet-tracer-mcp"


def output_dir(name: str, fallback: str) -> Path:
    """One safe folder name under `output_root()`. The caller creates it."""
    return output_root() / safe_name_component(name, fallback=fallback)
