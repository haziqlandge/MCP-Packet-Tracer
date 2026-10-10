"""load_backend per OS, the PT_MCP_UI_BACKEND override, and NullBackend (INTERFACES.md §2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.packet_tracer_mcp.infrastructure.platform.base import HostInfo, Platform
from src.packet_tracer_mcp.infrastructure.ui.backend import BackendUnavailable, Role
from src.packet_tracer_mcp.infrastructure.ui.backends import load_backend
from src.packet_tracer_mcp.infrastructure.ui.backends.null import NullBackend

LINUX = "UI mode is not available on Linux yet; every tool works headless. See PHASE-08."


def test_windows_gets_the_windows_backend():
    assert load_backend("windows", env={}).name == "windows"


def test_linux_gets_the_null_backend_with_its_reason():
    b = load_backend("linux", env={})
    assert b.name == "null"
    assert b.available() == (False, LINUX)


def test_macos_gets_the_macos_backend():
    # PHASE-04: the null placeholder is replaced by MacBackend. Building it
    # imports no pyobjc, so this holds on every OS (C2).
    assert load_backend("macos", env={}).name == "macos"


def test_macos_import_failure_is_null_with_the_error_and_the_fix(monkeypatch):
    monkeypatch.setitem(sys.modules, "src.packet_tracer_mcp.infrastructure.ui.backends.macos", None)
    b = load_backend("macos", env={})
    why = b.available()[1]
    assert b.name == "null" and "macos" in why and "pip install" in why


def test_unknown_os_is_null():
    b = load_backend("other", env={})
    assert b.name == "null" and "headless" in b.available()[1]


def test_the_os_defaults_to_the_running_host(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert load_backend(env={}).available() == (False, LINUX)


@pytest.mark.parametrize("os_name", ["windows", "macos", "linux"])
def test_override_null(os_name):
    b = load_backend(os_name, env={"PT_MCP_UI_BACKEND": "null"})
    assert b.name == "null" and "PT_MCP_UI_BACKEND" in b.available()[1]


def test_override_picks_a_backend_on_another_os():
    assert load_backend("linux", env={"PT_MCP_UI_BACKEND": " Windows "}).name == "windows"


def test_unknown_override_is_null_and_names_the_choices():
    b = load_backend("windows", env={"PT_MCP_UI_BACKEND": "wayland"})
    why = b.available()[1]
    assert b.name == "null" and "'wayland'" in why
    assert all(c in why for c in ("null", "windows", "macos", "linux"))


def test_import_failure_is_null_with_the_error_and_the_fix(monkeypatch):
    pkg = "src.packet_tracer_mcp.infrastructure.ui.backends.windows"
    monkeypatch.setitem(sys.modules, pkg, None)
    b = load_backend("windows", env={})
    why = b.available()[1]
    assert b.name == "null"
    assert "windows" in why and "pip install" in why


class TestNullBackend:
    def test_available_never_prompts_and_says_why(self):
        assert NullBackend("because").available(request=True) == (False, "because")

    @pytest.mark.parametrize("call", [
        lambda b: b.find_window(1, "PC1"), lambda b: b.main_window(1),
        lambda b: b.raise_window(1), lambda b: b.capture(1), lambda b: b.click(1, 2, 3),
        lambda b: b.elements(1), lambda b: b.elements(1, Role.TAB),
        lambda b: b.select(None), lambda b: b.press(None), lambda b: b.toggle_state(None),
        lambda b: b.range_value(None), lambda b: b.set_value(None, "x"),
        lambda b: b.scroll_to_end(None),
    ])
    def test_every_operation_raises_the_reason(self, call):
        with pytest.raises(BackendUnavailable, match="^because$"):
            call(NullBackend("because"))


class TestPlatformUiBackend:
    def _platform(self, os_name):
        return Platform(host=HostInfo(os_name, "1", "arm64", "3.12"), state_dir=Path("/tmp"),
                        clipboard=None)

    def test_built_for_the_platform_os_and_cached(self, monkeypatch):
        monkeypatch.delenv("PT_MCP_UI_BACKEND", raising=False)
        p = self._platform("linux")
        b = p.ui_backend()
        assert b.available() == (False, LINUX)
        assert p.ui_backend() is b

    def test_platform_equality_ignores_the_cache(self, monkeypatch):
        monkeypatch.delenv("PT_MCP_UI_BACKEND", raising=False)
        a, b = self._platform("linux"), self._platform("linux")
        a.ui_backend()
        assert a == b
