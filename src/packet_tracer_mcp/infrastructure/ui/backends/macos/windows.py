"""PT's windows on macOS: the AX list, the CG list, and the join between them.

Accessibility gives titles and frames; Core Graphics gives the CGWindowID, the
JSON-safe handle the presenter passes around, and capture needs. A window is the
same in both when the frames match (points, ±1 for rounding). Frames alone are
ambiguous: PT opens every device dialog at the same frame and keeps hidden twins
of some windows (PREVIOUS_WORK 2.4 #7), so a CG name equal to the AX title wins
(names are readable only with Screen Recording), then an on-screen window, then
the frontmost. The join is pure; the pyobjc readers below it are not. Every
name used here was exercised by `devtools/macos_probe.py` first (C6).
"""

from __future__ import annotations

import time

from .ax import attr as ax_attr, frame as ax_frame

TOLERANCE = 1.0
MAIN_TITLE = "Cisco Packet Tracer"  # the main window's title prefix, as on Windows
_AX_TIMEOUT_S = 3.0


# -- pure -----------------------------------------------------------------------

def frames_match(a, b, tol: float = TOLERANCE) -> bool:
    return (a is not None and b is not None and len(a) == 4 and len(b) == 4
            and all(abs(x - y) <= tol for x, y in zip(a, b)))


def join_window(frame, cg: list[dict], title: str = "") -> int | None:
    """CGWindowID of the CG window (layer 0, front to back) matching an AX frame."""
    if frame is None:
        return None
    same = [w for w in cg if w.get("layer", 0) == 0 and frames_match(frame, w["frame"])]
    same.sort(key=lambda w: (not (title and w.get("name") == title), not w.get("onscreen", False)))
    return same[0]["cg_id"] if same else None


def title_matches(ax_title: str, wanted: str, *, prefix: bool = False) -> bool:
    """Dialogs match exactly ("R10" is not "R1"); the main window by prefix."""
    return ax_title.startswith(wanted) if prefix else ax_title == wanted


# -- pyobjc readers -------------------------------------------------------------

def _quartz():
    import Quartz
    return Quartz


def _ax():
    import ApplicationServices
    return ApplicationServices


def cg_windows(pid: int) -> list[dict]:
    """PT's CG windows, front to back. Names are empty without Screen Recording."""
    Q = _quartz()
    out = []
    for w in Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionAll, Q.kCGNullWindowID) or []:
        if int(w.get(Q.kCGWindowOwnerPID, -1)) != pid:
            continue
        b = w.get(Q.kCGWindowBounds) or {}
        out.append({
            "cg_id": int(w[Q.kCGWindowNumber]),
            "name": str(w.get(Q.kCGWindowName) or ""),
            "layer": int(w.get(Q.kCGWindowLayer, 0)),
            "onscreen": bool(w.get(Q.kCGWindowIsOnscreen, False)),
            "frame": [float(b.get("X", 0)), float(b.get("Y", 0)),
                      float(b.get("Width", 0)), float(b.get("Height", 0))],
        })
    return out


def ax_windows(pid: int) -> list[tuple[object, str, list[float] | None]]:
    """(AX window, title, frame) for each of PT's windows.

    PT's AX window list sometimes reads empty for a moment (seen repeatedly while
    its dialogs opened), so an empty answer is retried before it is believed.
    """
    AS = _ax()
    app = AS.AXUIElementCreateApplication(pid)
    AS.AXUIElementSetMessagingTimeout(app, _AX_TIMEOUT_S)
    for attempt in range(3):
        wins = ax_attr(app, "AXWindows") or []
        if wins:
            return [(w, str(ax_attr(w, "AXTitle") or ""), ax_frame(w)) for w in wins]
        time.sleep(0.15)
    return []


def find(pid: int, title: str, *, prefix: bool = False) -> tuple[int, object] | None:
    """(CGWindowID, AX window) of PT's window titled `title`, or None."""
    cg = cg_windows(pid)
    for el, t, frame in ax_windows(pid):
        if title_matches(t, title, prefix=prefix):
            cg_id = join_window(frame, cg, t)
            if cg_id is not None:
                return cg_id, el
    return None


def raise_and_activate(pid: int, ax_window) -> None:
    """Bring the window to the front of PT, then PT to the front."""
    _ax().AXUIElementPerformAction(ax_window, "AXRaise")
    from AppKit import NSRunningApplication
    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if app is not None:
        app.activateWithOptions_(0)
