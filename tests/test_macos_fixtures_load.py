"""Every recorded macOS AX fixture is well-formed (PLAN/INTERFACES.md §7).

The fixtures are recorded from the real Packet Tracer by
`devtools/macos_probe.py ax`; the macOS backend's offline tests rest on them, so a
malformed or unredacted recording must fail here rather than in those tests.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "macos"
TOP_KEYS = {"recorded", "macos", "pt", "qt", "scale", "window", "tree"}
WINDOW_KEYS = {"title", "cg_id", "frame"}
NODE_KEYS = {"role", "subrole", "title", "description", "identifier", "value",
             "frame", "actions", "children"}
MAX_DEPTH = 40
MAX_NODES = 5000
VALUE_CAP = 200
HOME_PATH = re.compile(r"/Users/[^/\"\s]+")


def _fixtures() -> list[Path]:
    return sorted(FIXTURES.glob("*.json")) if FIXTURES.is_dir() else []


def _walk(node: dict, depth: int, stats: dict) -> None:
    assert set(node) == NODE_KEYS, f"node keys {sorted(node)}"
    assert isinstance(node["role"], str) and node["role"]
    assert isinstance(node["actions"], list)
    assert len(node["value"]) <= VALUE_CAP
    assert node["frame"] is None or len(node["frame"]) == 4
    stats["nodes"] += 1
    stats["depth"] = max(stats["depth"], depth)
    for child in node["children"]:
        _walk(child, depth + 1, stats)


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.name)
def test_fixture_is_well_formed(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert set(data) == TOP_KEYS
    assert set(data["window"]) == WINDOW_KEYS
    assert data["scale"] > 0
    assert data["tree"]["role"] == "AXWindow"
    stats = {"nodes": 0, "depth": 0}
    _walk(data["tree"], 0, stats)
    assert stats["nodes"] <= MAX_NODES
    assert stats["depth"] <= MAX_DEPTH
    assert not HOME_PATH.search(raw), "home path not redacted to ~"
