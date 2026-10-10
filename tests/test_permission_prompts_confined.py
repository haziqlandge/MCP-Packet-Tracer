"""CONSTRAINTS C3: headless paths never bring up a macOS permission prompt.

A TCC dialog nobody asked for, from `pt_bridge_status`, teaches users to click
Deny. Only the explicit UI-mode switch may ask. The tools run through the real
registry with the macOS backend forced and every grant missing; the request
functions record any call.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from src.packet_tracer_mcp.adapters.mcp.bridge_context import BridgeContext
from src.packet_tracer_mcp.adapters.mcp.tool_registry import register_tools
from src.packet_tracer_mcp.infrastructure import platform as host_platform
from src.packet_tracer_mcp.infrastructure.ui.backends.macos import permissions

SRC = Path(__file__).resolve().parents[1] / "src" / "packet_tracer_mcp"


class OfflineFileBridge:
    def pt_alive(self) -> bool:
        return True

    def mailbox_status(self) -> dict:
        return {"dir": "/tmp/bridge", "alive": True, "age_s": 0.1, "legacy": False}

    def send(self, payload: str) -> bool:
        return True

    def send_and_wait(self, js: str, timeout: float = 10.0):
        return None


class OfflineCtx(BridgeContext):
    """No network, no real PT: the file channel answers nothing."""

    def bridge_identity(self) -> str:
        return "none"

    def ensure_bridge(self) -> bool:
        return False

    def bridge_pt_connected(self) -> bool:
        return False


@pytest.fixture
def tools(tmp_path, monkeypatch):
    for var in ("HOME", "LOCALAPPDATA", "APPDATA"):
        monkeypatch.setenv(var, str(tmp_path))
    monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", "c3-test-token-long-enough-to-be-valid-0123456789")
    monkeypatch.setenv("PT_MCP_UI_BACKEND", "macos")
    host_platform.reset_current()
    asked: list[str] = []
    monkeypatch.setattr(permissions, "pyobjc_missing", lambda: None)
    monkeypatch.setattr(permissions, "state",
                        lambda: {"accessibility": False, "screen_recording": False, "post_events": False})
    monkeypatch.setattr(permissions, "_request_one", asked.append)
    permissions.reset_requests()
    mcp = FastMCP("c3")
    register_tools(mcp, OfflineCtx(file_bridge=OfflineFileBridge()))

    def call(name, **args):
        res = asyncio.run(mcp.call_tool(name, args))
        blocks = res[0] if isinstance(res, tuple) else res
        return "\n".join(getattr(b, "text", "") for b in blocks)

    yield call, asked
    permissions.reset_requests()
    host_platform.reset_current()


def test_headless_tools_never_request_a_permission(tools):
    call, asked = tools
    call("pt_bridge_status")
    call("pt_query_topology")
    call("pt_cli", device="R1", commands=["show clock"])
    call("pt_ui_mode", mode="status")
    assert asked == []


def test_switching_to_ui_mode_is_what_asks(tools):
    call, asked = tools
    out = call("pt_ui_mode", mode="ui")
    assert set(asked) == {"accessibility", "screen_recording"}
    assert "Accessibility" in out


def test_request_true_appears_only_in_pt_ui_mode():
    hits = []
    for path in SRC.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"available\(\s*request\s*=\s*True", line):
                hits.append(f"{path.relative_to(SRC).as_posix()}:{n}")
    assert len(hits) == 1 and hits[0].startswith("adapters/mcp/device_panel_tools.py:")
