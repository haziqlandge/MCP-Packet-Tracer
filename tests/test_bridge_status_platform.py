"""Bridge status keeps its channel explanation and adds preflight diagnostics."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from mcp.server.fastmcp import FastMCP

from src.packet_tracer_mcp.adapters.mcp.bridge_context import BridgeContext
from src.packet_tracer_mcp.adapters.mcp.tools import live


class FakeFileBridge:
    def __init__(self, alive):
        self.alive = alive

    def pt_alive(self):
        return self.alive

    def mailbox_status(self):
        return {"dir": "/tmp/bridge", "alive": self.alive, "age_s": 0.8,
                "legacy": False}


@pytest.mark.parametrize("channel,expected", [
    ("both", "CONNECTED over both channels"),
    ("http", "CONNECTED over HTTP"),
    ("file", "CONNECTED over file-bridge"),
    ("disconnected", "NOT connected over any channel"),
    ("foreign", "NOT this MCP server's bridge"),
    ("stale", "stale authorization remedy"),
])
def test_every_status_branch_carries_the_platform_block(monkeypatch, channel, expected):
    mailbox = FakeFileBridge(channel in ("both", "file"))
    ctx = BridgeContext(file_bridge=mailbox)
    ctx.bridge_identity = lambda: "foreign" if channel == "foreign" else "none"
    ctx.ensure_bridge = lambda: channel in ("both", "http")
    ctx.bridge_pt_connected = lambda: channel in ("both", "http")
    ctx.stale_client_message = lambda: "stale authorization remedy"
    if channel == "stale":
        ctx.instance = SimpleNamespace(_client_headers={}, saw_recent_unauthorized=True)
    calls = []
    platform = {"os": "macos", "os_version": "14.6", "arch": "arm64",
                "state_dir": "~/.local/state/packet-tracer-mcp",
                "mailbox": {"dir": "~/.local/state/packet-tracer-mcp/bridge", "alive": True,
                            "age_s": 0.8, "legacy": False},
                "clipboard": "pbcopy",
                "ui": {"backend": "macos", "ok": False, "reason": "grant to Codex",
                       "permissions": {"accessibility": False, "screen_recording": False},
                       "grant_to": "Codex"}}

    def preflight(*, file_bridge):
        calls.append(file_bridge)
        return platform

    monkeypatch.setattr(live, "platform_status", preflight, raising=False)
    monkeypatch.setattr(live, "token_was_rotated", lambda: False)
    monkeypatch.setattr(live, "token_is_ephemeral", lambda: False)
    mcp = FastMCP("status-test")
    live.register(mcp, ctx)
    result = asyncio.run(mcp.call_tool("pt_bridge_status", {}))
    blocks = result[0] if isinstance(result, tuple) else result
    reply = json.loads("\n".join(getattr(block, "text", "") for block in blocks))
    assert list(reply) == ["status", "platform"]
    assert expected in reply["status"]
    assert reply["platform"] == platform
    assert calls == [mailbox]


@pytest.mark.parametrize("os_name", ["macos", "windows", "linux"])
def test_real_platform_block_has_ordered_keys_home_paths_and_never_prompts(
        tmp_path, monkeypatch, os_name):
    from pathlib import Path

    from src.packet_tracer_mcp.infrastructure.platform import doctor
    from src.packet_tracer_mcp.infrastructure.platform.base import HostInfo
    from src.packet_tracer_mcp.infrastructure.ui.backends.macos import MacBackend, permissions
    from src.packet_tracer_mcp.infrastructure.ui.backends.null import NullBackend

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(permissions, "pyobjc_missing", lambda: None)
    monkeypatch.setattr(permissions, "state", lambda: {
        "accessibility": False, "screen_recording": False, "post_events": False})

    def forbidden_request(*args, **kwargs):
        raise AssertionError("Status diagnostics must never request a privacy permission")

    monkeypatch.setattr(permissions, "request", forbidden_request)
    monkeypatch.setattr(permissions, "_request_one", forbidden_request)
    backend = (MacBackend(responsible=lambda: ("Codex", "/Applications/Codex.app"))
               if os_name == "macos" else NullBackend("UI unavailable in offline test"))
    platform = SimpleNamespace(host=HostInfo(os_name, "test-version", "test-arch", "3.12"),
                               state_dir=tmp_path / ".local/state/packet-tracer-mcp",
                               clipboard=SimpleNamespace(name="none"), ui_backend=lambda: backend)
    mailbox = FakeFileBridge(False)
    mailbox.mailbox_status = lambda: {
        "dir": str(platform.state_dir / "bridge"), "alive": False, "age_s": None,
        "legacy": False}
    result = doctor.platform_status(file_bridge=mailbox, platform=platform)
    assert list(result) == ["os", "os_version", "arch", "state_dir", "mailbox", "clipboard", "ui"]
    assert result["os"] == os_name
    assert result["state_dir"] == "~/.local/state/packet-tracer-mcp"
    assert list(result["mailbox"]) == ["dir", "alive", "age_s", "legacy"]
    assert result["mailbox"]["dir"] == "~/.local/state/packet-tracer-mcp/bridge"
    assert result["mailbox"]["alive"] is False
    assert result["mailbox"]["age_s"] is None
    assert list(result["ui"]) == ["backend", "ok", "reason", "permissions", "grant_to"]
    if os_name == "macos":
        assert result["ui"]["permissions"] == {
            "accessibility": False, "screen_recording": False}
        assert result["ui"]["ok"] is False
        assert "Accessibility" in result["ui"]["reason"]
