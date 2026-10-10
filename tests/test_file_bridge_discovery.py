"""The file channel follows the extension's heartbeat (PLAN/INTERFACES.md §5, C5).

The released V5.2 extension polls `~/AppData/Local/packet-tracer-mcp/bridge` on a
Mac (measured, PREVIOUS_WORK 2.4 #4) while the server wrote to
`~/.local/state/packet-tracer-mcp/bridge`, so the file channel never worked off
Windows (ISSUES X1). The server now writes where the heartbeat is.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from src.packet_tracer_mcp.infrastructure.execution.file_bridge import (
    HEARTBEAT_FRESH_S, FileBridge,
)
from src.packet_tracer_mcp.infrastructure.platform.paths import mailbox_candidates


def beat(directory: Path, age_s: float = 0.0) -> None:
    """Write a heartbeat that is `age_s` seconds old."""
    directory.mkdir(parents=True, exist_ok=True)
    alive = directory / "alive.txt"
    alive.write_text("1", encoding="utf-8")
    t = time.time() - age_s
    os.utime(alive, (t, t))


@pytest.fixture
def dirs(tmp_path):
    return tmp_path / "canonical" / "bridge", tmp_path / "legacy" / "bridge"


class TestActiveMailbox:
    def test_canonical_fresh_wins(self, dirs):
        canonical, legacy = dirs
        beat(canonical)
        fb = FileBridge(candidates=[canonical, legacy])
        assert fb.active_dir() == canonical and fb.pt_alive()

    def test_only_legacy_fresh_is_followed(self, dirs):
        canonical, legacy = dirs
        beat(legacy)
        fb = FileBridge(candidates=[canonical, legacy])
        assert fb.active_dir() == legacy and fb.pt_alive()

    def test_both_stale_falls_back_to_canonical(self, dirs):
        canonical, legacy = dirs
        beat(canonical, age_s=HEARTBEAT_FRESH_S * 3)
        beat(legacy, age_s=HEARTBEAT_FRESH_S * 2)
        fb = FileBridge(candidates=[canonical, legacy])
        assert fb.active_dir() == canonical and not fb.pt_alive()

    def test_both_fresh_picks_the_fresher(self, dirs):
        canonical, legacy = dirs
        beat(canonical, age_s=HEARTBEAT_FRESH_S / 2)
        beat(legacy, age_s=0.1)
        assert FileBridge(candidates=[canonical, legacy]).active_dir() == legacy

    def test_an_explicit_directory_still_wins(self, dirs, tmp_path):
        canonical, legacy = dirs
        beat(legacy)
        explicit = tmp_path / "explicit"
        assert FileBridge(explicit).active_dir() == explicit


class TestSendFollowsTheHeartbeat:
    def test_send_writes_into_the_live_mailbox(self, dirs):
        canonical, legacy = dirs
        beat(legacy)
        fb = FileBridge(candidates=[canonical, legacy])
        assert fb.send("noop();")
        assert len(list(legacy.glob("req_*.js"))) == 1
        assert not canonical.exists()

    def test_the_choice_is_re_evaluated_on_every_send(self, dirs):
        canonical, legacy = dirs
        beat(legacy)
        fb = FileBridge(candidates=[canonical, legacy])
        fb.send("a();")
        beat(legacy, age_s=HEARTBEAT_FRESH_S * 2)
        beat(canonical)
        fb.send("b();")
        assert len(list(legacy.glob("req_*.js"))) == 1
        assert len(list(canonical.glob("req_*.js"))) == 1

    def test_send_and_wait_reads_the_answer_from_the_live_mailbox(self, dirs):
        canonical, legacy = dirs
        beat(legacy)
        fb = FileBridge(candidates=[canonical, legacy])
        import threading

        def answer():
            deadline = time.time() + 5
            while time.time() < deadline:
                for req in legacy.glob("req_*.js"):
                    (legacy / f"res_{req.stem[4:]}.txt").write_text("pong", encoding="utf-8")
                    req.unlink()
                    return
                time.sleep(0.02)

        t = threading.Thread(target=answer)
        t.start()
        assert fb.send_and_wait("ping();", timeout=5) == "pong"
        t.join()


class TestStatus:
    def test_reports_the_legacy_mailbox(self, dirs):
        canonical, legacy = dirs
        beat(legacy, age_s=0.5)
        st = FileBridge(candidates=[canonical, legacy]).mailbox_status()
        assert st["dir"] == str(legacy) and st["alive"] is True and st["legacy"] is True
        assert 0 <= st["age_s"] < HEARTBEAT_FRESH_S

    def test_reports_the_canonical_mailbox(self, dirs):
        canonical, legacy = dirs
        beat(canonical)
        st = FileBridge(candidates=[canonical, legacy]).mailbox_status()
        assert st["dir"] == str(canonical) and st["legacy"] is False

    def test_no_heartbeat_anywhere(self, dirs):
        canonical, legacy = dirs
        st = FileBridge(candidates=[canonical, legacy]).mailbox_status()
        assert st == {"dir": str(canonical), "alive": False, "age_s": None, "legacy": False}


def test_windows_never_creates_the_legacy_tree(tmp_path):
    home = tmp_path / "home"
    env = {"LOCALAPPDATA": str(tmp_path / "local")}
    candidates = mailbox_candidates("windows", env, home)
    assert len(candidates) == 1
    FileBridge(candidates=candidates).send("noop();")
    assert candidates[0].is_dir()
    assert not (home / "AppData").exists()


def test_default_candidates_come_from_the_platform_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    from src.packet_tracer_mcp.infrastructure.platform.base import detect_os
    expected = mailbox_candidates(detect_os(), os.environ, Path.home())
    assert FileBridge().candidates == expected


class TestStatusLine:
    """`pt_bridge_status` says which mailbox PT polls, with the home shown as `~`."""

    def test_legacy_mailbox_is_named_as_such(self):
        from src.packet_tracer_mcp.adapters.mcp.tools.live import mailbox_line
        home = str(Path.home())
        line = mailbox_line({"dir": f"{home}/AppData/Local/packet-tracer-mcp/bridge",
                             "alive": True, "age_s": 0.4, "legacy": True})
        assert "~/AppData/Local/packet-tracer-mcp/bridge" in line and home not in line
        assert "legacy" in line and "V5.2" in line

    def test_canonical_mailbox_has_no_legacy_note(self):
        from src.packet_tracer_mcp.adapters.mcp.tools.live import mailbox_line
        line = mailbox_line({"dir": f"{Path.home()}/.local/state/packet-tracer-mcp/bridge",
                             "alive": True, "age_s": 0.4, "legacy": False})
        assert "~/.local/state/packet-tracer-mcp/bridge" in line and "legacy" not in line
