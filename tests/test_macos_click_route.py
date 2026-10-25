"""The macOS click and key routes, and MacBackend's navigation, with events stubbed.

PHASE-00 (PREVIOUS_WORK 2.4 #6, #7): mouse events posted to PT's pid never reach
its canvas, so the click goes through the HID tap with PT frontmost and the
cursor put back; checkable sections switch only on focus + Space with PT
frontmost. A HID click lands on whatever is on top, so these tests pin every
refusal: no click unless PT is frontmost and the point is PT's canvas.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.packet_tracer_mcp.infrastructure.ui.backend import BackendError, Role, UiElement
from src.packet_tracer_mcp.infrastructure.ui.backends.macos import ax as mac_ax
from src.packet_tracer_mcp.infrastructure.ui.backends.macos import events
from src.packet_tracer_mcp.infrastructure.ui.backends.macos import windows as mac_windows
from src.packet_tracer_mcp.infrastructure.ui.backends.macos.backend import MacBackend, Ref

PID = 4242
CANVAS = "PtApp.CAppWindowBase.centralwidget.m_pWorkSpaceWnd.m_pViewArea_Window.m_workspaceWS"


class FakeIO:
    def __init__(self, *, front=PID, front_after=0, hit=("Workspace Description", CANVAS),
                 cursor=(10.0, 20.0), post_fails=False, focus_err=0, open_brings_front=False):
        self.front, self.front_after = front, front_after
        self.hit = list(hit)
        self.pos = cursor
        self.post_fails = post_fails
        self.focus_err = focus_err
        self.open_brings_front = open_brings_front
        self.log: list[tuple] = []
        self.polls = 0

    def activate(self, pid):
        self.log.append(("activate", pid))

    def open_app(self, pid):
        self.log.append(("open_app", pid))
        if self.open_brings_front:
            self.front = pid

    def raise_window(self, ax_window):
        self.log.append(("raise", ax_window))

    def is_frontmost(self, pid):
        self.polls += 1
        return (self.front if self.polls > self.front_after else 1) == pid

    def hit_idents(self, x, y):
        self.log.append(("hit", x, y))
        # A list of lists plays one answer per call (the window order settling).
        if self.hit and isinstance(self.hit[0], list):
            return self.hit.pop(0) if len(self.hit) > 1 else self.hit[0]
        return self.hit

    def cursor(self):
        return self.pos

    def post_click(self, x, y):
        self.log.append(("click", x, y))
        if self.post_fails:
            raise RuntimeError("event tap refused")

    def warp(self, x, y):
        self.log.append(("warp", x, y))

    def focus(self, el):
        self.log.append(("focus", el))
        return self.focus_err

    def key_to_pid(self, pid, keycode):
        self.log.append(("key", pid, keycode))

    def sleep(self, s):
        pass


def kinds(io):
    return [e[0] for e in io.log]


class TestClick:
    def test_happy_path_restores_the_cursor(self):
        io = FakeIO()
        assert events.click(PID, "MAIN", 299, 330, io=io) == "cursor-restored"
        assert io.log == [("activate", PID), ("raise", "MAIN"), ("hit", 299, 330),
                          ("click", 299, 330), ("warp", 10.0, 20.0)]

    def test_waits_for_pt_to_come_to_the_front(self):
        io = FakeIO(front_after=3)
        assert events.click(PID, "MAIN", 1, 2, io=io) == "cursor-restored"

    def test_refuses_when_pt_is_not_frontmost(self):
        io = FakeIO(front=999)
        with pytest.raises(BackendError, match="not the frontmost app"):
            events.click(PID, "MAIN", 1, 2, io=io)
        assert "click" not in kinds(io) and "warp" not in kinds(io)
        assert kinds(io).count("open_app") == 1  # the fallback was tried, once

    def test_activation_ignored_falls_back_to_launch_services(self):
        # Live, 2026-10-24 (ISSUES X18): from the Claude Code helper on macOS 26.6,
        # activateWithOptions_ left Claude in front 2 of 2 times; `open -a` worked.
        io = FakeIO(front=999, open_brings_front=True)
        assert events.click(PID, "MAIN", 299, 330, io=io) == "cursor-restored"
        assert kinds(io)[:3] == ["activate", "raise", "open_app"]
        assert ("click", 299, 330) in io.log

    def test_no_fallback_when_activation_works(self):
        io = FakeIO(front_after=3)
        events.click(PID, "MAIN", 1, 2, io=io)
        assert "open_app" not in kinds(io)

    def test_refuses_when_something_covers_the_canvas(self):
        io = FakeIO(hit=("PtApp.CWorkstationDialog.m_tabs", "PC1"))
        with pytest.raises(BackendError, match="covers PT's canvas"):
            events.click(PID, "MAIN", 500, 400, io=io)
        assert "click" not in kinds(io)

    def test_waits_for_pt_windows_to_come_over_the_point(self):
        # Live, 2026-10-10: PT reported frontmost before its windows were raised
        # over Claude's, so the first hit test found Claude's window.
        io = FakeIO(hit=[["", ""], ["", ""], ["Workspace Description", CANVAS]])
        assert events.click(PID, "MAIN", 299, 330, io=io) == "cursor-restored"
        assert kinds(io).count("hit") == 3 and ("click", 299, 330) in io.log

    def test_refuses_when_nothing_is_hit(self):
        io = FakeIO(hit=())
        with pytest.raises(BackendError, match="covers PT's canvas"):
            events.click(PID, "MAIN", 500, 400, io=io)
        assert "click" not in kinds(io)

    def test_cursor_is_restored_even_when_posting_fails(self):
        io = FakeIO(post_fails=True)
        with pytest.raises(RuntimeError):
            events.click(PID, "MAIN", 5, 6, io=io)
        assert io.log[-1] == ("warp", 10.0, 20.0)


class TestToolCheckedAtTheClick:
    # Live 2026-10-25, twice: the click landed with another canvas tool active
    # although Select was on when the presenter checked, before PT came to the
    # front: once a note editor opened (Place Note, N), once "Create Complex
    # PDU" for PC4 (C). A key reaching PT in between switches the tool, and
    # with Delete (Del) the click would delete the device.

    def test_checked_after_pt_is_in_front_and_before_the_click(self):
        io = FakeIO()
        events.click(PID, "MAIN", 299, 330, io=io, ready=lambda: io.log.append(("ready",)))
        assert io.log.index(("hit", 299, 330)) < io.log.index(("ready",)) < io.log.index(
            ("click", 299, 330))

    def test_not_ready_means_no_click_and_the_cursor_untouched(self):
        io = FakeIO()
        with pytest.raises(BackendError, match="Place Note"):
            events.click(PID, "MAIN", 299, 330, io=io, ready=lambda: "tool is Place Note (N)")
        assert not [a for a in io.log if a[0] in ("click", "warp")]


class TestKeyboardPress:
    def test_focus_then_space_to_the_pid(self):
        io = FakeIO()
        events.press_by_keyboard(PID, "EL", io=io)
        assert io.log == [("activate", PID), ("focus", "EL"), ("key", PID, events.KEY_SPACE)]

    def test_refuses_when_pt_is_not_frontmost(self):
        io = FakeIO(front=999)
        with pytest.raises(BackendError, match="not the frontmost app"):
            events.press_by_keyboard(PID, "EL", io=io)
        assert "key" not in kinds(io)

    def test_activation_ignored_falls_back_to_launch_services(self):
        io = FakeIO(front=999, open_brings_front=True)
        events.press_by_keyboard(PID, "EL", io=io)
        assert io.log == [("activate", PID), ("open_app", PID), ("focus", "EL"),
                          ("key", PID, events.KEY_SPACE)]

    def test_refuses_when_the_element_takes_no_focus(self):
        io = FakeIO(focus_err=-25205)
        with pytest.raises(BackendError, match="-25205"):
            events.press_by_keyboard(PID, "EL", io=io)
        assert "key" not in kinds(io)


class TestFrontmostIsReadLive:
    """Live, 2026-10-24: in a process that runs no AppKit event loop (the MCP
    server), `NSWorkspace.frontmostApplication()` kept answering PT while focus
    moved to Safari and then Claude; PT's own `AXFrontmost` followed each move.
    The click route waited on the cached answer and timed out."""

    def test_reads_pt_axfrontmost_and_never_nsworkspace(self, monkeypatch):
        import sys
        from types import ModuleType
        read: list[tuple] = []
        fake_as = SimpleNamespace(AXUIElementCreateApplication=lambda pid: ("app", pid))
        monkeypatch.setattr(mac_ax, "_as", lambda: fake_as)
        monkeypatch.setattr(mac_ax, "attr",
                            lambda el, name: read.append((el, name)) or name == "AXFrontmost")
        stale = ModuleType("AppKit")
        stale.NSWorkspace = SimpleNamespace(sharedWorkspace=lambda: pytest.fail("NSWorkspace read"))
        monkeypatch.setitem(sys.modules, "AppKit", stale)
        assert events.QuartzIO().is_frontmost(PID) is True
        assert read == [(("app", PID), "AXFrontmost")]

    def test_a_failed_read_counts_as_not_frontmost(self, monkeypatch):
        monkeypatch.setattr(mac_ax, "_as",
                            lambda: SimpleNamespace(AXUIElementCreateApplication=lambda pid: pid))
        monkeypatch.setattr(mac_ax, "attr", lambda el, name: None)
        assert events.QuartzIO().is_frontmost(PID) is False


# ---------------------------------------------------------------------------
# MacBackend navigation over stubbed AX calls
# ---------------------------------------------------------------------------

MAIN, DIALOG = 11, 22


def ui(name, role, handle, ax_el, ident="a.b"):
    return UiElement(raw=Ref(ax_el, handle), name=name, ident=ident, role=role,
                     offscreen=False, bounds=(0, 0, 1, 1))


@pytest.fixture
def stub(monkeypatch):
    """AX state: element → attributes; every perform/set is logged."""
    state = SimpleNamespace(attrs={}, log=[], perform_err=0, set_err=0, after_key=None)

    def perform(el, action):
        state.log.append(("perform", el, action))
        return state.perform_err

    def set_attr(el, name, value):
        state.log.append(("set", el, name, value))
        if state.set_err:
            return state.set_err
        state.attrs.setdefault(el, {})[name] = value
        return 0

    def attr(el, name):
        return state.attrs.get(el, {}).get(name)

    monkeypatch.setattr(mac_ax, "perform", perform)
    monkeypatch.setattr(mac_ax, "set_attr", set_attr)
    monkeypatch.setattr(mac_ax, "attr", attr)
    io = FakeIO()
    real_key = io.key_to_pid

    def key(pid, keycode):
        real_key(pid, keycode)
        if state.after_key:
            state.after_key()

    io.key_to_pid = key
    b = MacBackend(io=io, responsible=lambda: ("claude", None))
    b._windows = {MAIN: (PID, "MAINWIN"), DIALOG: (PID, "DLGWIN")}
    b._mains = {MAIN}
    state.io, state.backend = io, b
    return state


class TestNavigation:
    def test_select_and_press_use_axpress(self, stub):
        b = stub.backend
        b.select(ui("CLI", Role.TAB, DIALOG, "tab"))
        b.press(ui("Go", Role.BUTTON, DIALOG, "go"))
        assert stub.log == [("perform", "tab", "AXPress"), ("perform", "go", "AXPress")]

    def test_select_tool_in_the_main_window_uses_axpress(self, stub):
        stub.backend.press(ui("Select (Esc)", Role.CHECKBOX, MAIN, "sel"))
        assert stub.log == [("perform", "sel", "AXPress")]
        assert "key" not in kinds(stub.io)

    def test_dialog_section_switches_by_focus_and_space(self, stub):
        stub.after_key = lambda: stub.attrs.setdefault("sec", {}).__setitem__("AXValue", 1)
        stub.backend.press(ui("FastEthernet0", Role.CHECKBOX, DIALOG, "sec"))
        assert ("key", PID, events.KEY_SPACE) in stub.io.log
        assert not any(e[0] == "perform" for e in stub.log)

    def test_section_check_lags_the_key_press(self, stub):
        # Live, 2026-10-10: DHCP read 0 right after Space and 1 from ~0.15 s on.
        reads = {"n": 0}
        real_attr = mac_ax.attr

        def attr(el, name):
            if el == "sec" and name == "AXValue" and stub.io.log and stub.io.log[-1][0] == "key":
                reads["n"] += 1
                return 1 if reads["n"] >= 3 else 0
            return real_attr(el, name)

        mac_ax.attr = attr  # restored by the fixture's monkeypatch
        stub.backend.press(ui("DHCP", Role.CHECKBOX, DIALOG, "sec"))
        assert reads["n"] == 3

    def test_section_already_shown_is_not_pressed(self, stub):
        stub.attrs["sec"] = {"AXValue": 1}
        stub.backend.press(ui("DHCP", Role.CHECKBOX, DIALOG, "sec"))
        assert "key" not in kinds(stub.io) and "focus" not in kinds(stub.io)

    def test_section_that_did_not_switch_is_an_error(self, stub):
        with pytest.raises(BackendError, match="did not switch to 'DHCP'"):
            stub.backend.press(ui("DHCP", Role.CHECKBOX, DIALOG, "sec"))

    def test_ax_error_names_the_action_and_code(self, stub):
        stub.perform_err = -25200
        with pytest.raises(BackendError, match=r"AXPress.*'Go'.*-25200"):
            stub.backend.press(ui("Go", Role.BUTTON, DIALOG, "go"))

    def test_values(self, stub):
        stub.attrs["sel"] = {"AXValue": 1}
        stub.attrs["bar"] = {"AXValue": 12.5, "AXMaxValue": 300.0}
        b = stub.backend
        assert b.toggle_state(ui("Select (Esc)", Role.CHECKBOX, MAIN, "sel")) == 1
        assert b.toggle_state(ui("x", Role.CHECKBOX, MAIN, "none")) == 0
        bar = ui("", Role.SCROLLBAR, DIALOG, "bar")
        assert b.range_value(bar) == 12.5
        b.scroll_to_end(bar)
        assert stub.attrs["bar"]["AXValue"] == 300.0

    def test_scroll_to_end_needs_a_scroll_bar(self, stub):
        with pytest.raises(BackendError, match="not a scroll bar"):
            stub.backend.scroll_to_end(ui("", Role.EDIT, DIALOG, "console"))

    def test_set_value(self, stub):
        stub.backend.set_value(ui("URL", Role.EDIT, DIALOG, "url"), "http://192.168.10.10")
        assert stub.attrs["url"]["AXValue"] == "http://192.168.10.10"

    def test_set_value_retries_after_focus(self, stub):
        calls = []

        def set_attr(el, name, value):
            calls.append(name)
            if name == "AXValue" and calls.count("AXValue") == 1:
                return -25200
            stub.attrs.setdefault(el, {})[name] = value
            return 0

        mac_ax.set_attr = set_attr  # monkeypatched by the fixture, restored after
        stub.backend.set_value(ui("URL", Role.EDIT, DIALOG, "url"), "x")
        assert calls == ["AXValue", "AXFocused", "AXValue"]

    def test_click_goes_to_the_main_window_of_the_pid(self, stub):
        assert stub.backend.click(MAIN, 299, 330) == "cursor-restored"
        assert ("raise", "MAINWIN") in stub.io.log and ("click", 299, 330) in stub.io.log

    def test_unknown_handle(self, stub):
        with pytest.raises(BackendError, match="unknown"):
            stub.backend.elements(99)

    def test_elements_walk_the_window_and_keep_the_ax_element(self, stub, monkeypatch):
        tree = {"role": "AXWindow", "frame": [0, 0, 100, 100], "_el": "DLGWIN", "children": [
            {"role": "AXTabGroup", "title": "", "description": "", "identifier": "t", "value": "",
             "frame": [0, 0, 50, 10], "actions": [], "_el": "TG", "children": [
                {"role": "AXRadioButton", "title": "CLI", "description": "", "identifier": "t",
                 "value": "", "frame": [0, 0, 10, 10], "actions": [], "_el": "CLI", "children": []}]}]}
        seen = {}

        def walk(root, **kw):
            seen.update(kw, root=root)
            return tree, {}

        monkeypatch.setattr(mac_ax, "walk", walk)
        tabs = stub.backend.elements(DIALOG, Role.TAB)
        assert [(t.name, t.raw) for t in tabs] == [("CLI", Ref("CLI", DIALOG))]
        assert seen["root"] == "DLGWIN" and seen["keep_el"] is True and seen["with_actions"] is False


# ---------------------------------------------------------------------------
# Window lookup with PT off the current Space (ISSUES X13)
# ---------------------------------------------------------------------------

MAIN_FRAME = [0.0, 49.0, 1470.0, 851.0]
R1_FRAME = [335.0, 33.0, 800.0, 923.0]
MAIN_TITLE = "Cisco Packet Tracer - /Users/x/lab.pkt"


@pytest.fixture
def lookup(monkeypatch):
    """AX lists played one per `ax_windows` call (the last one repeats)."""
    state = SimpleNamespace(answers=[], calls=0)

    def ax_windows(pid):
        state.calls += 1
        return state.answers.pop(0) if len(state.answers) > 1 else state.answers[0]

    state.attrs = {}
    state.sets = []

    def set_attr(el, name, value):
        state.sets.append((el, name, value))
        state.attrs[(el, name)] = value
        return 0

    monkeypatch.setattr(mac_ax, "attr", lambda el, name: state.attrs.get((el, name)))
    monkeypatch.setattr(mac_ax, "set_attr", set_attr)
    monkeypatch.setattr(mac_windows, "ax_windows", ax_windows)
    monkeypatch.setattr(mac_windows, "cg_windows", lambda pid: [
        {"cg_id": 2431, "name": "R1", "layer": 0, "onscreen": True, "frame": R1_FRAME},
        {"cg_id": 528, "name": MAIN_TITLE, "layer": 0, "onscreen": True, "frame": MAIN_FRAME},
    ])
    state.io = FakeIO()
    state.backend = MacBackend(io=state.io, responsible=lambda: ("claude", None))
    return state


class TestWindowLookupOffSpace:
    # Live 2026-10-25: with Claude in front and PT on another Space, PT's
    # AXWindows read [] and every show/capture said "Can't find Packet
    # Tracer's main window"; after `open -a` the same calls worked.

    def test_no_window_listed_brings_pt_forward_then_finds_it(self, lookup):
        lookup.answers = [[], [], [("MAINWIN", MAIN_TITLE, MAIN_FRAME)]]
        assert lookup.backend.main_window(PID) == 528
        assert lookup.io.log.count(("open_app", PID)) == 1

    def test_a_dialog_is_found_after_bringing_pt_forward(self, lookup):
        lookup.answers = [[], [("MAINWIN", MAIN_TITLE, MAIN_FRAME), ("R1WIN", "R1", R1_FRAME)]]
        assert lookup.backend.find_window(PID, "R1") == 2431
        assert lookup.io.log == [("open_app", PID)]

    def test_listed_windows_never_activate_pt(self, lookup):
        # A dialog that is not open yet (the presenter polls for it after the
        # click) must not pull PT forward on every poll.
        lookup.answers = [[("MAINWIN", MAIN_TITLE, MAIN_FRAME)]]
        assert lookup.backend.find_window(PID, "R1") is None
        assert lookup.backend.main_window(PID) == 528
        assert lookup.io.log == []

    def test_gives_up_when_pt_never_lists_a_window(self, lookup):
        lookup.answers = [[]]
        assert lookup.backend.main_window(PID) is None
        assert lookup.io.log == [("open_app", PID)]
        assert lookup.calls <= 1 + MacBackend.WINDOW_POLLS


FULL_FRAME = [0.0, 33.0, 1470.0, 923.0]


class TestFullScreen:
    # Live 2026-10-25: with PT's main window in full screen, a dialog opened by
    # click got a full-screen Space of its own (capture 2940x1846, mostly
    # blank) and the next call could not find the main window. Out of full
    # screen, every dialog opened and was captured at its own size.

    def test_full_screen_main_window_is_taken_out_then_found_at_its_new_frame(self, lookup):
        lookup.attrs[("MAINWIN", "AXFullScreen")] = True
        lookup.answers = [[("MAINWIN", MAIN_TITLE, FULL_FRAME)],
                          [("MAINWIN", MAIN_TITLE, MAIN_FRAME)]]
        assert lookup.backend.main_window(PID) == 528
        assert lookup.sets == [("MAINWIN", "AXFullScreen", False)]

    def test_a_dialog_lookup_also_leaves_full_screen_first(self, lookup):
        lookup.attrs[("MAINWIN", "AXFullScreen")] = True
        lookup.answers = [[("MAINWIN", MAIN_TITLE, FULL_FRAME)],
                          [("MAINWIN", MAIN_TITLE, MAIN_FRAME), ("R1WIN", "R1", R1_FRAME)]]
        assert lookup.backend.find_window(PID, "R1") == 2431
        assert lookup.sets == [("MAINWIN", "AXFullScreen", False)]

    def test_windowed_pt_is_left_alone(self, lookup):
        lookup.attrs[("MAINWIN", "AXFullScreen")] = False
        lookup.answers = [[("MAINWIN", MAIN_TITLE, MAIN_FRAME)]]
        assert lookup.backend.main_window(PID) == 528
        assert lookup.sets == []

    def test_a_full_screen_dialog_is_not_touched(self, lookup):
        lookup.attrs[("R1WIN", "AXFullScreen")] = True
        lookup.answers = [[("MAINWIN", MAIN_TITLE, MAIN_FRAME), ("R1WIN", "R1", R1_FRAME)]]
        assert lookup.backend.find_window(PID, "R1") == 2431
        assert lookup.sets == []


TOOLBAR = "PtApp.CAppWindowBase.m_pPlToolBar.QToolButton"


@pytest.fixture
def tools(stub, monkeypatch):
    """The main window's tool buttons; Select is off when the click comes."""
    names = ["Select (Esc)", "Delete (Del)", "Place Note (N)", "Add Complex PDU (C)"]
    els = [ui(n, Role.CHECKBOX, MAIN, n, ident=TOOLBAR) for n in names]
    for n in names:
        stub.attrs[n] = {"AXValue": 0}
    stub.attrs["Add Complex PDU (C)"]["AXValue"] = 1
    monkeypatch.setattr(stub.backend, "elements", lambda handle, role=None: els)
    return stub


class TestSelectToolAtTheClick:
    def test_select_is_turned_back_on_then_the_click_goes(self, tools):
        def perform(el, action):
            tools.log.append(("perform", el, action))
            tools.attrs[el]["AXValue"] = 1
            return 0
        mac_ax.perform = perform  # monkeypatched by the fixture, restored after
        assert tools.backend.click(MAIN, 299, 330) == "cursor-restored"
        assert ("perform", "Select (Esc)", "AXPress") in tools.log
        assert ("click", 299, 330) in tools.io.log

    def test_select_that_stays_off_refuses_and_names_the_tool(self, tools):
        with pytest.raises(BackendError, match=r"Add Complex PDU \(C\).*not clicking"):
            tools.backend.click(MAIN, 299, 330)
        assert not [a for a in tools.io.log if a[0] == "click"]

    def test_select_already_on_is_not_pressed(self, tools):
        tools.attrs["Select (Esc)"]["AXValue"] = 1
        tools.attrs["Add Complex PDU (C)"]["AXValue"] = 0
        tools.backend.click(MAIN, 299, 330)
        assert not [a for a in tools.log if a[0] == "perform"]
        assert ("click", 299, 330) in tools.io.log
