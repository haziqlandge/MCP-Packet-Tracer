"""How the presenter finds PT's widgets, as data (PLAN/INTERFACES.md §3).

Each `by_ident` is the presenter's predicate at `bcb2ef3`, moved verbatim. It
runs on elements that carry an ident (Qt's objectName path); `by_shape` runs on
elements without one. With an empty ident and no `by_shape` there is no match.

When that finds nothing at all, `by_shape` gets a second pass over every
element: on macOS PT exposes some widgets under a different objectName (the
logical canvas is `...m_pViewArea_Window.m_workspaceWS`, not
`CLogicalWorkspace.QWidget`). The second pass never runs when the first found
something, so what Windows matched before stays exactly what it matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .backend import Role, UiElement


@dataclass(frozen=True)
class Locator:
    key: str
    by_ident: Callable[[UiElement], bool]
    by_shape: Callable[[UiElement, list[UiElement]], bool] | None = None


def _matches(el: UiElement, els: list[UiElement], loc: Locator) -> bool:
    if el.ident:
        return loc.by_ident(el)
    return loc.by_shape is not None and loc.by_shape(el, els)


def locate_all(els: list[UiElement], loc: Locator) -> list[UiElement]:
    hits = [e for e in els if _matches(e, els, loc)]
    if hits or loc.by_shape is None:
        return hits
    # Nothing matched: the platform may name the widget differently.
    return [e for e in els if e.ident and loc.by_shape(e, els)]


def locate(els: list[UiElement], loc: Locator) -> UiElement | None:
    hits = locate_all(els, loc)
    return hits[0] if hits else None


# Title bars of the Desktop apps. PT 9.0.1 uses two variants (seen through
# UIA, and identical through AX on macOS): Command Prompt →
# m_titleBar.m_titleLabel / m_closeButton; Firewall and Email →
# m_titleFrame.m_titleLable (Cisco's typo) / m_closeBtn.
APPLET_TITLES = ("m_titleBar.m_titleLabel", "m_titleFrame.m_titleLable")
APPLET_CLOSERS = ("m_titleBar.m_closeButton", "m_titleFrame.m_closeBtn")


def _applet_part(suffixes: tuple[str, ...]) -> Callable[[UiElement], bool]:
    """Visible parts of the open apps whose ident ends in one of `suffixes`."""
    return lambda e: ("CDesktopApplet" in e.ident and e.ident.endswith(suffixes)
                      and not e.offscreen)


def _select_name(e: UiElement) -> bool:
    return e.name.startswith("Select (")


# A name match, kept as it is: the same predicate is the fallback, so whether
# the platform exposes an ident for the tool button does not matter.
SELECT_TOOL = Locator("select_tool", _select_name, lambda e, els: _select_name(e))
# macOS (PHASE-00 fixture `main-window.json`): no CLogicalWorkspace.QWidget in
# the AX tree; the canvas is the AXGroup `...m_pViewArea_Window.m_workspaceWS`,
# whose frame is the view (0,180 1512×526 pt there).
LOGICAL_CANVAS = Locator(
    "logical_canvas", lambda e: e.ident.endswith("CLogicalWorkspace.QWidget"),
    lambda e, els: e.ident.endswith("m_pViewArea_Window.m_workspaceWS"),
)
CANVAS_HBAR = Locator(
    "canvas_hbar",
    lambda e: ("CLogicalWorkspace.qt_scrollarea_hcontainer" in e.ident
               and e.ident.endswith("QScrollBar")),
)
CANVAS_VBAR = Locator(
    "canvas_vbar",
    lambda e: ("CLogicalWorkspace.qt_scrollarea_vcontainer" in e.ident
               and e.ident.endswith("QScrollBar")),
)
APPLET_TITLE = Locator("applet_title", _applet_part(APPLET_TITLES))
APPLET_CLOSE = Locator("applet_close", _applet_part(APPLET_CLOSERS))
CONSOLE_SCROLLBAR = Locator(
    "console_scrollbar", lambda e: e.role == Role.SCROLLBAR and "CCommandLine" in e.ident,
)


def desktop_app(obj: str) -> Locator:
    """The Desktop button whose objectName is `obj` (from `names.desktop_app_object_name`)."""
    return Locator(f"desktop_app({obj})", lambda e: e.ident.endswith("." + obj))


def ident_suffix(suffix: str) -> Locator:
    """The element whose ident ends in `suffix` (`m_urlEdit`, `m_goButton`)."""
    return Locator(f"ident_suffix({suffix})", lambda e: e.ident.endswith(suffix))
