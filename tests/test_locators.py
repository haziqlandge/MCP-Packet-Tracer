"""Every locator key of PLAN/INTERFACES.md §3 on synthetic elements.

Each `by_ident` is the presenter's predicate from `bcb2ef3`, moved verbatim, so
these cases pin what the Windows presenter matched before the seam existed.
"""

from __future__ import annotations

import pytest

from src.packet_tracer_mcp.infrastructure.ui import locators
from src.packet_tracer_mcp.infrastructure.ui.backend import Role, UiElement
from src.packet_tracer_mcp.infrastructure.ui.locators import Locator, locate, locate_all

APP = "PtApp.CAppWindowBase"
WS = f"{APP}.m_pViewArea.CLogicalWorkspace"
DESK = "CWorkstationDialog.m_desktopTab.desktopScrollAreaWidgetContents"


def el(ident: str = "", name: str = "", role: Role = Role.OTHER, *, offscreen: bool = False) -> UiElement:
    return UiElement(raw=None, name=name, ident=ident, role=role, offscreen=offscreen,
                     bounds=(0, 0, 10, 10))


def test_every_documented_key_exists():
    keys = {locators.SELECT_TOOL.key, locators.LOGICAL_CANVAS.key, locators.CANVAS_HBAR.key,
            locators.CANVAS_VBAR.key, locators.APPLET_TITLE.key, locators.APPLET_CLOSE.key,
            locators.CONSOLE_SCROLLBAR.key, locators.desktop_app("EmailBtn").key,
            locators.ident_suffix("m_urlEdit").key}
    assert {k.split("(")[0] for k in keys} == {
        "select_tool", "logical_canvas", "canvas_hbar", "canvas_vbar", "applet_title",
        "applet_close", "desktop_app", "console_scrollbar", "ident_suffix"}


class TestSelectTool:
    # A name match, kept as it is: it must not depend on whether the platform
    # exposes an ident for the tool button.
    @pytest.mark.parametrize("ident", [f"{APP}.m_pPlToolBar.QToolButton", ""])
    def test_matches_by_name_with_or_without_ident(self, ident):
        assert locate([el(ident, "Select (Esc)")], locators.SELECT_TOOL) is not None

    @pytest.mark.parametrize("name", ["Delete (Del)", "Selection", "select (esc)", ""])
    def test_other_names(self, name):
        assert locate([el(f"{APP}.x", name)], locators.SELECT_TOOL) is None


class TestCanvas:
    def test_logical_canvas(self):
        assert locate([el(f"{WS}.QWidget")], locators.LOGICAL_CANVAS) is not None
        assert locate([el(f"{WS}.QWidget.child")], locators.LOGICAL_CANVAS) is None

    def test_scroll_bars_by_axis(self):
        h = el(f"{WS}.qt_scrollarea_hcontainer.QScrollBar")
        v = el(f"{WS}.qt_scrollarea_vcontainer.QScrollBar")
        assert locate([v, h], locators.CANVAS_HBAR) is h
        assert locate([h, v], locators.CANVAS_VBAR) is v

    def test_scroll_bar_needs_the_scrollbar_suffix(self):
        assert locate([el(f"{WS}.qt_scrollarea_hcontainer")], locators.CANVAS_HBAR) is None


class TestApplets:
    @pytest.mark.parametrize("suffix", ["m_titleBar.m_titleLabel", "m_titleFrame.m_titleLable"])
    def test_both_title_variants(self, suffix):
        assert locate([el(f"{DESK}.CDesktopApplet.X.{suffix}")], locators.APPLET_TITLE)

    @pytest.mark.parametrize("suffix", ["m_titleBar.m_closeButton", "m_titleFrame.m_closeBtn"])
    def test_both_closer_variants(self, suffix):
        assert locate([el(f"{DESK}.CDesktopApplet.X.{suffix}")], locators.APPLET_CLOSE)

    def test_offscreen_and_non_applet_parts_are_skipped(self):
        els = [el(f"{DESK}.CDesktopApplet.X.m_titleBar.m_titleLabel", offscreen=True),
               el(f"{DESK}.Other.m_titleBar.m_titleLabel")]
        assert locate_all(els, locators.APPLET_TITLE) == []


class TestDesktopApp:
    def test_matches_the_object_name_after_a_dot(self):
        btn = el(f"{DESK}.m_desktopFrame.EmailBtn")
        assert locate([btn], locators.desktop_app("EmailBtn")) is btn

    def test_partial_object_name_does_not_match(self):
        assert locate([el(f"{DESK}.m_desktopFrame.MyEmailBtn")], locators.desktop_app("EmailBtn")) is None


class TestConsoleScrollbar:
    def test_needs_the_role_and_the_console(self):
        ok = el("CLI.CCommandLine.QScrollBar", role=Role.SCROLLBAR)
        assert locate_all([ok, el("CLI.CCommandLine.QScrollBar", role=Role.OTHER),
                           el("CLI.Other.QScrollBar", role=Role.SCROLLBAR)],
                          locators.CONSOLE_SCROLLBAR) == [ok]


def test_ident_suffix():
    edit = el("Browser.m_urlEdit")
    assert locate([el("Browser.m_goButton"), edit], locators.ident_suffix("m_urlEdit")) is edit


class TestLocateRules:
    def test_empty_ident_without_by_shape_never_matches(self):
        always = Locator("always", lambda e: True)
        assert locate([el("")], always) is None
        for loc in (locators.LOGICAL_CANVAS, locators.CANVAS_HBAR, locators.APPLET_TITLE,
                    locators.CONSOLE_SCROLLBAR, locators.desktop_app("EmailBtn"),
                    locators.ident_suffix("")):
            assert locate([el("", role=Role.SCROLLBAR)], loc) is None, loc.key

    def test_by_shape_only_when_the_ident_is_empty(self):
        seen = []

        def shape(e, els):
            seen.append(len(els))
            return True

        loc = Locator("shape", lambda e: False, shape)
        with_ident, without = el("a.b"), el("")
        assert locate([with_ident, without], loc) is without
        assert seen == [2]

    def test_locate_is_first_and_locate_all_keeps_order(self):
        a, b = el("x.Btn"), el("y.Btn")
        loc = locators.ident_suffix("Btn")
        assert locate([a, b], loc) is a
        assert locate_all([b, a], loc) == [b, a]


def test_rect_is_read_lazily_when_given_a_callable():
    calls = []
    e = UiElement(raw=None, name="", ident="a", role=Role.OTHER, offscreen=False,
                  bounds=lambda: calls.append(1) or (1, 2, 3, 4))
    assert calls == []
    assert e.rect == (1, 2, 3, 4) and calls == [1]


class TestSecondPass:
    """The fallback reaches elements with an ident only when nothing matched."""

    def test_windows_keeps_its_canvas_even_when_the_mac_name_comes_first(self):
        mac = el(f"{APP}.centralwidget.m_pWorkSpaceWnd.m_pViewArea_Window.m_workspaceWS")
        win = el(f"{WS}.QWidget")
        assert locate([mac, win], locators.LOGICAL_CANVAS) is win
        assert locate_all([mac, win], locators.LOGICAL_CANVAS) == [win]

    def test_mac_canvas_found_when_windows_name_is_absent(self):
        mac = el(f"{APP}.centralwidget.m_pWorkSpaceWnd.m_pViewArea_Window.m_workspaceWS")
        assert locate([el("other.thing"), mac], locators.LOGICAL_CANVAS) is mac

    def test_no_second_pass_without_by_shape(self):
        assert locate([el("a.b")], Locator("x", lambda e: False)) is None

    def test_second_pass_skips_elements_without_ident(self):
        calls = []
        loc = Locator("x", lambda e: False, lambda e, els: calls.append(e.ident) or e.ident == "")
        assert locate([el("a.b")], loc) is None
        assert calls == ["a.b"]
