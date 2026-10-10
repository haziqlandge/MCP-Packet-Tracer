"""Host facts: OS, the PT processes and the app macOS asks for permissions.

`responsible_app` names the app the user must grant Accessibility and Screen
Recording to. It is pure over an injected `ps`, so the recorded chains run on
every OS. The first chain is the one measured on the executor Mac in PHASE-00.
"""

from __future__ import annotations

import platform as stdlib_platform
import subprocess

import pytest

from src.packet_tracer_mcp.infrastructure.platform.base import detect_os
from src.packet_tracer_mcp.infrastructure.platform.host import (
    host_info, pt_processes, responsible_app, responsible_bundle,
)

BREW_PY = ("/opt/homebrew/Cellar/python@3.12/3.12.15/Frameworks/Python.framework/"
           "Versions/3.12/Resources/Python.app/Contents/MacOS/Python")
CLAUDE_CLI = ("/Users/u/Library/Application Support/Claude/claude-code/2.1.293/8433d0d9cd0d/"
              "claude.app/Contents/MacOS/claude")

CHAINS = {
    # PREVIOUS_WORK 2.4 #9: Claude desktop's Code tab, measured 2026-10-10.
    "claude_code_tab": {
        11767: (11766, BREW_PY), 11766: (10832, "/bin/zsh"), 10832: (10831, CLAUDE_CLI),
        10831: (6977, "/Applications/Claude.app/Contents/Helpers/disclaimer"),
        6977: (1, "/Applications/Claude.app/Contents/MacOS/Claude"),
    },
    "claude_desktop": {
        500: (400, "/Users/u/proj/.venv/bin/python"),
        400: (1, "/Applications/Claude.app/Contents/MacOS/Claude"),
    },
    "terminal": {
        500: (400, BREW_PY), 400: (300, "-zsh"), 300: (200, "/usr/bin/login"),
        200: (1, "/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal"),
    },
    "iterm2": {
        500: (400, "/bin/zsh"), 400: (1, "/Applications/iTerm.app/Contents/MacOS/iTerm2"),
    },
    "vscode": {
        500: (400, "/bin/zsh"),
        400: (1, "/Applications/Visual Studio Code.app/Contents/Frameworks/"
                 "Code Helper (Plugin).app/Contents/MacOS/Code Helper (Plugin)"),
    },
    "no_app": {500: (400, "/usr/bin/python3"), 400: (1, "/usr/sbin/sshd")},
}
START = {"claude_code_tab": 11767}


def ps_for(chain):
    return lambda pid: chain.get(pid)


@pytest.mark.parametrize("name, expected", [
    ("claude_code_tab", "claude"),   # never "Python": the interpreter's own bundle is skipped
    ("claude_desktop", "Claude"),
    ("terminal", "Terminal"),
    ("iterm2", "iTerm"),
    ("vscode", "Visual Studio Code"),  # the outer bundle, not the helper
    ("no_app", None),
])
def test_responsible_app_on_recorded_chains(name, expected):
    chain = CHAINS[name]
    assert responsible_app(START.get(name, 500), ps=ps_for(chain), os_name="macos") == expected


def test_responsible_bundle_is_the_full_path():
    # The CLI's path is versioned; the remedy text must name all of it.
    chain = CHAINS["claude_code_tab"]
    assert responsible_bundle(11767, ps=ps_for(chain), os_name="macos") == CLAUDE_CLI.split(
        "/Contents/MacOS/")[0]


def test_responsible_app_is_none_off_macos():
    chain = CHAINS["claude_desktop"]
    assert responsible_app(500, ps=ps_for(chain), os_name="windows") is None


def test_a_failing_ps_gives_none():
    assert responsible_app(500, ps=lambda pid: None, os_name="macos") is None


def test_a_cycle_terminates():
    cycle = {500: (400, "/bin/zsh"), 400: (500, "/bin/zsh")}
    assert responsible_app(500, ps=ps_for(cycle), os_name="macos") is None


def test_host_info_describes_this_interpreter():
    info = host_info()
    assert info.os == detect_os()
    assert info.python == stdlib_platform.python_version()
    assert info.arch == stdlib_platform.machine()


class TestPtProcesses:
    @staticmethod
    def run_returning(stdout: str, calls: list):
        def run(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")
        return run

    def test_macos_matches_the_exact_process_name(self):
        calls: list = []
        pids = pt_processes(os_name="macos", run=self.run_returning("10015\n10018\n", calls))
        assert pids == [10015, 10018]
        # Measured: PT's process (and its progress-bar helper) are named PacketTracer.
        assert calls == [["pgrep", "-x", "PacketTracer"]]

    def test_windows_parses_tasklist_csv(self):
        calls: list = []
        out = '"PacketTracer.exe","4242","Console","1","512,000 K"\n'
        assert pt_processes(os_name="windows", run=self.run_returning(out, calls)) == [4242]

    def test_any_failure_is_an_empty_list(self):
        def boom(args, **kwargs):
            raise FileNotFoundError("pgrep")
        assert pt_processes(os_name="linux", run=boom) == []
