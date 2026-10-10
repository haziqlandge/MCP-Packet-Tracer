"""WindowsBackend adapts win32 + Uia without changing what they do (CONSTRAINTS C4).

UIA cannot run here, so `Uia` is replaced by a fake that records the exact calls
the old presenter made (`descendants(h, "TabItem")`, `invoke`, ...). The real
`uia.Element` is kept as `raw`, which is what every action unwraps.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.packet_tracer_mcp.infrastructure.ui.backend import Capture, Role
from src.packet_tracer_mcp.infrastructure.ui.backends.windows import backend as wb
from src.packet_tracer_mcp.infrastructure.ui.backends.windows.uia import Element

# Control type ids as comtypes' generated UIAutomationClient module names them.
M = SimpleNamespace(
    UIA_TabItemControlTypeId=50019, UIA_ButtonControlTypeId=50000,
    UIA_CheckBoxControlTypeId=50002, UIA_ListItemControlTypeId=50007,
    UIA_EditControlTypeId=50004, UIA_ScrollBarControlTypeId=50014,
    UIA_TextControlTypeId=50020, UIA_WindowControlTypeId=50032,
)


class FakeUia:
    calls: list = []
    tree: list = []

    def __init__(self):
        self.m = M
        FakeUia.calls.append(("init",))

    def descendants(self, hwnd, control_type=None):
        FakeUia.calls.append(("descendants", hwnd, control_type))
        return list(FakeUia.tree)

    def select(self, el):
        FakeUia.calls.append(("select", el))

    def invoke(self, el):
        FakeUia.calls.append(("invoke", el))

    def toggle_state(self, el):
        return 1

    def range_value(self, el):
        return 12.5

    def set_value(self, el, text):
        FakeUia.calls.append(("set_value", el, text))

    def scroll_to_end(self, el):
        FakeUia.calls.append(("scroll_to_end", el))


def _uia_el(aid, ct, name="n", offscreen=False):
    raw = SimpleNamespace(CurrentBoundingRectangle=SimpleNamespace(left=1, top=2, right=3, bottom=4))
    return Element(raw=raw, name=name, automation_id=aid, control_type=ct, offscreen=offscreen)


@pytest.fixture
def backend(monkeypatch):
    FakeUia.calls = []
    FakeUia.tree = []
    monkeypatch.setattr(wb, "Uia", FakeUia)
    return wb.WindowsBackend()


def test_elements_map_uia_to_ui_elements(backend):
    tab = _uia_el("a.qt_tabwidget_tabbar.Desktop", 50019, "Desktop")
    odd = _uia_el("a.b", 99999)
    FakeUia.tree = [tab, odd]
    els = backend.elements(7)
    assert [(e.name, e.ident, e.role, e.offscreen) for e in els] == [
        ("Desktop", "a.qt_tabwidget_tabbar.Desktop", Role.TAB, False), ("n", "a.b", Role.OTHER, False)]
    assert els[0].raw is tab
    assert els[0].rect == (1, 2, 3, 4)
    assert FakeUia.calls[-1] == ("descendants", 7, None)


@pytest.mark.parametrize("role, uia_name", [
    (Role.TAB, "TabItem"), (Role.BUTTON, "Button"), (Role.SCROLLBAR, "ScrollBar"),
    (Role.CHECKBOX, "CheckBox"), (Role.LIST_ITEM, "ListItem"), (Role.EDIT, "Edit"),
    (Role.STATIC, "Text"), (Role.WINDOW, "Window"),
])
def test_role_filter_uses_the_uia_condition(backend, role, uia_name):
    backend.elements(7, role)
    assert FakeUia.calls[-1] == ("descendants", 7, uia_name)


def test_actions_unwrap_raw(backend):
    raw = _uia_el("x", 50000)
    FakeUia.tree = [raw]
    el = backend.elements(1)[0]
    backend.select(el)
    backend.press(el)
    backend.set_value(el, "http://10.0.0.1")
    backend.scroll_to_end(el)
    assert backend.toggle_state(el) == 1 and backend.range_value(el) == 12.5
    acts = [c for c in FakeUia.calls if c[0] not in ("init", "descendants")]
    assert acts == [("select", raw), ("invoke", raw), ("set_value", raw, "http://10.0.0.1"),
                    ("scroll_to_end", raw)]


def test_each_operation_initialises_com_on_its_own_thread(backend):
    # The old presenter built a Uia() (CoInitializeEx) per call; tool calls run
    # on worker threads, so the backend must not keep one across calls.
    backend.elements(1)
    backend.elements(1)
    assert [c for c in FakeUia.calls if c[0] == "init"] == [("init",), ("init",)]


def test_window_calls_go_to_win32(monkeypatch, backend):
    seen = []
    fake = SimpleNamespace(
        find_window=lambda pid, t: seen.append(("find", pid, t)) or 11,
        main_window=lambda pid: seen.append(("main", pid)) or 12,
        raise_window=lambda h: seen.append(("raise", h)),
        capture=lambda h: (2, 1, b"\x01\x02\x03\x04" * 2),
        post_click=lambda h, x, y: seen.append(("click", h, x, y)) or (5, 6),
        is_supported=lambda: True,
    )
    monkeypatch.setattr(wb, "win32", fake)
    assert backend.find_window(3, "PC1") == 11 and backend.main_window(3) == 12
    backend.raise_window(11)
    assert backend.capture(11) == Capture(2, 1, b"\x01\x02\x03\x04" * 2)
    assert backend.click(12, 100, 200) == "posted"
    assert seen == [("find", 3, "PC1"), ("main", 3), ("raise", 11), ("click", 12, 100, 200)]


def test_available_keeps_the_windows_wording(monkeypatch, backend):
    monkeypatch.setattr(wb.win32, "is_supported", lambda: False)
    assert backend.available() == (False, "presenting in PT's GUI only works on Windows")
