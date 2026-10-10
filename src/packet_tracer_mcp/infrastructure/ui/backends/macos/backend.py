"""MacBackend: PT's windows, their capture and their navigation on macOS
(PLAN/phases/PHASE-04.md, PHASE-05.md).

Handles are CGWindowIDs (ints), found by joining PT's AX windows to its CG
windows. Elements come from the AX walk in `ax.py`; each keeps its AXUIElement
and window handle as `raw` (a `Ref`). Units: frames and clicks in points,
captures in pixels (C10).

Unlike Windows, macOS UI mode is not invisible (ISSUES X9): the canvas click
and a section switch bring PT to the front, and the click moves the cursor for
a moment before putting it back (`events.py`).
"""

from __future__ import annotations

import os
from typing import Callable, NamedTuple

from ...backend import BackendError, BackendUnavailable, Capture, Role, UiElement, WindowHandle
from . import ax
from . import capture as mac_capture
from . import events
from . import permissions
from . import windows


SECTION_TIMEOUT_S = 1.0


class Ref(NamedTuple):
    """An element's backend handle: its AXUIElement and the window it was read from."""
    el: object
    handle: int

# The two permissions UI mode checks; posting events comes with Accessibility.
_NEEDED = ("accessibility", "screen_recording")


def _responsible() -> tuple[str | None, str | None]:
    from ....platform.host import responsible_app, responsible_bundle
    pid = os.getpid()
    return responsible_app(pid), responsible_bundle(pid)


class MacBackend:
    name = "macos"

    def __init__(self, *, responsible: Callable[[], tuple[str | None, str | None]] | None = None,
                 io: events.EventIO | None = None):
        self._responsible = responsible or _responsible
        self._windows: dict[int, tuple[int, object]] = {}  # CGWindowID → (pid, AX window)
        self._mains: set[int] = set()                       # handles of PT's main window
        self._io = io or events.QuartzIO()
        self.last_route = ""                                # capture route used last

    # -- permissions ------------------------------------------------------------
    def _remedy(self, missing: list[str]) -> str:
        app, bundle = self._responsible()
        return permissions.remedy(missing, app, bundle)

    def _missing(self) -> list[str]:
        st = permissions.state()
        return [p for p in _NEEDED if not st.get(p)]

    def available(self, *, request: bool = False) -> tuple[bool, str]:
        """Usable when pyobjc imports and Accessibility is granted. A missing
        Screen Recording grant is reported but only blocks capture. `request`
        shows the system prompts, once each (C3: only pt_ui_mode("ui") asks)."""
        why = permissions.pyobjc_missing()
        if why:
            return False, why
        missing = self._missing()
        if missing and request:
            permissions.request(missing)
            missing = self._missing()
        if "accessibility" in missing:
            return False, self._remedy(missing)
        return True, self._remedy(missing)

    # -- windows ----------------------------------------------------------------
    def _remember(self, pid: int, found: tuple[int, object] | None) -> WindowHandle | None:
        if found is None:
            return None
        cg_id, ax_window = found
        self._windows[cg_id] = (pid, ax_window)
        return cg_id

    def find_window(self, pid: int, title: str) -> WindowHandle | None:
        return self._remember(pid, windows.find(pid, title))

    def main_window(self, pid: int) -> WindowHandle | None:
        handle = self._remember(pid, windows.find(pid, windows.MAIN_TITLE, prefix=True))
        if handle is not None:
            self._mains.add(handle)
        return handle

    def _entry(self, handle: WindowHandle) -> tuple[int, object]:
        entry = self._windows.get(handle)
        if entry is None:
            raise BackendError(f"window {handle} is unknown: find it first")
        return entry

    def raise_window(self, handle: WindowHandle) -> None:
        windows.raise_and_activate(*self._entry(handle))

    def capture(self, handle: WindowHandle) -> Capture:
        why = permissions.pyobjc_missing()
        if why:
            raise BackendUnavailable(why)
        if not permissions.state().get("screen_recording"):
            raise BackendUnavailable(self._remedy(["screen_recording"]))
        cap, self.last_route = mac_capture.capture_window(handle)
        return cap

    # -- navigation ---------------------------------------------------------------
    def click(self, handle: WindowHandle, x: int, y: int) -> str:
        pid, window = self._entry(handle)
        return events.click(pid, window, x, y, io=self._io)

    def elements(self, handle: WindowHandle, role: Role | None = None) -> list[UiElement]:
        _, window = self._entry(handle)
        tree, _ = ax.walk(window, with_actions=False, keep_el=True)
        els = ax.elements_from_tree(tree, raw=lambda node: Ref(node["_el"], handle))
        return [e for e in els if role is None or e.role is role]

    def _perform(self, el: UiElement, action: str) -> None:
        err = ax.perform(el.raw.el, action)
        if err:
            raise BackendError(f"{action} on '{el.name}' failed (AX error {err}).")

    def select(self, el: UiElement) -> None:
        self._perform(el, "AXPress")

    def press(self, el: UiElement) -> None:
        # A checkable button in a device dialog is a Config/Services section:
        # AXPress only flips its check there, so it is switched from the
        # keyboard. The main window's tool buttons (Select) take AXPress.
        if el.role is Role.CHECKBOX and el.raw.handle not in self._mains:
            self._switch_section(el)
            return
        self._perform(el, "AXPress")

    def _switch_section(self, el: UiElement) -> None:
        """The checked section is the one shown; its check follows the key press
        by ~0.15 s (measured), so it is polled before giving up."""
        if self.toggle_state(el) == 1:
            return
        pid, _ = self._entry(el.raw.handle)
        events.press_by_keyboard(pid, el.raw.el, io=self._io)
        waited = 0.0
        while self.toggle_state(el) != 1:
            if waited >= SECTION_TIMEOUT_S:
                raise BackendError(f"PT did not switch to '{el.name}'. It must stay the frontmost "
                                   "app while the section changes.")
            self._io.sleep(0.1)
            waited += 0.1

    def toggle_state(self, el: UiElement) -> int:
        v = ax.attr(el.raw.el, "AXValue")
        return int(v) if v is not None else 0

    def range_value(self, el: UiElement) -> float:
        v = ax.attr(el.raw.el, "AXValue")
        return float(v) if v is not None else 0.0

    def set_value(self, el: UiElement, text: str) -> None:
        err = ax.set_attr(el.raw.el, "AXValue", text)
        if err:  # Qt may want the field focused first
            ax.set_attr(el.raw.el, "AXFocused", True)
            err = ax.set_attr(el.raw.el, "AXValue", text)
        if err:
            raise BackendError(f"could not type into '{el.name}' (AX error {err}).")

    def scroll_to_end(self, el: UiElement) -> None:
        if el.role is not Role.SCROLLBAR:
            raise BackendError(f"'{el.name or el.ident}' is not a scroll bar.")
        top = ax.attr(el.raw.el, "AXMaxValue")
        err = ax.set_attr(el.raw.el, "AXValue", top) if top is not None else -1
        if err:
            raise BackendError(f"could not scroll '{el.ident}' (AX error {err}).")
