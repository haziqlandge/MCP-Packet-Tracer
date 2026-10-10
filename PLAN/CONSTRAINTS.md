# CONSTRAINTS

Project-specific constraints for the cross-platform work. The non-negotiable
rules in `AGENTS.md` (JS via `json.dumps`, `safe_name_component` +
`resolve_within`, token-gated bridge, validation outside models, failing test
first, no guessed PT API) apply unchanged and are not repeated here.

## Integrity constraints

**Each is a correctness requirement, not a style preference.**

| # | Constraint | Why | Violation looks like |
|---|---|---|---|
| C1 | Only `infrastructure/platform/` and `infrastructure/ui/backends/` read `sys.platform` / `os.name`. Everything else asks `platform.current()` | One home per OS fact. Scattered checks are how the code became Windows-only | `if sys.platform == "darwin":` in a tool module. Enforced by a grep test (PHASE-01) |
| C2 | Every module imports cleanly on every OS. OS-only packages (`comtypes`, `Quartz`, `ApplicationServices`, `AppKit`, `ScreenCaptureKit`) are imported inside backend functions or modules that `load_backend` alone imports | Windows and Ubuntu CI, and every headless user, must never need them | `ModuleNotFoundError: No module named 'Quartz'` on Windows CI. Enforced by an import-every-module test with each OS faked (PHASE-03) |
| C3 | Headless paths never trigger a permission prompt and never need a GUI permission. Only `pt_ui_mode("ui")`, `show=True`/`capture=True` and `pt-mcp doctor --request-permissions` call `available(request=True)` | A prompt nobody asked for, from `pt_bridge_status`, teaches users to deny | A TCC dialog appears when the server starts or on a headless tool. Enforced by a test that the request APIs are reachable only from those entry points (PHASE-04) |
| C4 | The Windows backend is a **move, not a rewrite**: `win32.py` and `uia.py` move with `git mv`, with function bodies byte-identical. `WindowsBackend` only adapts calls. Presenter behaviour on Windows is unchanged | The work runs on a Mac. Windows UI mode cannot be verified live until a Windows session | `git diff -M main -- '*win32.py' '*uia.py'` shows more than import lines. Windows live smoke regresses |
| C5 | Both sides of the pairing compute the same paths (`INTERFACES.md` §5), and the released V5.2 `.pts` keeps working on every OS | Users install the `.pts` from Releases. A Python-only fix must not depend on a rebuild | `pt_bridge_status` shows the mailbox "alive: false" while PT is open on a Mac |
| C6 | No guessed API, on either side. A PT method must already be used in the repo or be confirmed against Cisco's reference (AGENTS rule 6). A macOS selector or constant must be exercised by `devtools/macos_probe.py` on the Mac before code depends on it, and its exact name recorded in PREVIOUS_WORK Part 2 | PT and pyobjc both fail without saying why (`Invalid arguments for IPC call`, `AttributeError`) | `AttributeError: module 'Quartz' has no attribute ...` on the Mac. A selector misspelled by one underscore |
| C7 | A degraded result is a result. When UI mode cannot work (missing permission, unsupported OS, no window), the headless part completes and the reply carries the **remedy**: which permission, which app, where in System Settings | "Works out of the box" includes telling the user exactly what to click | A traceback, or "GUI not available" with no next step |
| C8 | Never claim live verification from offline tests. Never claim Windows UI mode is unchanged until it has run on Windows | AGENTS "Working with the bridge". The executor machine is a Mac | A ticked acceptance box with only pytest evidence for a live criterion |
| C9 | The tool API is stable: tool names and parameters are unchanged. `tool_api.json` is regenerated only for deliberate description edits (PHASE-07). `SERVER_INSTRUCTIONS` ≤ 2,000 chars, descriptions ≤ 1,500 | Clients and the skill depend on the API. The limits are tested | `test_tool_api` fails outside PHASE-07, or a description grows past its cap |
| C10 | Units never mix. macOS `rect` and `click` are points, `Capture` is pixels. Windows is pixels throughout | Retina is ×2 | Clicks land at half or double the position. Captures are cropped or doubled |
| C11 | Outputs never land relative to an unwritable cwd. Every tool output folder goes through `platform.output_dir()` | GUI clients may start the MCP with cwd `/` (SYNTHESIS §6) | `[Errno 30] Read-only file system: 'projects'` |

## Data constraints

| Constraint | Detail |
|---|---|
| Fixtures carry no secrets | AX dumps contain device names and UI text only. Never a token, and never the home path unredacted (replace it with `~`) |
| Fixtures are recorded, not hand-written | `tests/fixtures/macos/*.json` come from `devtools/macos_probe.py` on the real PT. A hand edit is a test of nothing |

## Technical constraints

| Constraint | Detail |
|---|---|
| Python | ≥ 3.11 (`pyproject.toml`). The macOS system `python3` (3.9) is not supported. Docs point to uv or python.org |
| PT | 9.0.x for macOS. Amended 2026-10-10: PT 9.0.1 for macOS is a **universal binary** (x86_64 + arm64), so Rosetta is not required (PREVIOUS_WORK 2.4 #1). It bundles Qt 6.8.7 |
| macOS | UI capture: SCK on 14+. 12.3–13 fall back to CGWindowListCreateImage, best effort |
| JS pasted into PT | Single line, no `//` comments (AGENTS Gotchas). Compiled `.pts` files are exempt |

## Performance targets

| Operation | Target | Basis |
|---|---|---|
| `pt_ui_open` with the dialog already open | ≤ 1.5 s | Windows presenter today: sub-second |
| `pt_ui_open` by canvas click | ≤ 4 s | Windows waits up to 3 s for the window (`presenter.py` `_wait_window`) |
| `pt_ui_capture` | ≤ 2 s | SCK screenshot plus PNG encode of a ~1 MP window |
| AX tree walk of one dialog | ≤ 800 ms, ≤ 5,000 nodes | UIA FindAll is about 100–300 ms. AX IPC per attribute is slower |

## Scope boundaries — explicitly out

| Excluded | Reason |
|---|---|
| Linux UI mode | Gated in PHASE-08: no Linux PT machine |
| Automatic `.pts` installation | Registry format unknown (AGENTS rule 6). `FUTURE_WORK.md` brief |
| PT versions other than 9.0.x | No machine to verify them |
| Upstream PR | Only with the user's OK, after removing the plan docs |

## Machine and resource limits

**2026-10-10.** Executor: the user's Mac with PT. Model, macOS version and CPU
are recorded in PHASE-00. One PT and one bridge at a time, so live smoke runs
serially (never two agents against one PT). The Windows machine (Windows 10 Pro,
PT 9.0.1, Python 3.14.8) wrote this plan and is used later only for the Windows
UI regression check (`FUTURE_WORK.md` §2).
