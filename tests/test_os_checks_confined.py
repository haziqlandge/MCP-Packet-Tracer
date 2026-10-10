"""CONSTRAINTS C1: only the platform layer and the UI backends look at the OS.

Scattered `sys.platform` checks are how the code became Windows-only. Any other
module asks `infrastructure.platform` instead.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "packet_tracer_mcp"
ALLOWED_DIRS = ("infrastructure/platform/", "infrastructure/ui/backends/")
# Emptied in PHASE-03, when the Windows UI code moved under ui/backends/.
# Never add to it.
ALLOW_LIST: set[str] = set()
OS_CHECK = re.compile(r"\bsys\.platform\b|\bos\.name\b")


def test_os_checks_live_only_in_the_platform_layer():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith(ALLOWED_DIRS) or rel in ALLOW_LIST:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if OS_CHECK.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()}")
    print("C1 allow-list:", sorted(ALLOW_LIST))
    assert offenders == []


def test_allow_list_entries_still_exist():
    # A stale entry would silently re-open the door after the file moves.
    assert all((SRC / rel).is_file() for rel in ALLOW_LIST)
