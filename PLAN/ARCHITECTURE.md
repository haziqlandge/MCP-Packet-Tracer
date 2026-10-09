# ARCHITECTURE

The authoritative description of the cross-platform structure. Phase files point
here instead of restating it. The existing layering
(domain → application → infrastructure → adapters, see `AGENTS.md` and
`CODEMAP.md`) is unchanged. This plan adds two seams inside `infrastructure/`.

## System overview

```
 MCP client (Claude Code / Claude Desktop / other)
        │ stdio or streamable-http (:39000)
 ┌──────▼──────────────────────────────────────────────────────────┐
 │ adapters/mcp: tools/<topic>.py, device_panel_tools, desktop_*    │  OS-agnostic. Never imports a backend
 └──────┬───────────────────────────────────────┬──────────────────┘
        │ BridgeContext                          │ PanelSupport → Presenter
 ┌──────▼────────────────────────┐      ┌───────▼─────────────────────────────┐
 │ infrastructure/execution/      │      │ infrastructure/ui/presenter.py       │  OS-agnostic flow:
 │ HTTP bridge · file bridge ·    │      │ PT JS + locators (INTERFACES §3)     │  PT's API first, GUI second
 │ token · deploy executor        │      └───────┬─────────────────────────────┘
 └──────┬────────────────────────┘              │ WindowBackend (INTERFACES §2)
        │ state_dir, clipboard,          ┌──────▼───────┬───────────────┬────────────┐
        │ output_root                    │ backends/    │ backends/     │ backends/  │  (backends/linux/
 ┌──────▼────────────────────────┐       │ windows/     │ macos/        │ null.py    │   PHASE-08, gated)
 │ infrastructure/platform/       │       │ Win32 + UIA  │ AX + CG + SCK │ reason only│
 │ paths · clipboard · output ·   │       └──────┬───────┴──────┬────────┴────────────┘
 │ host  (INTERFACES §1)          │              │              │
 └──────┬────────────────────────┘               │              │
        │ files in the state dir                 │ Win32/UIA    │ AX / CGEvent / SCK (TCC-gated)
 ┌──────▼────────────────────────────────────────▼──────────────▼───────────┐
 │ Packet Tracer: webview (HTTP poll :54321) · script engine (mailbox) · Qt  │
 └───────────────────────────────────────────────────────────────────────────┘
```

## Data flow, stage by stage

| # | Stage | Input | Output | Persisted as |
|---|---|---|---|---|
| 1 | Platform detection | `sys.platform`, env, home | `Platform` (INTERFACES §1) | Process cache only |
| 2 | Pairing | state dir | token; mailbox dir chosen by heartbeat | `<state>/bridge_token`, `<mailbox>/alive.txt` |
| 3 | Command transport | JS built with `json.dumps` | PT result text | `req_*.js` / `res_*.txt` (mailbox) or HTTP queue |
| 4 | UI presentation | device, tab, app, section | dialog shown; optional PNG | `<output_root>/screenshots/*.png` |
| 5 | Diagnostics | none | checklist / `platform` block | stdout (`pt-mcp doctor`), tool reply |

Execution stays synchronous and per request, as today: a tool call runs its
stages in-process and replies. There is no background worker. The one
asynchronous API (ScreenCaptureKit's completion handler) is wrapped into a
blocking call with a timeout inside the macOS backend, so nothing above the
backend changes.

## Components and responsibilities

```
src/packet_tracer_mcp/
  infrastructure/platform/
    __init__.py        current() / reset_current(): the cached Platform of this process
    base.py            OsName, detect_os, HostInfo, Clipboard protocol, Platform
    paths.py           state_dir(), mailbox_candidates(): pure functions of (os, env, home)
    clipboard.py       ClipExe, Pbcopy, WlCopy, Xclip, Xsel, NoClipboard; clipboard_for()
    output.py          output_root(), output_dir(): where relative output folders land
    host.py            host_info(), pt_processes(), responsible_app() (macOS launch chain)
  infrastructure/ui/
    backend.py         WindowBackend protocol, UiElement, Role, Capture, errors
    locators.py        named widget locators: identifier predicate + fallback predicate
    presenter.py       OS-agnostic open/close/capture on a WindowBackend
    names.py, png.py   unchanged, shared by every backend
    backends/__init__.py   load_backend(): OS → backend, PT_MCP_UI_BACKEND override
    backends/null.py       NullBackend: every call raises BackendUnavailable(reason)
    backends/windows/      win32.py + uia.py (moved, bodies unchanged) + backend.py
    backends/macos/        ax.py, windows.py, capture.py, events.py, permissions.py, backend.py
    backends/linux/        PHASE-08 only
  infrastructure/execution/
    bridge_token.py    token_dir() delegates to platform.paths.state_dir()
    file_bridge.py     mailbox dir = freshest heartbeat among mailbox_candidates()
    deploy_executor.py clipboard through Platform.clipboard
  devtools/
    live_smoke.py      run tool calls against a live PT from this checkout
    macos_probe.py     dump permissions, CG windows and AX trees to JSON fixtures
  server.py            `pt-mcp doctor` subcommand next to the existing --stdio switch
tests/fixtures/macos/  AX trees and window lists recorded from the real PT (PHASE-00)
tests/live/            JSON call lists for devtools/live_smoke.py (opt-in, never in CI)
EXTENSION/script-engine/main.js   home derivation; mailbox dir follows the token found
```

## Key technology choices

| Choice | Rationale |
|---|---|
| In-package backends chosen at runtime | The user's requirement: "just connect mcp and it works out of box on any os" (2026-10-10). `RESEARCH/SYNTHESIS.md` §3 |
| pyobjc (Quartz, ApplicationServices, Cocoa, ScreenCaptureKit) | SCK completion handlers are Objective-C blocks. `RESEARCH/topics/macos-ui-automation.md` §3, S9, S10 |
| AX tree for navigation | The macOS twin of UIA, with AXPress on any Qt (S4, S5). `macos-ui-automation.md` §6 |
| AX↔CG bounds join for window handles | Titles from CG are empty without Screen Recording. `macos-ui-automation.md` §2 |
| SCK, then CGWindowListCreateImage, then `screencapture -l` | CGWindowListCreateImage is deprecated in macOS 14 (S8). `macos-ui-automation.md` §3 |
| Locators as data | Identifiers may be empty on old Qt. `RESEARCH/topics/pt-on-macos.md` §4 |
| Heartbeat-driven mailbox discovery | Makes the released V5.2 `.pts` work on macOS and Linux with no rebuild. `pt-on-macos.md` §3 |
| Environment markers in core `dependencies` | No extra for the user to remember. The `[ui]` extra stays as an empty alias for old instructions |
| Node to test `main.js` | Preinstalled on GitHub runners. Skipped locally when `node` is absent |

## Communication between components

- `adapters/` never imports `ui/backends/` or `platform/` internals. It goes
  through `PanelSupport`, `Presenter` and `platform.current()`.
- `presenter.py` never checks the OS and never touches `UiElement.ident`
  directly. It calls `locators.locate()` (`CONSTRAINTS.md` C1).
- Backends never send JS to PT. The presenter owns every PT API call, and the
  backend owns every OS call.
- Headless code paths never import `ui/backends/*` (`CONSTRAINTS.md` C2, C3).
- Only `infrastructure/platform/` and `infrastructure/ui/backends/` may read
  `sys.platform` or `os.name`. A test enforces it (PHASE-01).

## Deployment

The user installs from git or PyPI with pip or `uvx`. pip resolves the platform
dependencies through environment markers. The `.pts` is installed once in PT
(Extensions → Scripting → Configure PT Script Modules → Add…). On macOS, the
first use of UI mode triggers the two TCC prompts, and `pt-mcp doctor` names the
app to grant. Nothing else is configured by hand.

## What this architecture deliberately does not do

- **No Linux UI mode before PHASE-08.** No Linux machine with PT exists for
  verification. The null backend gives a precise reason in the meantime.
- **No automatic `.pts` install.** PT's module registry format is unknown and
  guessing it violates AGENTS rule 6. It is queued as a brief in `FUTURE_WORK.md`.
- **No keyboard emulation.** Typing goes through PT's API, as on Windows.
- **No change to the bridge protocol, token scheme or port.** Pairing compatibility
  with released extensions comes first.
- **No helper `.app`.** A signed helper bundle would own its own TCC grants, but
  it adds signing and notarisation work this project cannot maintain.
- **No PT version matrix.** PT 9.0.x is the only version verified, on each OS.
