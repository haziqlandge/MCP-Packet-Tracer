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
"""

from __future__ import annotations

import time
from typing import Protocol

from ...backend import BackendError

KEY_SPACE = 49            # kVK_Space
CANVAS_IDENT = "m_pViewArea_Window.m_workspaceWS"
FRONT_TIMEOUT_S = 1.5     # activation took ~0.4 s in PHASE-00
# PT reports frontmost before its windows are raised over the others (measured
# live): the point is hit-tested again until PT's canvas is on top.
HIT_TIMEOUT_S = 1.0
_POLL_S = 0.1
_HIT_DEPTH = 12           # parents climbed from the hit element


class EventIO(Protocol):
    def activate(self, pid: int) -> None: ...
    def raise_window(self, ax_window) -> None: ...
    def frontmost_pid(self) -> int | None: ...
    def hit_idents(self, x: float, y: float) -> list[str]: ...
    def cursor(self) -> tuple[float, float]: ...
    def post_click(self, x: float, y: float) -> None: ...
    def warp(self, x: float, y: float) -> None: ...
    def focus(self, el) -> int: ...
    def key_to_pid(self, pid: int, keycode: int) -> None: ...
    def sleep(self, seconds: float) -> None: ...


def _wait_front(pid: int, io: EventIO, what: str) -> None:
    waited = 0.0
    while io.frontmost_pid() != pid:
        if waited >= FRONT_TIMEOUT_S:
            raise BackendError(f"Packet Tracer is not the frontmost app, so the {what} was not sent "
                               "(macOS delivers it to whatever is in front).")
        io.sleep(_POLL_S)
        waited += _POLL_S


def click(pid: int, main_ax_window, x: float, y: float, *, io: EventIO | None = None) -> str:
    """Left click at a screen point (points) on PT's canvas. Returns "cursor-restored"."""
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

    def raise_window(self, ax_window) -> None:
        from . import ax
        ax.perform(ax_window, "AXRaise")

    def frontmost_pid(self) -> int | None:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return int(app.processIdentifier()) if app is not None else None

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
