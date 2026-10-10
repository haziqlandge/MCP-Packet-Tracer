"""The state directory and mailbox candidates (PLAN/INTERFACES.md §5).

Both sides of the pairing must compute the same paths (CONSTRAINTS C5): the
token and the mailbox live where the extension looks for them. On Windows the
location must stay exactly what `token_dir()` returned before the platform
layer existed, or every installed extension loses its token.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.packet_tracer_mcp.infrastructure.platform.base import detect_os
from src.packet_tracer_mcp.infrastructure.platform.paths import mailbox_candidates, state_dir

HOME = Path("/home/u")


def _legacy_windows_token_dir(env: dict[str, str], home: Path) -> Path:
    """`bridge_token.token_dir()` on Windows at bcb2ef3, frozen here on purpose."""
    base = env.get("LOCALAPPDATA") or env.get("APPDATA")
    return Path(base) / "packet-tracer-mcp" if base else home / ".packet-tracer-mcp"


class TestDetectOs:
    @pytest.mark.parametrize("raw, expected", [
        ("win32", "windows"), ("cygwin", "windows"), ("darwin", "macos"),
        ("linux", "linux"), ("linux2", "linux"), ("freebsd14", "other"),
    ])
    def test_maps_sys_platform(self, raw, expected):
        assert detect_os(raw) == expected

    def test_default_is_the_running_platform(self):
        assert detect_os() in ("windows", "macos", "linux", "other")


class TestStateDir:
    @pytest.mark.parametrize("env", [
        {"LOCALAPPDATA": r"C:\Users\u\AppData\Local", "APPDATA": r"C:\Users\u\AppData\Roaming"},
        {"APPDATA": r"C:\Users\u\AppData\Roaming"},
        {"LOCALAPPDATA": r"C:\Users\u\AppData\Local"},
        {},
    ])
    def test_windows_is_unchanged(self, env):
        assert state_dir("windows", env, HOME) == _legacy_windows_token_dir(env, HOME)

    @pytest.mark.parametrize("os_name", ["macos", "linux", "other"])
    def test_posix_default(self, os_name):
        assert state_dir(os_name, {}, HOME) == HOME / ".local" / "state" / "packet-tracer-mcp"

    @pytest.mark.parametrize("os_name", ["macos", "linux"])
    def test_xdg_state_home_is_ignored(self, os_name):
        # The extension cannot read environment variables, so honouring
        # XDG_STATE_HOME moved the token where PT never looks.
        env = {"XDG_STATE_HOME": "/elsewhere/state"}
        assert state_dir(os_name, env, HOME) == HOME / ".local" / "state" / "packet-tracer-mcp"


class TestMailboxCandidates:
    def test_windows_has_only_the_canonical_mailbox(self):
        env = {"LOCALAPPDATA": r"C:\Users\u\AppData\Local"}
        assert mailbox_candidates("windows", env, HOME) == [state_dir("windows", env, HOME) / "bridge"]

    @pytest.mark.parametrize("os_name", ["macos", "linux"])
    def test_posix_adds_the_v52_legacy_mailbox_second(self, os_name):
        assert mailbox_candidates(os_name, {}, HOME) == [
            HOME / ".local" / "state" / "packet-tracer-mcp" / "bridge",
            # Released V5.2 polls this one on a Mac (PREVIOUS_WORK 2.4 #4).
            HOME / "AppData" / "Local" / "packet-tracer-mcp" / "bridge",
        ]


def test_paths_never_read_the_real_environment(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", "/must/not/be/read")
    assert state_dir("windows", {}, HOME) == HOME / ".packet-tracer-mcp"
    assert os.environ["LOCALAPPDATA"] == "/must/not/be/read"
