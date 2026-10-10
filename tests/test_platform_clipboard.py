"""Clipboard selection and the bytes each tool receives (PLAN/INTERFACES.md §1).

`pt_deploy` used to copy only on Windows (ISSUES X2). Each clipboard takes an
injected `run`, so these tests check the exact command, encoding and
environment without touching the real clipboard.
"""

from __future__ import annotations

import subprocess

import pytest

from src.packet_tracer_mcp.infrastructure.platform.clipboard import clipboard_for


class FakeRun:
    def __init__(self, exc: BaseException | None = None):
        self.calls: list[tuple[object, dict]] = []
        self.exc = exc

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc is not None:
            raise self.exc
        return subprocess.CompletedProcess(args, 0)


def which_from(*present: str):
    return lambda name: f"/usr/bin/{name}" if name in present else None


class TestSelection:
    def test_windows_uses_clip(self):
        assert clipboard_for("windows", which=which_from(), env={}, run=FakeRun()).name == "clip.exe"

    def test_macos_uses_pbcopy(self):
        assert clipboard_for("macos", which=which_from("pbcopy"), env={}, run=FakeRun()).name == "pbcopy"

    def test_macos_without_pbcopy_has_none(self):
        assert clipboard_for("macos", which=which_from(), env={}, run=FakeRun()).name == "none"

    def test_wayland_prefers_wl_copy(self):
        cb = clipboard_for("linux", which=which_from("wl-copy", "xclip"),
                           env={"WAYLAND_DISPLAY": "wayland-0"}, run=FakeRun())
        assert cb.name == "wl-copy"

    def test_wayland_without_wl_copy_falls_back_to_xclip(self):
        cb = clipboard_for("linux", which=which_from("xclip"),
                           env={"WAYLAND_DISPLAY": "wayland-0"}, run=FakeRun())
        assert cb.name == "xclip"

    def test_x11_ignores_wl_copy(self):
        cb = clipboard_for("linux", which=which_from("wl-copy", "xclip"), env={}, run=FakeRun())
        assert cb.name == "xclip"

    def test_xsel_is_the_last_resort(self):
        assert clipboard_for("linux", which=which_from("xsel"), env={}, run=FakeRun()).name == "xsel"

    def test_linux_without_tools_has_none(self):
        assert clipboard_for("linux", which=which_from(), env={}, run=FakeRun()).name == "none"


class TestCopy:
    def test_clip_keeps_todays_call(self):
        run = FakeRun()
        assert clipboard_for("windows", which=which_from(), env={}, run=run).copy("héllo") is True
        args, kwargs = run.calls[0]
        assert args == "clip"
        assert kwargs["input"] == "héllo".encode("utf-16-le")
        assert kwargs["check"] is True and kwargs["timeout"] == 5

    def test_pbcopy_sends_utf8_with_a_utf8_locale(self):
        run = FakeRun()
        cb = clipboard_for("macos", which=which_from("pbcopy"), env={"PATH": "/usr/bin"}, run=run)
        assert cb.copy("héllo") is True
        args, kwargs = run.calls[0]
        assert args == ["pbcopy"]
        assert kwargs["input"] == "héllo".encode("utf-8")
        # A GUI-launched process can lack a locale; pbcopy then mangles non-ASCII.
        assert kwargs["env"]["LC_CTYPE"] == "UTF-8"
        assert kwargs["env"]["PATH"] == "/usr/bin"

    @pytest.mark.parametrize("tool, argv", [
        ("wl-copy", ["wl-copy"]),
        ("xclip", ["xclip", "-selection", "clipboard"]),
        ("xsel", ["xsel", "--clipboard", "--input"]),
    ])
    def test_linux_tools_receive_utf8(self, tool, argv):
        run = FakeRun()
        env = {"WAYLAND_DISPLAY": "w"} if tool == "wl-copy" else {}
        cb = clipboard_for("linux", which=which_from(tool), env=env, run=run)
        assert cb.copy("héllo") is True
        assert run.calls[0][0] == argv
        assert run.calls[0][1]["input"] == "héllo".encode("utf-8")

    @pytest.mark.parametrize("exc", [
        subprocess.CalledProcessError(1, "pbcopy"), subprocess.TimeoutExpired("pbcopy", 5),
        FileNotFoundError("pbcopy"), OSError("broken pipe"),
    ])
    def test_a_failing_tool_returns_false(self, exc):
        cb = clipboard_for("macos", which=which_from("pbcopy"), env={}, run=FakeRun(exc))
        assert cb.copy("x") is False

    def test_no_clipboard_never_runs_anything(self):
        run = FakeRun()
        assert clipboard_for("linux", which=which_from(), env={}, run=run).copy("x") is False
        assert run.calls == []


class FakeClipboard:
    def __init__(self, name: str = "fake", ok: bool = True):
        self.name, self.ok, self.texts = name, ok, []

    def copy(self, text: str) -> bool:
        self.texts.append(text)
        return self.ok


def _with_clipboard(monkeypatch, tmp_path, clipboard):
    from src.packet_tracer_mcp.infrastructure import platform as pt_platform
    from src.packet_tracer_mcp.infrastructure.platform.base import HostInfo, Platform
    host = HostInfo(os="macos", os_version="26.5.1", arch="arm64", python="3.12.15")
    monkeypatch.setattr(pt_platform, "current",
                        lambda: Platform(host=host, state_dir=tmp_path, clipboard=clipboard))


class TestDeployUsesThePlatformClipboard:
    """ISSUES X2: `pt_deploy` copied only through clip.exe, so never on a Mac."""

    def test_the_topology_script_is_copied(self, tmp_path, monkeypatch):
        from src.packet_tracer_mcp.domain.models.requests import TopologyRequest
        from src.packet_tracer_mcp.domain.services.orchestrator import plan_from_request
        from src.packet_tracer_mcp.infrastructure.execution.deploy_executor import DeployExecutor
        fake = FakeClipboard()
        _with_clipboard(monkeypatch, tmp_path, fake)
        plan, _ = plan_from_request(TopologyRequest(routers=1, pcs_per_lan=1))
        result = DeployExecutor(output_dir=tmp_path).execute(plan, project_name="p")
        assert result["clipboard"] is True
        script = (tmp_path / "p" / "topology.js").read_text(encoding="utf-8")
        assert fake.texts == [script]

    @pytest.mark.parametrize("name, expected", [("pbcopy", True), ("none", False)])
    def test_is_available_reports_the_clipboard(self, tmp_path, monkeypatch, name, expected):
        from src.packet_tracer_mcp.infrastructure.execution.deploy_executor import DeployExecutor
        _with_clipboard(monkeypatch, tmp_path, FakeClipboard(name=name))
        assert DeployExecutor(output_dir=tmp_path).is_available() is expected
