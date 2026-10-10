"""Only an explicit UI-mode choice requests permissions, and remedies survive."""

from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from src.packet_tracer_mcp.adapters.mcp.device_panel_tools import register_device_panel_tools
from src.packet_tracer_mcp.shared.ui_mode import UiModeStore

REMEDY = "Screen Recording remedy for Codex: System Settings > Privacy & Security."


class FakePresenter:
    def __init__(self, ok=True, reason=""):
        self.ok = ok
        self.reason = reason
        self.requests = []

    def available(self, *, request=False):
        self.requests.append(request)
        return self.ok, self.reason


def tools(tmp_path, presenter):
    store = UiModeStore(tmp_path, environ={})
    mcp = FastMCP("onboarding-test")

    def forbidden_send(*args):
        raise AssertionError("Changing UI mode must not contact Packet Tracer")

    register_device_panel_tools(mcp, send_and_wait=forbidden_send, check_bridge=lambda: None,
                                store=store, presenter=presenter)

    def call(mode):
        result = asyncio.run(mcp.call_tool("pt_ui_mode", {"mode": mode}))
        blocks = result[0] if isinstance(result, tuple) else result
        return "\n".join(getattr(block, "text", "") for block in blocks)

    return call, store


@pytest.mark.parametrize("mode", ["ui", "gui", "visible"])
def test_missing_permissions_preserve_ui_mode_for_after_the_grant(tmp_path, mode):
    presenter = FakePresenter(False, REMEDY)
    call, store = tools(tmp_path, presenter)
    out = call(mode)
    assert REMEDY in out
    assert presenter.requests == [True]
    assert store.get() == "ui"
    assert UiModeStore(tmp_path, environ={}).get() == "ui"


@pytest.mark.parametrize("mode", ["ui", "status", "get", ""])
def test_capture_remedy_is_shown_even_when_navigation_is_available(tmp_path, mode):
    presenter = FakePresenter(True, REMEDY)
    call, _ = tools(tmp_path, presenter)
    assert REMEDY in call(mode)
    assert presenter.requests == [mode == "ui"]


@pytest.mark.parametrize("mode", ["status", "get", "", "headless", "off", "sideways"])
def test_reading_status_headless_and_invalid_modes_never_request_permissions(tmp_path, mode):
    presenter = FakePresenter(False, REMEDY)
    call, store = tools(tmp_path, presenter)
    call(mode)
    assert not any(presenter.requests)
    assert store.get() == "headless"


def test_actual_presenter_status_reports_macos_grants_and_the_responsible_app(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from src.packet_tracer_mcp.infrastructure.platform import doctor
    from src.packet_tracer_mcp.infrastructure.platform.base import HostInfo
    from src.packet_tracer_mcp.infrastructure.ui.backends.macos import MacBackend, permissions
    from src.packet_tracer_mcp.infrastructure.ui.presenter import Presenter

    def forbidden_request(*args, **kwargs):
        raise AssertionError("Reading mode status must never request permission")

    monkeypatch.setattr(permissions, "pyobjc_missing", lambda: None)
    monkeypatch.setattr(permissions, "state", lambda: {
        "accessibility": False, "screen_recording": False, "post_events": False})
    monkeypatch.setattr(permissions, "request", forbidden_request)
    monkeypatch.setattr(doctor.host, "responsible_app", lambda *args, **kwargs: "Codex")
    monkeypatch.setattr(doctor.host, "responsible_bundle",
                        lambda *args, **kwargs: "/Applications/Codex.app")
    backend = MacBackend(responsible=lambda: ("Codex", "/Applications/Codex.app"))
    platform = SimpleNamespace(host=HostInfo("macos", "test", "arm64", "3.12"),
                               ui_backend=lambda: backend)
    monkeypatch.setattr(doctor, "current", lambda: platform)
    presenter = Presenter(lambda *args: None, backend=backend)
    call, _ = tools(tmp_path, presenter)
    out = call("status")
    diagnostics = json.loads(out.split("UI diagnostics: ", 1)[1].split("\n", 1)[0])
    assert diagnostics["backend"] == "macos"
    assert diagnostics["permissions"] == {"accessibility": False, "screen_recording": False}
    assert diagnostics["grant_to"] == "Codex"
    assert "Codex" in diagnostics["reason"] and "System Settings" in diagnostics["reason"]
