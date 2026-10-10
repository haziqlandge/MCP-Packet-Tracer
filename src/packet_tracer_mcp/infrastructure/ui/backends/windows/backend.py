"""WindowsBackend: `win32` and `Uia` behind `WindowBackend`, doing what they did.

Each call that touches UIA builds a `Uia()`, as the presenter did before the
seam: its constructor initialises COM on the calling thread, and tool calls run
on worker threads. The COM objects themselves are cached by `uia.py`.

Errors from `uia` (`UiaUnavailable`, COM errors) pass through unchanged, so the
notes the tools show on Windows read as they did.
"""

from __future__ import annotations

from ...backend import Capture, Role, UiElement, WindowHandle
from . import win32
from .uia import Element, Uia

# Role → the UIA control type name `Uia.descendants` filters on.
_UIA_TYPES = {
    Role.TAB: "TabItem", Role.BUTTON: "Button", Role.CHECKBOX: "CheckBox",
    Role.LIST_ITEM: "ListItem", Role.EDIT: "Edit", Role.SCROLLBAR: "ScrollBar",
    Role.STATIC: "Text", Role.WINDOW: "Window",
}


class WindowsBackend:
    name = "windows"

    def available(self, *, request: bool = False) -> tuple[bool, str]:
        """The GUI part needs Windows and comtypes. `request` has no effect here."""
        if not win32.is_supported():
            return False, "presenting in PT's GUI only works on Windows"
        try:
            import comtypes  # noqa: F401
        except ImportError:
            return False, ("'comtypes' is missing: install it with `pip install packet-tracer-mcp[ui]` "
                           "(or `pip install comtypes`)")
        return True, ""

    # -- windows ------------------------------------------------------------
    def find_window(self, pid: int, title: str) -> WindowHandle | None:
        return win32.find_window(pid, title)

    def main_window(self, pid: int) -> WindowHandle | None:
        return win32.main_window(pid)

    def raise_window(self, handle: WindowHandle) -> None:
        win32.raise_window(handle)

    def capture(self, handle: WindowHandle) -> Capture:
        w, h, bgra = win32.capture(handle)
        return Capture(w, h, bgra)

    def click(self, handle: WindowHandle, x: int, y: int) -> str:
        win32.post_click(handle, x, y)
        return "posted"

    # -- elements -------------------------------------------------------------
    def elements(self, handle: WindowHandle, role: Role | None = None) -> list[UiElement]:
        u = Uia()
        roles = {getattr(u.m, f"UIA_{t}ControlTypeId"): r for r, t in _UIA_TYPES.items()}
        uia_type = _UIA_TYPES.get(role) if role is not None else None
        els = [self._wrap(e, roles) for e in u.descendants(handle, uia_type)]
        if role is not None and uia_type is None:  # Role.OTHER: no UIA condition for it
            els = [e for e in els if e.role is role]
        return els

    @staticmethod
    def _wrap(e: Element, roles: dict[int, Role]) -> UiElement:
        return UiElement(raw=e, name=e.name, ident=e.automation_id,
                         role=roles.get(e.control_type, Role.OTHER),
                         offscreen=e.offscreen, bounds=e.rect)

    # -- actions (each unwraps the uia.Element kept as raw) -------------------
    def select(self, el: UiElement) -> None:
        Uia().select(el.raw)

    def press(self, el: UiElement) -> None:
        Uia().invoke(el.raw)

    def toggle_state(self, el: UiElement) -> int:
        return Uia().toggle_state(el.raw)

    def range_value(self, el: UiElement) -> float:
        return Uia().range_value(el.raw)

    def set_value(self, el: UiElement, text: str) -> None:
        Uia().set_value(el.raw, text)

    def scroll_to_end(self, el: UiElement) -> None:
        Uia().scroll_to_end(el.raw)
