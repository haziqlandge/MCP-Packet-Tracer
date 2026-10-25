"""Clicks and key presses into PT on macOS, by the only routes that worked.

PHASE-00 (PREVIOUS_WORK 2.4 #6, #7), measured on PT 9.0.1 / macOS 26.5.1:

- Mouse events posted to PT's pid never open a device dialog (5 variants). What
  works is a click at HID level with PT frontmost: activate PT, `AXRaise` its
  main window, `CGEventPost(kCGHIDEventTap)` down/up, then warp the cursor back.
  The cursor moves for a moment, so the route reports "cursor-restored".
- A checkable button (Config/Services sections) ignores `AXPress` as a click:
  Qt maps it to `toggle()`. Focusing it and posting Space to PT's pid switches
  the panel, but only while PT is frontmost.

A HID click lands on whatever is on top, so `click` refuses unless PT is
frontmost and the point hits PT's logical canvas. Every pyobjc name here was
exercised by `devtools/macos_probe.py` first (C6); they are imported inside
`QuartzIO`, so this module imports on every OS (C2).

Activation (ISSUES X18, measured 2026-10-24 on macOS 26.6): from a background
process such as the MCP server under the Claude Code helper,
`activateWithOptions_` can leave the other app in front (2 of 2 tries), while
LaunchServices (`open -a` on PT's own bundle) brought PT forward 3 of 3. So
`_wait_front` falls back to it once if PT is not in front shortly. Whether PT
is in front is read from its `AXFrontmost`, live (see `QuartzIO.is_frontmost`).
"""

from __future__ import annotations

import subprocess
import time
from typing import Callable, Protocol

from ...backend import BackendError

KEY_SPACE = 49            # kVK_Space
CANVAS_IDENT = "m_pViewArea_Window.m_workspaceWS"
ACTIVATE_GRACE_S = 0.5    # activateWithOptions_ took ~0.4 s in PHASE-00
FRONT_TIMEOUT_S = 3.0     # in all, including the LaunchServices fallback
# PT reports frontmost before its windows are raised over the others (measured
# live): the point is hit-tested again until PT's canvas is on top.
HIT_TIMEOUT_S = 1.0
_POLL_S = 0.1
_HIT_DEPTH = 12           # parents climbed from the hit element


class EventIO(Protocol):
    def activate(self, pid: int) -> None: ...
    def open_app(self, pid: int) -> None: ...
    def raise_window(self, ax_window) -> None: ...
    def is_frontmost(self, pid: int) -> bool: ...
    def hit_idents(self, x: float, y: float) -> list[str]: ...
    def cursor(self) -> tuple[float, float]: ...
    def post_click(self, x: float, y: float) -> None: ...
    def warp(self, x: float, y: float) -> None: ...
    def focus(self, el) -> int: ...
    def key_to_pid(self, pid: int, keycode: int) -> None: ...
    def sleep(self, seconds: float) -> None: ...


def _wait_front(pid: int, io: EventIO, what: str) -> None:
    waited = 0.0
    opened = False
    while not io.is_frontmost(pid):
        if not opened and waited >= ACTIVATE_GRACE_S:
            io.open_app(pid)
            opened = True
        if waited >= FRONT_TIMEOUT_S:
            raise BackendError(f"Packet Tracer is not the frontmost app, so the {what} was not sent "
                               "(macOS delivers it to whatever is in front).")
        io.sleep(_POLL_S)
        waited += _POLL_S


def click(pid: int, main_ax_window, x: float, y: float, *, io: EventIO | None = None,
          ready: Callable[[], str | None] | None = None) -> str:
    """Left click at a screen point (points) on PT's canvas. Returns "cursor-restored".

    `ready` runs with PT in front, right before the click is posted; a string
    from it is the reason not to click (the canvas tool, ISSUES X20)."""
    io = io or QuartzIO()
    io.activate(pid)
    io.raise_window(main_ax_window)
    _wait_front(pid, io, "click")
    waited = 0.0
    while True:
        idents = io.hit_idents(x, y)
        if any(i.endswith(CANVAS_IDENT) for i in idents):
            break
        if waited >= HIT_TIMEOUT_S:
            top = next((i for i in idents if i), "nothing")
            raise BackendError(f"another window covers PT's canvas at ({x:.0f}, {y:.0f}) "
                               f"({top[-60:]}); not clicking. Move or close it and try again.")
        io.sleep(_POLL_S)
        waited += _POLL_S
    why = ready() if ready is not None else None
    if why:
        raise BackendError(why)
    saved = io.cursor()
    try:
        io.post_click(x, y)
        io.sleep(0.05)
    finally:
        io.warp(*saved)
    return "cursor-restored"


def press_by_keyboard(pid: int, ax_el, *, io: EventIO | None = None) -> None:
    """Focus a checkable button and press Space in PT (switches a section)."""
    io = io or QuartzIO()
    io.activate(pid)
    _wait_front(pid, io, "key press")
    err = io.focus(ax_el)
    if err:
        raise BackendError(f"could not focus the button (AX error {err}).")
    io.key_to_pid(pid, KEY_SPACE)


class QuartzIO:
    """The real event routes (pyobjc), as the probe exercised them."""

    def activate(self, pid: int) -> None:
        from AppKit import NSRunningApplication
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is not None:
            app.activateWithOptions_(0)

    def open_app(self, pid: int) -> None:
        """Activate the running PT through LaunchServices (`open -a` its bundle)."""
        from AppKit import NSRunningApplication
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        url = app.bundleURL() if app is not None else None
        if url is None:
            return
        try:
            subprocess.run(["open", "-a", str(url.path())], capture_output=True,
                           timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            pass  # _wait_front still refuses unless PT comes to the front

    def raise_window(self, ax_window) -> None:
        from . import ax
        ax.perform(ax_window, "AXRaise")

    def is_frontmost(self, pid: int) -> bool:
        # Not NSWorkspace.frontmostApplication(): in a process that runs no
        # AppKit event loop (the MCP server) its answer is cached, measured
        # stuck on one app while focus moved twice (2026-10-24). PT's own
        # AXFrontmost followed every move.
        from . import ax
        return bool(ax.attr(ax._as().AXUIElementCreateApplication(pid), "AXFrontmost"))

    def hit_idents(self, x: float, y: float) -> list[str]:
        """Idents of the element at (x, y) and of its parents, innermost first."""
        import ApplicationServices as AS
        from . import ax
        err, el = AS.AXUIElementCopyElementAtPosition(AS.AXUIElementCreateSystemWide(), x, y, None)
        out: list[str] = []
        for _ in range(_HIT_DEPTH):
            if err != 0 or el is None:
                break
            out.append(str(ax.attr(el, "AXIdentifier") or ""))
            el = ax.attr(el, "AXParent")
        return out

    def cursor(self) -> tuple[float, float]:
        import Quartz as Q
        loc = Q.CGEventGetLocation(Q.CGEventCreate(None))
        return float(loc.x), float(loc.y)

    def post_click(self, x: float, y: float) -> None:
        import Quartz as Q
        for kind in (Q.kCGEventLeftMouseDown, Q.kCGEventLeftMouseUp):
            Q.CGEventPost(Q.kCGHIDEventTap,
                          Q.CGEventCreateMouseEvent(None, kind, (x, y), Q.kCGMouseButtonLeft))

    def warp(self, x: float, y: float) -> None:
        import Quartz as Q
        Q.CGWarpMouseCursorPosition((x, y))

    def focus(self, el) -> int:
        from . import ax
        return ax.set_attr(el, "AXFocused", True)

    def key_to_pid(self, pid: int, keycode: int) -> None:
        import Quartz as Q
        for down in (True, False):
            Q.CGEventPostToPid(pid, Q.CGEventCreateKeyboardEvent(None, keycode, down))

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
