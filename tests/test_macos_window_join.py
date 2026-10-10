"""The AX window ↔ CGWindowID join (PLAN/phases/PHASE-04.md, with its amendment).

The CG list below is the one recorded on the executor Mac in PHASE-00
(PREVIOUS_WORK 2.4 #7): PT opens every device dialog at the same frame, and keeps
an off-screen twin of the Control Center window. Frames are points.
"""

from __future__ import annotations

from src.packet_tracer_mcp.infrastructure.ui.backends.macos.windows import (
    frames_match, join_window, title_matches,
)

MAIN = [0.0, 33.0, 1512.0, 876.0]
DIALOG = [406.0, 103.0, 700.0, 708.0]
BUILDER = [200.0, 172.0, 800.0, 528.0]


def cg(cg_id, name, frame, *, layer=0, onscreen=True):
    return {"cg_id": cg_id, "name": name, "layer": layer, "onscreen": onscreen, "frame": frame}


RECORDED = [  # front to back, as CGWindowListCopyWindowInfo lists them
    cg(4863, "PC1", DIALOG),
    cg(4859, "R1", DIALOG),
    cg(3578, "Logs - MCP BUILDER", BUILDER),
    cg(3513, "Logs - MCP BUILDER", BUILDER, onscreen=False),
    cg(3510, "Cisco Packet Tracer - ~/x.pkt", MAIN),
    cg(3505, "", [396.0, 288.0, 720.0, 405.0], layer=101, onscreen=False),
]


def test_exact_bounds():
    assert join_window(MAIN, RECORDED, "Cisco Packet Tracer - ~/x.pkt") == 3510


def test_rounding_within_one_point():
    assert join_window([0.4, 33.6, 1511.5, 876.9], RECORDED) == 3510
    assert frames_match([0.4, 33.6, 1511.5, 876.9], MAIN)
    assert not frames_match([2.0, 33.0, 1512.0, 876.0], MAIN)


def test_same_bounds_are_told_apart_by_title():
    assert join_window(DIALOG, RECORDED, "R1") == 4859
    assert join_window(DIALOG, RECORDED, "PC1") == 4863


def test_without_names_the_frontmost_candidate_wins():
    # No Screen Recording: CG names are empty, so the join cannot be exact.
    anonymous = [dict(w, name="") for w in RECORDED]
    assert join_window(DIALOG, anonymous, "R1") == 4863


def test_the_on_screen_twin_wins():
    assert join_window(BUILDER, list(reversed(RECORDED)), "Logs - MCP BUILDER") == 3578


def test_other_layers_never_match():
    assert join_window([396.0, 288.0, 720.0, 405.0], RECORDED) is None


def test_no_match():
    assert join_window([1.0, 2.0, 3.0, 4.0], RECORDED, "R1") is None
    assert join_window(None, RECORDED, "R1") is None


def test_title_matching_is_exact_for_dialogs_and_prefix_for_the_main_window():
    # Same rules as the Windows backend's find_window / main_window.
    assert title_matches("R1", "R1") and not title_matches("R10", "R1")
    assert title_matches("Cisco Packet Tracer - ~/x.pkt", "Cisco Packet Tracer", prefix=True)
    assert not title_matches("Logs - MCP BUILDER", "Cisco Packet Tracer", prefix=True)
