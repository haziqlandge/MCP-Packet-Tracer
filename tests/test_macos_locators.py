"""Every locator the presenter uses, on the recorded macOS trees (PHASE-05).

This is the test the macOS UI mode rests on: each key must find exactly the
element the presenter needs in PT 9.0.1's real AX tree. Keys whose element does
not exist on macOS are pinned as such (a finding, not a guess).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.packet_tracer_mcp.infrastructure.ui import locators, names
from src.packet_tracer_mcp.infrastructure.ui.backend import Role, UiElement
from src.packet_tracer_mcp.infrastructure.ui.backends.macos import ax
from src.packet_tracer_mcp.infrastructure.ui.locators import locate, locate_all
from src.packet_tracer_mcp.infrastructure.ui.presenter import Presenter
from tests.fakes.fake_backend import FakeBackend

FIXTURES = Path(__file__).parent / "fixtures" / "macos"


def els(name: str) -> list[UiElement]:
    return ax.elements_from_tree(json.loads((FIXTURES / name).read_text(encoding="utf-8"))["tree"])


class TestMainWindow:
    def test_select_tool(self):
        hits = locate_all(els("main-window.json"), locators.SELECT_TOOL)
        assert [e.name for e in hits] == ["Select (Esc)"]

    def test_logical_canvas_is_the_workspace_group(self):
        hits = locate_all(els("main-window.json"), locators.LOGICAL_CANVAS)
        assert len(hits) == 1
        assert hits[0].ident.endswith("m_pViewArea_Window.m_workspaceWS")
        assert hits[0].rect == (0, 180, 1512, 706)

    def test_no_canvas_scroll_bars_in_the_recording(self):
        # PREVIOUS_WORK 2.4 #2: none exposed while the scene fits the view.
        main = els("main-window.json")
        assert locate(main, locators.CANVAS_HBAR) is None
        assert locate(main, locators.CANVAS_VBAR) is None


class TestDesktop:
    def test_every_app_button_is_found_once(self):
        desk = els("PC1-desktop.json")
        for app in ("ip_configuration", "command_prompt", "web_browser", "terminal"):
            obj = names.desktop_app_object_name(app)
            hits = locate_all(desk, locators.desktop_app(obj))
            assert len(hits) == 1 and hits[0].role is Role.BUTTON, app

    def test_command_prompt_applet(self):
        cmd = els("PC1-desktop-command_prompt.json")
        titles = locate_all(cmd, locators.APPLET_TITLE)
        assert [t.name for t in titles] == ["Command Prompt "]
        assert names.desktop_app_object_name(titles[0].name) == "CommandPromptBtn"
        assert len(locate_all(cmd, locators.APPLET_CLOSE)) == 1

    def test_email_innermost_closer_is_the_pressable_one(self):
        mail = els("PC1-desktop-email.json")
        titles = locate_all(mail, locators.APPLET_TITLE)
        assert sorted(t.name for t in titles) == ["Configure Mail", "MAIL BROWSER"]
        closers = locate_all(mail, locators.APPLET_CLOSE)
        assert len(closers) == 2
        inner = max(closers, key=lambda e: len(e.ident))  # the presenter's choice
        outer = min(closers, key=lambda e: len(e.ident))
        assert "AXPress" in inner.raw["actions"] and "AXPress" not in outer.raw["actions"]
        # The presenter recognises the outer app from its title.
        outer_title = min(titles, key=lambda e: len(e.ident))
        assert names.desktop_app_object_name(outer_title.name) == "EmailBtn"

    def test_web_browser_fields(self):
        web = els("PC1-desktop-web_browser.json")
        assert locate(web, locators.ident_suffix("m_urlEdit")).role is Role.EDIT
        assert locate(web, locators.ident_suffix("m_goButton")).role is Role.BUTTON

    def test_console_has_no_scroll_bar_element(self):
        for name in ("R1-cli.json", "PC1-desktop-command_prompt.json"):
            assert locate(els(name), locators.CONSOLE_SCROLLBAR) is None, name


class TestSections:
    def _section(self, fixture, section):
        key = names.normalize(section)
        return [e for e in els(fixture)
                if e.role in {Role.CHECKBOX, Role.BUTTON, Role.LIST_ITEM}
                and not e.offscreen and names.normalize(e.name) == key]

    def test_config_interface_section(self):
        hits = self._section("PC1-config-fastethernet0.json", "FastEthernet0")
        assert len(hits) == 1 and hits[0].role is Role.CHECKBOX

    def test_services_section(self):
        hits = self._section("SRV1-services-dhcp.json", "DHCP")
        assert len(hits) == 1 and hits[0].role is Role.CHECKBOX


class TestPresenterOnRecordedTrees:
    """The presenter's own flows, fed with the recorded elements."""

    def _p(self, backend):
        now = [0.0]
        return Presenter(lambda js, t: "ok", sleep=lambda s: now.__setitem__(0, now[0] + s),
                         clock=lambda: now[0], backend=backend)

    def test_open_the_cli_tab(self):
        b = FakeBackend(trees={7: els("R1-cli.json")})
        self._p(b)._select_tab(7, "CLI")
        assert b.log == [("select", "CLI")]

    def test_open_an_app_from_the_desktop(self):
        b = FakeBackend(trees={7: els("PC1-desktop.json")})
        assert self._p(b)._open_app(7, "command_prompt") == "app command_prompt opened"
        assert b.log == [("press", "Command\nPrompt")]

    def test_email_close_loop_on_the_recorded_tree(self):
        mail, desk = els("PC1-desktop-email.json"), els("PC1-desktop.json")
        inner = "BaseWorkstationMailConfiguration"
        closed: list[str] = []

        def tree(backend):
            if len(closed) >= 2:
                return desk
            if closed:  # the inner panel is gone, the outer one is left
                return [e for e in mail if inner not in e.ident]
            return mail

        def close(backend, e):
            # As in PT: a closer works only on the innermost open panel.
            if e.ident.endswith("m_closeBtn") and (inner in e.ident) == (not closed):
                closed.append(e.ident)

        for e in mail:
            if e.ident.endswith("m_closeBtn"):
                e.raw = SimpleNamespace(toggle=None, on_press=close)
        b = FakeBackend(trees={7: tree})
        assert self._p(b)._open_app(7, "command_prompt") == "app command_prompt opened"
        assert len(closed) == 2 and inner in closed[0] and inner not in closed[1]
        assert b.log[-1] == ("press", "Command\nPrompt")
