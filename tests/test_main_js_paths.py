"""The extension's own path choice (EXTENSION/script-engine/main.js, INTERFACES §5).

Released V5.2's `mcpBridgeDir()` returned the directory of the FIRST token
candidate, `<home>/AppData/Local/...`, without checking that a token was there;
on a Mac it polled a different mailbox from the one Python wrote to (ISSUES X1,
measured in PREVIOUS_WORK 2.4 #4). These run the real main.js under node with a
stub `ipc`; they skip when node is not installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = ROOT / "EXTENSION" / "script-engine" / "main.js"
HARNESS = Path(__file__).parent / "js" / "main_paths_harness.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(user_folder: str, files: list[str]) -> dict:
    out = subprocess.run(
        [NODE, str(HARNESS), str(MAIN_JS), json.dumps({"userFolder": user_folder, "files": files})],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


def test_macos_token_in_local_state_gives_that_mailbox():
    r = run("/Users/u/Cisco Packet Tracer 9.0.1",
            ["/Users/u/.local/state/packet-tracer-mcp/bridge_token"])
    assert r["bridgeDir"] == "/Users/u/.local/state/packet-tracer-mcp/bridge"
    assert r["candidates"][0] == "/Users/u/.local/state/packet-tracer-mcp/bridge_token"


def test_windows_user_folder_keeps_appdata_first():
    r = run("C:/Users/u/Cisco Packet Tracer 9.0.1",
            ["C:/Users/u/AppData/Local/packet-tracer-mcp/bridge_token"])
    assert r["bridgeDir"] == "C:/Users/u/AppData/Local/packet-tracer-mcp/bridge"
    assert r["candidates"][0] == "C:/Users/u/AppData/Local/packet-tracer-mcp/bridge_token"


def test_windows_backslashes_are_normalised():
    r = run("C:\\Users\\u\\Cisco Packet Tracer 9.0.1",
            ["C:/Users/u/AppData/Local/packet-tracer-mcp/bridge_token"])
    assert r["bridgeDir"] == "C:/Users/u/AppData/Local/packet-tracer-mcp/bridge"


def test_linux_pt_folder():
    r = run("/home/u/pt", ["/home/u/.local/state/packet-tracer-mcp/bridge_token"])
    assert r["bridgeDir"] == "/home/u/.local/state/packet-tracer-mcp/bridge"


def test_a_user_folder_nested_under_documents_still_finds_home():
    r = run("/Users/u/Documents/Cisco Packet Tracer 9.0.1",
            ["/Users/u/.local/state/packet-tracer-mcp/bridge_token"])
    assert r["bridgeDir"] == "/Users/u/.local/state/packet-tracer-mcp/bridge"


def test_no_token_gives_the_os_default_and_is_not_cached():
    r = run("/Users/u/Cisco Packet Tracer 9.0.1", [])
    assert r["bridgeDir"] == "/Users/u/.local/state/packet-tracer-mcp/bridge"
    # Cached only once a token was found: a server started after PT must still pair.
    assert r["cachedAfterTick"] == ""
