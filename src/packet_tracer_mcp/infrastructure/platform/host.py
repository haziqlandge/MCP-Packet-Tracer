"""Host facts: OS and versions, the running PT processes, and on macOS the app the
user must grant Accessibility and Screen Recording to.

Every function returns None or [] instead of raising (PLAN/INTERFACES.md §1).
"""

from __future__ import annotations

import csv
import platform as stdlib_platform
import subprocess
from collections.abc import Callable

from .base import HostInfo, OsName, detect_os

Ps = Callable[[int], "tuple[int, str] | None"]
Run = Callable[..., subprocess.CompletedProcess]
_MAX_CHAIN = 30


def host_info() -> HostInfo:
    os_name = detect_os()
    if os_name == "macos":
        version = stdlib_platform.mac_ver()[0]
    elif os_name == "windows":
        version = stdlib_platform.version()
    else:
        version = stdlib_platform.release()
    return HostInfo(os=os_name, os_version=version, arch=stdlib_platform.machine(),
                    python=stdlib_platform.python_version())


def _ps(pid: int) -> tuple[int, str] | None:
    """`(ppid, executable path)` of `pid`, from `ps`. None when unknown."""
    try:
        out = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    ppid, _, exe = out.partition(" ")
    try:
        return int(ppid), exe.strip()
    except ValueError:
        return None


def _outer_bundle(exe: str) -> str | None:
    """The outermost `.app` bundle an executable lives in.

    Outermost, because helpers nest (`Visual Studio Code.app/.../Code Helper.app`)
    and TCC asks about the app the user knows. An interpreter's own
    `Python.framework/.../Python.app` is never the answer: measured on the Mac
    (PREVIOUS_WORK 2.4 #9), it would have named "Python" instead of the client.
    """
    if "/Python.framework/" in exe:
        return None
    parts = exe.split("/")
    for i, part in enumerate(parts[:-1]):
        if part.endswith(".app"):
            return "/".join(parts[: i + 1])
    return None


def responsible_bundle(pid: int, *, ps: Ps = _ps, os_name: OsName | None = None) -> str | None:
    """Path of the app bundle macOS attributes `pid` to, walking up the ppid chain.

    Under Claude desktop's Code tab this is the bundled Claude Code CLI, a
    versioned path; remedy text names the full path. None off macOS.
    """
    if (os_name or detect_os()) != "macos":
        return None
    seen: set[int] = set()
    for _ in range(_MAX_CHAIN):
        if pid <= 1 or pid in seen:
            return None
        seen.add(pid)
        link = ps(pid)
        if link is None:
            return None
        ppid, exe = link
        bundle = _outer_bundle(exe)
        if bundle:
            return bundle
        pid = ppid
    return None


def responsible_app(pid: int, *, ps: Ps = _ps, os_name: OsName | None = None) -> str | None:
    """Name of that app ("Claude", "Terminal", "claude" for the Claude Code CLI)."""
    bundle = responsible_bundle(pid, ps=ps, os_name=os_name)
    return bundle.rsplit("/", 1)[-1][: -len(".app")] if bundle else None


def pt_processes(*, os_name: OsName | None = None, run: Run = subprocess.run) -> list[int]:
    """PIDs of running Packet Tracer processes; [] when none or unknown."""
    os_name = os_name or detect_os()
    if os_name == "windows":
        argv = ["tasklist", "/FI", "IMAGENAME eq PacketTracer.exe", "/FO", "CSV", "/NH"]
    elif os_name == "macos":
        # Measured: the app and its progress-bar helper are both named PacketTracer.
        argv = ["pgrep", "-x", "PacketTracer"]
    else:
        argv = ["pgrep", "-f", "PacketTracer"]
    try:
        out = run(argv, capture_output=True, text=True, timeout=5).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return []
    if os_name == "windows":
        rows = csv.reader(out.splitlines())
        return [int(r[1]) for r in rows if len(r) > 1 and r[1].isdigit()]
    return [int(line) for line in out.split() if line.isdigit()]
