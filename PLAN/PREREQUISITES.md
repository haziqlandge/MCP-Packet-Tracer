# PREREQUISITES

Everything the Mac needs before and during the phases. Install notes that cost
time go to "Hard-won notes" at the bottom, numbered, as they are learned.

## Required — software

| Item | Version / note | Used by |
|---|---|---|
| macOS | Record `sw_vers` in PHASE-00. 14+ for the SCK capture path | all |
| Rosetta 2 | Needed on Apple Silicon if PT is x86-64 (`softwareupdate --install-rosetta`). PT 9.0.1 is universal: not needed (2026-10-10) | PT |
| Cisco Packet Tracer | 9.0.x for macOS, already installed on the Mac (user, 2026-10-10) | PHASE-00 onward |
| MCP Control Center `.pts` | V5.2 from upstream Releases (`docs/live-deploy.md`) | PHASE-00 onward |
| Python | ≥ 3.11, **not** the system `/usr/bin/python3`. uv (`uv python install 3.13`) or python.org | all |
| git | Xcode Command Line Tools (`xcode-select --install`) | all |
| node | Optional. Any LTS (`brew install node`). Only for the `main.js` test | PHASE-02 |
| An MCP client | Claude Code (terminal) and/or Claude Desktop. Record which ones the user runs | PHASE-00, 06, 07 |

## Required — packages

| Package | Purpose | Phase |
|---|---|---|
| `packet-tracer-mcp` (this checkout, `pip install -e ".[test]"`) | the server and tests | 00 |
| `pyobjc-core`, `pyobjc-framework-Cocoa`, `pyobjc-framework-Quartz`, `pyobjc-framework-ApplicationServices`, `pyobjc-framework-ScreenCaptureKit` | macOS backend. Installed by hand in PHASE-00, then pulled in by environment markers from PHASE-04 | 00, 04 |
| `pytest`, `pyflakes` | already in the `test` extra | all |

## Required — accounts and credentials

| Account | For | Cost | Notes |
|---|---|---|---|
| GitHub access to `haziqlandge/MCP-Packet-Tracer` | clone the branch, push from the Mac | free | The branch must be pushed from Windows first (`FUTURE_WORK.md` §0) |
| Cisco NetAcad | only if PT must be reinstalled | free | PT is already installed |

Environment variables (names only): `PT_MCP_BRIDGE_TOKEN` (tests; avoids the real
token file), `PT_MCP_UI_BACKEND` (force `null` to test the headless path),
`PT_MCP_OUTPUT_DIR` (optional output root).

## Required — macOS permissions (granted to the client app, not to Python)

| Permission | Needed for | When |
|---|---|---|
| Accessibility | AX tree, AXPress, posted clicks | first UI-mode use (PHASE-04/05) |
| Screen Recording | window capture | first capture (PHASE-04) |

Which app gets the grant is answered in PHASE-00 (`RESEARCH/SYNTHESIS.md` §9, question 9).

## Optional

| Item | Value | Why optional |
|---|---|---|
| Accessibility Inspector (Xcode) | browse PT's AX tree by hand while writing locators | `macos_probe.py` dumps the same data |
| PTBuilder reference files | needed to build a `.pts` (`EXTENSION/script-engine/README.md`) | only if PHASE-00 finds a way to build one on the Mac |
| A second Mac user account | a cleaner out-of-the-box run in PHASE-07 | deleting the state dir and venv is enough |

## Hard-won notes

1. GUI apps on macOS do not inherit the shell's PATH. An MCP config with
   `"command": "python3"` can resolve to the system Python 3.9 and crash on
   `requires-python`. Use an absolute interpreter path (`pt-mcp doctor
   --print-config`). Expected from SYNTHESIS §6; confirm in PHASE-00.
2. Under Claude desktop's Code tab the macOS grants go to the bundled Claude Code
   CLI, `~/Library/Application Support/Claude/claude-code/<version>/<hash>/claude.app`,
   not to `Claude.app`. In System Settings use **+**, then Cmd+Shift+G and paste the
   path. Measured 2026-10-10 (PREVIOUS_WORK 2.4 #9).
3. PT listens on TCP 39000 on macOS, the MCP server's default HTTP port. Use the
   stdio transport, or another port for HTTP (ISSUES X8).
