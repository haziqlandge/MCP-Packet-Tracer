"""Recorded AX trees → UiElements, through the same `to_element` the live backend uses.

The fixtures are PT 9.0.1 on macOS 26.5.1 (`devtools/macos_probe.py ax`), so the
conversion is tested on real data (PLAN/INTERFACES.md §7). Pure Python: runs on
every OS.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from src.packet_tracer_mcp.infrastructure.ui.backend import Role
from src.packet_tracer_mcp.infrastructure.ui.backends.macos import ax

FIXTURES = Path(__file__).parent / "fixtures" / "macos"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def elements(name: str):
    return ax.elements_from_tree(load(name)["tree"])


def _nodes(tree: dict):
    yield tree
    for c in tree["children"]:
        yield from _nodes(c)


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.json")))
def test_every_node_below_the_window_becomes_an_element(name):
    tree = load(name)["tree"]
    els = ax.elements_from_tree(tree)
    assert len(els) == sum(1 for _ in _nodes(tree)) - 1  # the window itself is the root
    counts = Counter(e.role for e in els)
    ax_counts = Counter(n["role"] for n in _nodes(tree))
    assert counts[Role.BUTTON] == ax_counts["AXButton"]
    assert counts[Role.CHECKBOX] == ax_counts["AXCheckBox"]
    assert counts[Role.EDIT] == ax_counts["AXTextField"] + ax_counts["AXTextArea"]
    assert counts[Role.STATIC] == ax_counts["AXStaticText"]


def test_tabs_are_the_radio_buttons_of_the_tab_group():
    tabs = [e.name for e in elements("PC1-desktop.json") if e.role is Role.TAB]
    assert tabs == ["Physical", "Config", "Desktop", "Programming", "Attributes"]
    assert [e.name for e in elements("R1-cli.json") if e.role is Role.TAB] == [
        "Physical", "Config", "CLI", "Attributes"]


def test_radio_buttons_outside_a_tab_group_are_not_tabs():
    els = {e.name: e for e in elements("SRV1-services-dhcp.json")}
    assert els["On"].role is Role.OTHER and els["Off"].role is Role.OTHER
    assert els["Services"].role is Role.TAB


def test_names_fall_back_to_the_description():
    # Applet title labels carry their text in AXDescription, not AXTitle.
    titles = [e for e in elements("PC1-desktop-command_prompt.json")
              if e.ident.endswith("m_titleBar.m_titleLabel")]
    assert [e.name for e in titles] == ["Command Prompt "]
    assert titles[0].role is Role.STATIC


def test_select_tool_and_its_state_value():
    sel = next(e for e in elements("main-window.json") if e.name == "Select (Esc)")
    assert sel.role is Role.CHECKBOX
    assert sel.ident == "PtApp.CAppWindowBase.m_pPlToolBar.QToolButton"
    assert sel.raw["value"] == "1"


def test_rect_is_left_top_right_bottom_in_points():
    canvas = next(e for e in elements("main-window.json") if e.ident.endswith("m_workspaceWS"))
    assert canvas.rect == (0, 180, 1512, 706)
    assert canvas.offscreen is False


def test_cells_are_list_items_and_tables_rows():
    roles = Counter(e.role for e in elements("SRV1-services-dhcp.json"))
    assert roles[Role.LIST_ITEM] == 9  # 1 AXRow + 8 AXCell


class TestOffscreen:
    WIN = [0.0, 0.0, 100.0, 100.0]

    def node(self, frame, role="AXButton"):
        return {"role": role, "subrole": "", "title": "b", "description": "", "identifier": "a.b",
                "value": "", "frame": frame, "actions": [], "children": []}

    def test_inside(self):
        assert ax.to_element(self.node([10, 10, 20, 20]), self.WIN).offscreen is False

    def test_partly_inside_counts_as_visible(self):
        assert ax.to_element(self.node([90, 90, 20, 20]), self.WIN).offscreen is False

    @pytest.mark.parametrize("frame", [[200, 10, 20, 20], [10, 10, 0, 20], None])
    def test_outside_zero_size_or_unknown(self, frame):
        assert ax.to_element(self.node(frame), self.WIN).offscreen is True
