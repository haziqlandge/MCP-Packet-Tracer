"""macOS privacy permissions (TCC) for UI mode: state, asking once, and the remedy.

Navigation needs Accessibility (the AX tree, AXPress) and posting events, which
macOS grants under the same Accessibility switch; capture also needs Screen
Recording. Checking uses the preflight APIs only and never shows a prompt
(CONSTRAINTS C3). Asking is `request()`, which only the UI-mode switch reaches.

The grant belongs to the app macOS holds responsible for the server, not to
Python: under Claude desktop's Code tab, the bundled Claude Code CLI at a
versioned path (PREVIOUS_WORK 2.4 #9), so the remedy names the full path. A
grant took effect in the running client without a restart (measured there).
pyobjc is imported inside the functions, so this module imports on every OS (C2).
"""

from __future__ import annotations

from pathlib import Path

PERMISSIONS = ("accessibility", "screen_recording", "post_events")
# System Settings → Privacy & Security → <pane> for each permission.
PANES = {
    "accessibility": "Accessibility",
    "post_events": "Accessibility",
    "screen_recording": "Screen & System Audio Recording",
}

_requested: set[str] = set()


def pyobjc_missing() -> str | None:
    """None when the pyobjc frameworks import, else the remedy."""
    try:
        import ApplicationServices  # noqa: F401
        import Quartz  # noqa: F401
    except ImportError as exc:
        return (f"pyobjc is missing ({exc}). It installs with packet-tracer-mcp on macOS: run "
                "`pip install --upgrade packet-tracer-mcp` in the server's environment. "
                "Every tool works headless meanwhile.")
    return None


def state() -> dict[str, bool]:
    """Which permissions this process has. Preflight only: never prompts."""
    import ApplicationServices as AS
    import Quartz
    return {
        "accessibility": bool(AS.AXIsProcessTrustedWithOptions({AS.kAXTrustedCheckOptionPrompt: False})),
        "screen_recording": bool(Quartz.CGPreflightScreenCaptureAccess()),
        "post_events": bool(Quartz.CGPreflightPostEventAccess()),
    }


def _request_one(name: str) -> None:
    import ApplicationServices as AS
    import Quartz
    if name == "accessibility":
        AS.AXIsProcessTrustedWithOptions({AS.kAXTrustedCheckOptionPrompt: True})
    elif name == "screen_recording":
        Quartz.CGRequestScreenCaptureAccess()
    elif name == "post_events":
        Quartz.CGRequestPostEventAccess()


def request(missing: list[str]) -> None:
    """Show the system prompt for each missing permission, at most once per
    process: a second dialog for the same thing in one session is noise."""
    for name in missing:
        if name in _requested:
            continue
        _requested.add(name)
        _request_one(name)


def reset_requests() -> None:
    """Forget what was asked. For tests only."""
    _requested.clear()


def _tilde(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home):] if home != "/" and path.startswith(home) else path


def remedy(missing: list[str], app: str | None, bundle: str | None = None) -> str:
    """What to switch on, where, and for which app. "" when nothing is missing."""
    if not missing:
        return ""
    panes = list(dict.fromkeys(PANES[m] for m in missing))
    who = app or "the app that runs this MCP server"
    where = f" ({_tilde(bundle)})" if bundle else ""
    route = " and ".join(f"Privacy & Security → {p}" for p in panes)
    return (f"UI mode needs {' and '.join(panes)} for {who}{where}. Open System Settings → "
            f"{route} and turn on {app or 'that app'} (if it is not listed, add it with + and "
            "press Cmd+Shift+G to paste its path). It takes effect at once, no restart needed. "
            "Every tool works headless meanwhile.")
