"""macOS permissions: the remedy text, ask-once requests and `MacBackend.available`.

Runs on every OS: the pyobjc calls are patched out, so only the decisions are
tested. What the grants do on a real Mac is in PREVIOUS_WORK 2.4 #9 (they take
effect in the running client, no restart).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.packet_tracer_mcp.infrastructure.ui.backend import BackendUnavailable
from src.packet_tracer_mcp.infrastructure.ui.backends.macos import permissions
from src.packet_tracer_mcp.infrastructure.ui.backends.macos.backend import MacBackend

HOME = str(Path.home())
CLI = f"{HOME}/Library/Application Support/Claude/claude-code/2.1.293/8433d0d9cd0d/claude.app"
SR = "Screen & System Audio Recording"


class TestRemedy:
    def test_both_missing_names_both_panes_and_the_app(self):
        r = permissions.remedy(["accessibility", "screen_recording"], "claude", CLI)
        assert "Accessibility" in r and SR in r
        assert "System Settings" in r and "Privacy & Security" in r
        assert "claude" in r
        # The CLI's path is versioned: the remedy names all of it, home as ~.
        assert "~/Library/Application Support/Claude/claude-code/2.1.293/8433d0d9cd0d/claude.app" in r
        if HOME != "/":
            assert HOME not in r

    def test_only_screen_recording(self):
        r = permissions.remedy(["screen_recording"], "Claude", None)
        assert SR in r and "Accessibility" not in r and "Claude" in r

    def test_only_accessibility(self):
        r = permissions.remedy(["accessibility"], "Terminal", None)
        assert "Accessibility" in r and SR not in r

    def test_posting_events_is_granted_under_accessibility(self):
        r = permissions.remedy(["post_events"], "Claude", None)
        assert "Accessibility" in r and SR not in r

    def test_an_unknown_app_is_described(self):
        r = permissions.remedy(["accessibility"], None, None)
        assert "the app that runs this MCP server" in r

    def test_says_no_restart_is_needed(self):
        # Measured on the executor Mac (PREVIOUS_WORK 2.4 #9).
        assert "no restart" in permissions.remedy(["screen_recording"], "claude", CLI)

    def test_nothing_missing_needs_no_remedy(self):
        assert permissions.remedy([], "claude", CLI) == ""


class TestRequestOnce:
    def test_each_permission_is_requested_at_most_once_per_process(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(permissions, "_request_one", calls.append)
        permissions.reset_requests()
        permissions.request(["accessibility", "screen_recording"])
        permissions.request(["accessibility", "screen_recording"])
        permissions.request(["screen_recording"])
        assert calls == ["accessibility", "screen_recording"]
        permissions.reset_requests()


@pytest.fixture
def mac(monkeypatch):
    """A MacBackend whose OS calls are fakes: `granted` is the TCC state, and a
    request grants what it asks for when `grant_on_request` is set."""
    granted = {"accessibility": False, "screen_recording": False, "post_events": False}
    calls: list[str] = []
    ctl = {"grant_on_request": False}

    def request_one(p):
        calls.append(p)
        if ctl["grant_on_request"]:
            granted[p] = True

    monkeypatch.setattr(permissions, "pyobjc_missing", lambda: None)
    monkeypatch.setattr(permissions, "state", lambda: dict(granted))
    monkeypatch.setattr(permissions, "_request_one", request_one)
    permissions.reset_requests()
    backend = MacBackend(responsible=lambda: ("claude", CLI))
    yield backend, granted, calls, ctl
    permissions.reset_requests()


class TestAvailable:
    def test_everything_granted(self, mac):
        backend, granted, calls, _ = mac
        granted.update(accessibility=True, screen_recording=True, post_events=True)
        assert backend.available() == (True, "")

    def test_without_accessibility_it_is_unavailable_with_the_remedy(self, mac):
        backend, granted, calls, _ = mac
        granted.update(screen_recording=True)
        ok, why = backend.available()
        assert not ok and "Accessibility" in why and "claude" in why

    def test_only_screen_recording_missing_still_navigates(self, mac):
        backend, granted, calls, _ = mac
        granted.update(accessibility=True, post_events=True)
        ok, why = backend.available()
        assert ok and SR in why

    def test_a_check_never_prompts(self, mac):
        backend, granted, calls, _ = mac
        backend.available()
        backend.available()
        assert calls == []

    def test_a_request_prompts_then_checks_again(self, mac):
        backend, granted, calls, ctl = mac
        ctl["grant_on_request"] = True
        assert backend.available(request=True) == (True, "")
        assert set(calls) == {"accessibility", "screen_recording"}

    def test_pyobjc_missing_gives_the_install_remedy(self, monkeypatch):
        monkeypatch.setattr(permissions, "pyobjc_missing", lambda: "pyobjc is missing: pip install x")
        monkeypatch.setattr(permissions, "state", lambda: pytest.fail("state() must not run"))
        assert MacBackend(responsible=lambda: (None, None)).available() == \
            (False, "pyobjc is missing: pip install x")

    def test_capture_without_screen_recording_raises_its_remedy(self, mac):
        backend, granted, calls, _ = mac
        granted.update(accessibility=True, post_events=True)
        with pytest.raises(BackendUnavailable) as exc:
            backend.capture(1234)
        assert SR in str(exc.value) and "Accessibility" not in str(exc.value)
