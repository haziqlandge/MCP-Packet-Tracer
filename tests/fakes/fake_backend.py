"""A scripted WindowBackend for presenter tests (PLAN/phases/PHASE-03.md).

Windows are a title → handle map; each handle's elements are a list or a
function of the backend (for trees that change, like closing an applet). Every
action is appended to `log`, so a test can assert what was clicked, pressed or
typed, and above all what was NOT.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Callable

from src.packet_tracer_mcp.infrastructure.ui.backend import (
    BackendUnavailable, Capture, Role, UiElement,
)


def el(name: str = "", ident: str = "", role: Role = Role.OTHER, *, offscreen: bool = False,
       rect: tuple[int, int, int, int] = (0, 0, 10, 10), toggle: int | None = None,
       sticky: bool = False, value: float = 0.0, on_press: Callable | None = None,
       fail: bool = False) -> UiElement:
    """An element. `toggle` is its toggle state; `sticky` means pressing it does
    not change that state (a tool PT refuses to switch). `fail` makes
    scroll_to_end raise."""
    raw = SimpleNamespace(toggle=toggle, sticky=sticky, value=value, on_press=on_press, fail=fail)
    return UiElement(raw=raw, name=name, ident=ident, role=role, offscreen=offscreen, bounds=rect)


class FakeBackend:
    name = "fake"

    def __init__(self, *, available: tuple[bool, str] = (True, ""), main: int | None = None,
                 windows: dict[str, int] | None = None,
                 trees: dict[int, list[UiElement] | Callable[["FakeBackend"], list[UiElement]]] | None = None,
                 capture: Capture | None = None, click_opens: dict | None = None,
                 click_result: str = "posted", unavailable_on: str = ""):
        self._available = available
        self.main = main
        self.windows = dict(windows or {})
        self.trees = dict(trees or {})
        self.cap = capture
        # point (x, y) → (title, handle): a click there opens that dialog
        self.click_opens = dict(click_opens or {})
        self.click_result = click_result
        self.unavailable_on = unavailable_on
        self.log: list[tuple] = []
        self.requests: list[bool] = []

    def _check(self, op: str) -> None:
        if op == self.unavailable_on:
            raise BackendUnavailable(f"{op}: grant it in System Settings")

    def available(self, *, request: bool = False) -> tuple[bool, str]:
        self.requests.append(request)
        return self._available

    def find_window(self, pid: int, title: str) -> int | None:
        self._check("find_window")
        return self.windows.get(title)

    def main_window(self, pid: int) -> int | None:
        return self.main

    def raise_window(self, handle: int) -> None:
        self.log.append(("raise", handle))

    def capture(self, handle: int) -> Capture:
        self._check("capture")
        self.log.append(("capture", handle))
        return self.cap

    def click(self, handle: int, x: int, y: int) -> str:
        self.log.append(("click", handle, x, y))
        if (x, y) in self.click_opens:
            title, h = self.click_opens[(x, y)]
            self.windows[title] = h
        return self.click_result

    def elements(self, handle: int, role: Role | None = None) -> list[UiElement]:
        tree = self.trees.get(handle, [])
        els = tree(self) if callable(tree) else list(tree)
        return [e for e in els if role is None or e.role is role]

    def select(self, e: UiElement) -> None:
        self.log.append(("select", e.name))

    def press(self, e: UiElement) -> None:
        # Elements from recorded fixtures carry their node dict as raw: no state.
        self.log.append(("press", e.name or e.ident.rsplit(".", 1)[-1]))
        if getattr(e.raw, "toggle", None) is not None and not e.raw.sticky:
            e.raw.toggle = 1 - e.raw.toggle
        if getattr(e.raw, "on_press", None):
            e.raw.on_press(self, e)

    def toggle_state(self, e: UiElement) -> int:
        return e.raw.toggle

    def range_value(self, e: UiElement) -> float:
        return e.raw.value

    def set_value(self, e: UiElement, text: str) -> None:
        self.log.append(("set_value", e.ident.rsplit(".", 1)[-1], text))

    def scroll_to_end(self, e: UiElement) -> None:
        if e.raw.fail:
            raise RuntimeError("no RangeValue")
        self.log.append(("scroll_to_end", e.ident))
