"""The seam between the presenter and an OS's window automation (PLAN/INTERFACES.md §2).

The presenter speaks only `WindowBackend`; each OS has its backend under
`backends/`. Elements carry Qt's objectName path as `ident` (UIA's
AutomationId on Windows, AXIdentifier on macOS), which `locators.py` matches.

Units (CONSTRAINTS C10): `rect` and `click` use the backend's screen units
(Windows: physical pixels; macOS: points). `Capture` is always in pixels. The
presenter never mixes the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol, Union

Rect = tuple[int, int, int, int]  # left, top, right, bottom
WindowHandle = int                # Windows: HWND. macOS: CGWindowID. JSON-safe on purpose


class Role(str, Enum):
    TAB = "tab"
    BUTTON = "button"
    CHECKBOX = "checkbox"
    LIST_ITEM = "list_item"
    EDIT = "edit"
    SCROLLBAR = "scrollbar"
    STATIC = "static"
    WINDOW = "window"
    OTHER = "other"


@dataclass(eq=False)
class UiElement:
    raw: object        # backend handle; never leaves the backend and the presenter
    name: str          # visible text
    ident: str         # Qt objectName path; "" when the platform does not expose it
    role: Role
    offscreen: bool
    # The rect, or a function that reads it. UIA reads each rect cross-process,
    # and the presenter needs only the canvas's, so the Windows backend passes
    # the reader and the rect is read when asked for.
    bounds: Union[Rect, Callable[[], Rect]]

    @property
    def rect(self) -> Rect:
        b = self.bounds
        return b() if callable(b) else b


@dataclass(frozen=True)
class Capture:
    width: int    # pixels
    height: int   # pixels
    bgra: bytes   # width*4 bytes per row, top-down, B,G,R,A (png.bgra_to_png input)


class BackendUnavailable(RuntimeError):
    """The backend cannot run here. str() is the actionable remedy (C7)."""


class BackendError(RuntimeError):
    """An operation failed: the element is gone, or the action was refused."""


class WindowBackend(Protocol):
    name: str  # "windows" | "macos" | "linux" | "null"

    def available(self, *, request: bool = False) -> tuple[bool, str]:
        """(available, reason). `request=True` may show OS permission prompts;
        only UI-mode entry points pass it (C3)."""
        ...

    def find_window(self, pid: int, title: str) -> WindowHandle | None: ...
    def main_window(self, pid: int) -> WindowHandle | None: ...
    def raise_window(self, handle: WindowHandle) -> None: ...
    def capture(self, handle: WindowHandle) -> Capture: ...

    def click(self, handle: WindowHandle, x: int, y: int) -> str:
        """Left click at a screen point. Returns how: "posted" (the cursor did not
        move) or "cursor-restored"."""
        ...

    def elements(self, handle: WindowHandle, role: Role | None = None) -> list[UiElement]: ...
    def select(self, el: UiElement) -> None: ...         # a tab
    def press(self, el: UiElement) -> None: ...          # button, list item, checkbox, toggle
    def toggle_state(self, el: UiElement) -> int: ...    # 0 off, 1 on, 2 indeterminate
    def range_value(self, el: UiElement) -> float: ...
    def set_value(self, el: UiElement, text: str) -> None: ...
    def scroll_to_end(self, el: UiElement) -> None: ...
