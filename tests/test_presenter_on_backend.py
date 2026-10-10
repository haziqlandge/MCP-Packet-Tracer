"""The presenter's flows on a scripted backend (PLAN/phases/PHASE-03.md, Tests).

These pin the Windows behaviour the seam must keep: the order of the steps, the
step texts, and above all the refusal to click the canvas unless the Select
tool is on (with Delete active, a click deletes the device).
"""

from __future__ import annotations

import json

import pytest

from src.packet_tracer_mcp.infrastructure.ui.backend import Capture, Role
from src.packet_tracer_mcp.infrastructure.ui.png import PNG_SIGNATURE
from src.packet_tracer_mcp.infrastructure.ui.presenter import Presenter, PresenterError
from tests.fakes.fake_backend import FakeBackend, el

PID = 4242
MAIN = 1
APP = "PtApp.CAppWindowBase"
WS = f"{APP}.m_pViewArea.CLogicalWorkspace"
DESK = "CWorkstationDialog.m_desktopTab.desktopScrollAreaWidgetContents"
CANVAS = (0, 100, 800, 700)  # left, top, right, bottom
CENTER = (400, 400)


def pt(*, open_=False, logical=True, zoom=0, cx=199, cy=400, host=False, exists=True):
    """A fake send_and_wait answering the presenter's JS; records what it got."""
    sent: list[str] = []

    def send(js: str, timeout: float):
        sent.append(js)
        if "getCenterXCoordinate" in js:
            if not exists:
                return json.dumps({"ok": False, "error": "device_not_found"})
            return json.dumps({"ok": True, "pid": PID, "logical": logical, "zoom": zoom,
                               "cx": cx, "cy": cy, "open": open_, "host": host, "model": "PC-PT"})
        if "setVisible" in js:
            return "ok"
        if "centerOnComponentByName" in js:
            return "ok"
        if "getProcessId()))" in js:
            return str(PID)
        return "ok"

    return send, sent


def main_tree(*, select_state=1, sticky=False, with_select=True, h=0.0, v=0.0):
    els = [el("Delete (Del)", f"{APP}.m_pPlToolBar.QToolButton", Role.CHECKBOX, toggle=0)]
    if with_select:
        els.append(el("Select (Esc)", f"{APP}.m_pPlToolBar.QToolButton", Role.CHECKBOX,
                      toggle=select_state, sticky=sticky))
    els += [el("", f"{WS}.QWidget", Role.OTHER, rect=CANVAS),
            el("", f"{WS}.qt_scrollarea_hcontainer.QScrollBar", Role.SCROLLBAR, value=h),
            el("", f"{WS}.qt_scrollarea_vcontainer.QScrollBar", Role.SCROLLBAR, value=v)]
    return els


def dialog_tabs(*names):
    return [el(n, f"CDialog.m_tabs.qt_tabwidget_tabbar.{n}", Role.TAB) for n in names]


def presenter(send, backend):
    """A presenter on a fake clock: waits cost no real time."""
    now = [0.0]

    def sleep(s: float) -> None:
        now[0] += s

    return Presenter(send, sleep=sleep, clock=lambda: now[0], backend=backend)


def clicks(b):
    return [a for a in b.log if a[0] == "click"]


# ---------------------------------------------------------------------------
# open: finding or opening the dialog
# ---------------------------------------------------------------------------

class TestOpenDialog:
    def test_already_open(self):
        send, _ = pt()
        b = FakeBackend(windows={"PC1": 7}, trees={7: dialog_tabs("Physical", "Desktop")})
        r = presenter(send, b).open("PC1", tab="Desktop")
        assert r["steps"] == ["dialog already open", "tab Desktop"]
        assert r["hwnd"] == 7 and ("raise", 7) in b.log and ("select", "Desktop") in b.log
        assert clicks(b) == []

    def test_hidden_dialog_is_shown_through_the_api(self):
        send, sent = pt(open_=True)
        b = FakeBackend(trees={})
        p = presenter(send, b)
        real = p._js

        def js(code, timeout=10.0):
            out = real(code, timeout)
            if "setVisible(true)" in code:
                b.windows["PC1"] = 9
            return out

        p._js = js
        r = p.open("PC1")
        # As at bcb2ef3: the re-shown dialog then also counts as already open.
        assert r["steps"] == ["dialog shown through PT's API", "dialog already open"]
        assert r["hwnd"] == 9
        assert clicks(b) == []

    def test_opened_by_click_with_select_already_on(self):
        send, _ = pt(cx=199, cy=400)
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree(select_state=1)},
                        click_opens={(199, 500): ("R1", 5)})
        r = presenter(send, b).open("R1")
        assert r["steps"] == ["dialog opened (click posted, cursor not moved)"]
        assert clicks(b) == [("click", MAIN, 199, 500)]
        assert not any(a[0] == "press" for a in b.log)

    def test_cursor_restored_route_says_the_cursor_moved(self):
        send, _ = pt(cx=199, cy=400)
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree()}, click_opens={(199, 500): ("R1", 5)},
                        click_result="cursor-restored")
        r = presenter(send, b).open("R1")
        assert r["steps"] == [
            "dialog opened (click sent; the cursor moved there for a moment and was put back)"]

    def test_select_tool_is_toggled_on_first(self):
        send, _ = pt()
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree(select_state=0)},
                        click_opens={(199, 500): ("R1", 5)})
        r = presenter(send, b).open("R1")
        assert r["steps"] == ["Select tool activated", "dialog opened (click posted, cursor not moved)"]
        assert b.log.index(("press", "Select (Esc)")) < b.log.index(("click", MAIN, 199, 500))

    def test_refuses_to_click_when_select_cannot_be_turned_on(self):
        # Delete stays active: a click would delete the device. Never click.
        send, _ = pt()
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree(select_state=0, sticky=True)},
                        click_opens={(199, 500): ("R1", 5)})
        with pytest.raises(PresenterError, match="won't click"):
            presenter(send, b).open("R1")
        assert clicks(b) == []

    def test_refuses_to_click_without_a_select_tool(self):
        send, _ = pt()
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree(with_select=False)})
        with pytest.raises(PresenterError, match="not clicking blind"):
            presenter(send, b).open("R1")
        assert clicks(b) == []

    def test_physical_view_refuses(self):
        send, _ = pt(logical=False)
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree()})
        with pytest.raises(PresenterError, match="Physical view"):
            presenter(send, b).open("R1")
        assert clicks(b) == []

    def test_scroll_bars_offset_the_click(self):
        send, _ = pt(cx=300, cy=250)
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree(h=50.0, v=20.0)},
                        click_opens={(250, 330): ("R1", 5)})
        presenter(send, b).open("R1")
        assert clicks(b) == [("click", MAIN, 250, 330)]

    def test_device_outside_the_viewport_is_centred_then_clicked_where_the_bars_say(self):
        # Windows: centring moves the scroll bars, and the point is recomputed from them.
        send, sent = pt(cx=5000, cy=400)
        tree = main_tree()
        hbar = next(e for e in tree if "hcontainer" in e.ident)
        real = send

        def send_and_scroll(js, timeout):
            if "centerOnComponentByName" in js:
                hbar.raw.value = 4700.0
            return real(js, timeout)

        b = FakeBackend(main=MAIN, trees={MAIN: tree}, click_opens={(300, 500): ("R1", 5)})
        r = presenter(send_and_scroll, b).open("R1")
        assert "canvas centred on the device" in r["steps"]
        assert any("centerOnComponentByName" in s for s in sent)
        assert clicks(b) == [("click", MAIN, 300, 500)]

    def test_device_still_outside_after_centring_clicks_the_centre(self):
        # macOS exposes no canvas scroll bars (ISSUES X12): after centring, the
        # device is in the middle of the view, never at the stale point.
        send, _ = pt(cx=2200, cy=900)
        tree = [e for e in main_tree() if e.role is not Role.SCROLLBAR]
        b = FakeBackend(main=MAIN, trees={MAIN: tree}, click_opens={CENTER: ("SRV1", 5)})
        r = presenter(send, b).open("SRV1")
        assert clicks(b) == [("click", MAIN, *CENTER)]
        assert "canvas centred on the device" in r["steps"]

    def test_zoomed_canvas_clicks_the_centre(self):
        send, _ = pt(zoom=2)
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree()}, click_opens={CENTER: ("R1", 5)})
        r = presenter(send, b).open("R1")
        assert r["steps"][0] == "canvas centred on the device (zoom other than 100%)"
        assert clicks(b) == [("click", MAIN, *CENTER)]

    def test_second_attempt_clicks_the_centre(self):
        send, _ = pt()
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree()}, click_opens={CENTER: ("R1", 5)})
        presenter(send, b).open("R1")
        assert clicks(b) == [("click", MAIN, 199, 500), ("click", MAIN, *CENTER)]

    def test_dialog_that_never_opens(self):
        send, _ = pt()
        b = FakeBackend(main=MAIN, trees={MAIN: main_tree()})
        with pytest.raises(PresenterError, match="did not open"):
            presenter(send, b).open("R1")

    def test_unknown_device(self):
        send, _ = pt(exists=False)
        with pytest.raises(PresenterError, match="does not exist"):
            presenter(send, FakeBackend()).open("R9")


# ---------------------------------------------------------------------------
# tabs, sections, apps
# ---------------------------------------------------------------------------

class TestNavigation:
    def test_missing_tab_lists_the_ones_there(self):
        send, _ = pt()
        b = FakeBackend(windows={"R1": 7}, trees={7: dialog_tabs("Physical", "Config", "CLI")})
        with pytest.raises(PresenterError, match=r"Tab 'Desktop' does not exist.*Physical, Config, CLI\."):
            presenter(send, b).open("R1", tab="Desktop")

    def test_section_presses_the_visible_clickable_one(self):
        send, _ = pt()
        tree = dialog_tabs("Config") + [
            el("FastEthernet0", "x.hidden", Role.CHECKBOX, offscreen=True),
            el("FastEthernet0", "x.label", Role.STATIC),
            el("FastEthernet0", "x.section", Role.CHECKBOX),
        ]
        b = FakeBackend(windows={"PC1": 7}, trees={7: tree})
        r = presenter(send, b).open("PC1", tab="Config", section="fast ethernet 0")
        assert r["steps"][-1] == "section fast ethernet 0"
        assert [a for a in b.log if a[0] == "press"] == [("press", "FastEthernet0")]

    def test_missing_section(self):
        send, _ = pt()
        b = FakeBackend(windows={"PC1": 7}, trees={7: dialog_tabs("Config")})
        with pytest.raises(PresenterError, match="Can't find section 'DHCP'"):
            presenter(send, b).open("PC1", tab="Config", section="DHCP")

    def test_app_defaults_to_the_desktop_tab(self):
        send, _ = pt()
        tree = dialog_tabs("Desktop") + [el("", f"{DESK}.m_desktopFrame.CommandPromptBtn", Role.BUTTON)]
        b = FakeBackend(windows={"PC1": 7}, trees={7: tree})
        r = presenter(send, b).open("PC1", app="cmd")
        assert r["tab"] == "Desktop"
        assert r["steps"] == ["dialog already open", "tab Desktop", "app cmd opened"]

    def test_email_nested_panels_close_inside_out(self):
        frame = ("m_titleFrame", "m_titleLable", "m_closeBtn")
        panels = [("CBaseWorkstationMailBrowser", "MAIL BROWSER"),
                  ("CBaseWorkstationMailBrowser.BaseWorkstationMailConfiguration", "Configure Mail")]

        def close(backend, e):
            # As in PT: only the innermost panel's closer works.
            if f"CDesktopApplet.{panels[-1][0]}." in e.ident:
                panels.pop()

        def tree(backend):
            out = dialog_tabs("Desktop")
            if not panels:
                return out + [el("", f"{DESK}.m_desktopFrame.{n}", Role.BUTTON)
                              for n in ("EmailBtn", "CommandPromptBtn")]
            for path, title in panels:
                base = f"{DESK}.CDesktopApplet.{path}.{frame[0]}"
                out += [el(title, f"{base}.{frame[1]}", Role.STATIC),
                        el("", f"{base}.{frame[2]}", Role.BUTTON, on_press=close)]
            return out

        send, _ = pt()
        b = FakeBackend(windows={"PC1": 7}, trees={7: tree})
        r = presenter(send, b).open("PC1", app="command_prompt")
        assert [a for a in b.log if a[0] == "press"] == [
            ("press", "m_closeBtn"), ("press", "m_closeBtn"), ("press", "CommandPromptBtn")]
        assert r["steps"][-1] == "app command_prompt opened" and panels == []

    def test_unknown_app(self):
        send, _ = pt()
        b = FakeBackend(windows={"PC1": 7}, trees={7: dialog_tabs("Desktop")})
        with pytest.raises(PresenterError, match="Unknown app 'solitaire'"):
            presenter(send, b).open("PC1", app="solitaire")


# ---------------------------------------------------------------------------
# fill_and_go, invoke_button, scroll_consoles
# ---------------------------------------------------------------------------

class TestDialogActions:
    def test_fill_and_go(self):
        b = FakeBackend(trees={7: [el("", "Browser.m_urlEdit", Role.EDIT),
                                   el("Go", "Browser.m_goButton", Role.BUTTON)]})
        assert presenter(pt()[0], b).fill_and_go(7, "m_urlEdit", "http://10.0.0.1", "m_goButton")
        assert b.log == [("set_value", "m_urlEdit", "http://10.0.0.1"), ("press", "Go")]

    def test_fill_and_go_ignores_offscreen_fields(self):
        b = FakeBackend(trees={7: [el("", "Browser.m_urlEdit", Role.EDIT, offscreen=True),
                                   el("Go", "Browser.m_goButton", Role.BUTTON)]})
        assert presenter(pt()[0], b).fill_and_go(7, "m_urlEdit", "x", "m_goButton") is False
        assert b.log == []

    def test_invoke_button_by_visible_text(self):
        b = FakeBackend(trees={7: [el("OK", "a.hidden", Role.BUTTON, offscreen=True),
                                   el("ok ", "a.ok", Role.BUTTON), el("OK", "a.label", Role.STATIC)]})
        assert presenter(pt()[0], b).invoke_button(7, "OK") is True
        assert b.log == [("press", "ok ")]
        assert presenter(pt()[0], b).invoke_button(7, "Cancel") is False

    def test_scroll_consoles_only_visible_consoles(self):
        b = FakeBackend(trees={7: [
            el("", "CLI.CCommandLine.QScrollBar", Role.SCROLLBAR),
            el("", "Cmd.CCommandLine.QScrollBar", Role.SCROLLBAR, offscreen=True),
            el("", "Other.QScrollBar", Role.SCROLLBAR),
        ]})
        assert presenter(pt()[0], b).scroll_consoles(7) is True
        assert b.log == [("scroll_to_end", "CLI.CCommandLine.QScrollBar")]

    def test_scroll_consoles_survives_a_failing_bar(self):
        b = FakeBackend(trees={7: [el("", "CLI.CCommandLine.QScrollBar", Role.SCROLLBAR, fail=True)]})
        assert presenter(pt()[0], b).scroll_consoles(7) is False

    def test_open_scrolls_when_asked(self):
        tree = dialog_tabs("CLI") + [el("", "CLI.CCommandLine.QScrollBar", Role.SCROLLBAR)]
        b = FakeBackend(windows={"R1": 7}, trees={7: tree})
        r = presenter(pt()[0], b).open("R1", tab="CLI", scroll_bottom=True)
        assert r["steps"][-1] == "console scrolled to the end"


# ---------------------------------------------------------------------------
# capture, availability
# ---------------------------------------------------------------------------

class TestCapture:
    def test_writes_a_png_and_flags_blank(self, tmp_path):
        b = FakeBackend(windows={"PC1": 7}, capture=Capture(2, 1, b"\x00\x00\x00\xff" * 2))
        info = presenter(pt()[0], b).capture("PC1", tmp_path / "shots" / "pc1.png")
        assert info == {"path": str(tmp_path / "shots" / "pc1.png"), "width": 2, "height": 1,
                        "blank": True}
        assert (tmp_path / "shots" / "pc1.png").read_bytes().startswith(PNG_SIGNATURE)
        assert b.log == [("raise", 7), ("capture", 7)]

    def test_not_blank(self, tmp_path):
        b = FakeBackend(windows={"PC1": 7}, capture=Capture(2, 1, b"\x00\x00\x00\xff\x10\x20\x30\xff"))
        assert presenter(pt()[0], b).capture("PC1", tmp_path / "a.png")["blank"] is False

    def test_main_window_when_no_device(self, tmp_path):
        b = FakeBackend(main=MAIN, capture=Capture(1, 1, b"\x01\x02\x03\xff"))
        presenter(pt()[0], b).capture("", tmp_path / "main.png")
        assert ("capture", MAIN) in b.log

    def test_dialog_not_open(self, tmp_path):
        with pytest.raises(PresenterError, match="is not open"):
            presenter(pt()[0], FakeBackend()).capture("PC1", tmp_path / "a.png")


class TestAvailability:
    @pytest.mark.parametrize("call", [
        lambda p, tmp: p.open("PC1"), lambda p, tmp: p.capture("PC1", tmp / "a.png"),
    ])
    def test_unavailable_backend_gives_its_reason_verbatim(self, tmp_path, call):
        b = FakeBackend(available=(False, "UI mode is not available on Linux yet."))
        with pytest.raises(PresenterError) as exc:
            call(presenter(pt()[0], b), tmp_path)
        assert str(exc.value) == "UI mode is not available on Linux yet."
        assert b.requests == [False]

    @pytest.mark.parametrize("call", [
        lambda p, tmp: p.open("PC1"), lambda p, tmp: p.capture("PC1", tmp / "a.png"),
    ])
    def test_backend_unavailable_mid_flow_becomes_a_presenter_error(self, tmp_path, call):
        b = FakeBackend(windows={"PC1": 7}, unavailable_on="find_window")
        with pytest.raises(PresenterError, match="^find_window: grant it in System Settings$"):
            call(presenter(pt()[0], b), tmp_path)

    def test_available_passes_request_through(self):
        b = FakeBackend()
        p = presenter(pt()[0], b)
        assert p.available(request=True) == (True, "")
        assert b.requests == [True]

    def test_default_backend_is_the_platform_one(self, monkeypatch):
        from src.packet_tracer_mcp.infrastructure import platform
        fake = FakeBackend()
        monkeypatch.setattr(platform, "current", lambda: type("P", (), {"ui_backend": lambda self: fake})())
        assert Presenter(pt()[0]).backend is fake
