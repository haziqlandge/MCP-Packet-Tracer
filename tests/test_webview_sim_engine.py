"""The Simulation tab's engine helpers survive the trip to PT's Script Engine.

The webview installs them with $se("runCode", SIM_ENGINE_JS). PT's webview ->
Script Engine IPC drops the newlines, so the helpers' first // comment swallowed
the rest: runCode raised "SyntaxError: Parse error", mcpDemoDevices was never
defined, and the tab showed "Could not read the topology from PT." (seen live on
the Mac, 2026-10-26). These run the real interface.js under node and skip when
node is not installed. That PT strips the newlines is only checked live.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INTERFACE_JS = ROOT / "EXTENSION" / "webview" / "interface.js"
HARNESS = Path(__file__).parent / "js" / "interface_sim_engine_harness.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run() -> dict:
    out = subprocess.run(
        [NODE, str(HARNESS), str(INTERFACE_JS)],
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True,
    )
    return json.loads(out.stdout)


def test_sim_engine_js_is_one_line():
    assert run()["newlines"] == 0


def test_helpers_install_after_newlines_are_stripped():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["devices"] == {"pcs": ["PC1", "PC2"], "servers": ["Srv"], "window_sim": True}
