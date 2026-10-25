"""The Control Center editor's shortcuts follow the OS (EXTENSION/webview).

Before, the editor showed Windows hints everywhere (Ctrl+Enter, Ctrl+K) and took
Control *or* Command on every OS, so on a Mac Control+K, the text system's
"delete to end of line", cleared the whole editor. These run the real
interface.js under node with a stub navigator and document; they skip when node
is not installed. Whether PT's own webview reports a Mac platform and passes
Command through as metaKey can only be checked live, in PT.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INTERFACE_JS = ROOT / "EXTENSION" / "webview" / "interface.js"
INDEX_HTML = ROOT / "EXTENSION" / "webview" / "index.html"
HARNESS = Path(__file__).parent / "js" / "interface_shortcuts_harness.js"
NODE = shutil.which("node")

MAC = {"platform": "MacIntel",
       "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) QtWebEngine/6.5.3 Chrome/108.0.5359.220 Safari/537.36"}
WINDOWS = {"platform": "Win32",
           "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) QtWebEngine/6.5.3 Chrome/108.0.5359.220 Safari/537.36"}
LINUX = {"platform": "Linux x86_64", "userAgent": "Mozilla/5.0 (X11; Linux x86_64)"}

needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(env: dict, keys: list[dict] | None = None) -> dict:
    scenario = dict(env, keys=keys or [])
    out = subprocess.run(
        [NODE, str(HARNESS), str(INTERFACE_JS), json.dumps(scenario)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


@needs_node
def test_mac_hints_show_command():
    r = run(MAC)
    assert r["isMac"] is True
    assert r["hints"] == {
        "runKbd": "⌘↩",
        "clearKbd": "⌘K",
        "runTitle": "Run (⌘↩)",
        "clearLogTitle": "Clear log (⌘L)",
    }


@needs_node
@pytest.mark.parametrize("env", [WINDOWS, LINUX], ids=["windows", "linux"])
def test_other_os_hints_show_ctrl(env):
    r = run(env)
    assert r["isMac"] is False
    assert r["hints"] == {
        "runKbd": "Ctrl+Enter",
        "clearKbd": "Ctrl+K",
        "runTitle": "Run (Ctrl+Enter)",
        "clearLogTitle": "Clear log (Ctrl+L)",
    }


@needs_node
def test_mac_command_shortcuts_run():
    r = run(MAC, [{"key": "Enter", "metaKey": True},
                  {"key": "k", "metaKey": True},
                  {"key": "l", "metaKey": True},
                  {"key": "K", "metaKey": True}])  # Caps Lock on
    assert r["pressed"] == [["run"], ["clear"], ["clearLog"], ["clear"]]


@needs_node
def test_mac_control_keys_are_left_to_the_text_system():
    # Control+K deletes to the end of the line on a Mac; it must not clear the editor.
    r = run(MAC, [{"key": "Enter", "ctrlKey": True},
                  {"key": "k", "ctrlKey": True},
                  {"key": "l", "ctrlKey": True}])
    assert r["pressed"] == [[], [], []]


@needs_node
def test_windows_ctrl_shortcuts_run_and_the_windows_key_does_not():
    r = run(WINDOWS, [{"key": "Enter", "ctrlKey": True},
                      {"key": "k", "ctrlKey": True},
                      {"key": "l", "ctrlKey": True},
                      {"key": "k", "metaKey": True}])
    assert r["pressed"] == [["run"], ["clear"], ["clearLog"], []]


@needs_node
def test_extra_modifiers_do_not_trigger():
    r = run(MAC, [{"key": "k", "metaKey": True, "shiftKey": True},
                  {"key": "k", "metaKey": True, "altKey": True},
                  {"key": "k", "metaKey": True, "ctrlKey": True}])
    assert r["pressed"] == [[], [], []]


def test_every_modifier_hint_in_index_html_is_rewritten_per_os():
    # A hint written only in the HTML would stay "Ctrl+..." on a Mac.
    html = INDEX_HTML.read_text(encoding="utf-8")
    for m in re.finditer(r"<span[^>]*class=\"kbd\"[^>]*>([^<]*)</span>", html):
        if "Ctrl" in m.group(1):
            assert "data-shortcut=" in m.group(0), m.group(0)
    for m in re.finditer(r"<[a-z]+[^>]*title=\"[^\"]*Ctrl\+[^\"]*\"[^>]*>", html):
        assert "data-shortcut-title=" in m.group(0) and "data-title=" in m.group(0), m.group(0)
