# PHASE-03 — UI backend seam

## Objective

The presenter speaks only `WindowBackend` (`INTERFACES.md` §2) and finds widgets
only through locators (§3). The Windows code is moved behind `WindowsBackend`
without changing what it does. A `NullBackend` answers every other OS with a
precise reason. Behaviour on Windows is byte-for-byte the same flow.

## Why it exists

Requirement (c) in `RESEARCH/SYNTHESIS.md` §1, and the thesis of §4: a macOS
backend can only reach parity without a second presenter if the presenter
stops calling `win32` and `uia` directly. Today `presenter.py` imports `win32` in
five places and `Uia` in four, and tests UIA control-type ids (`u.m.UIA_CheckBoxControlTypeId`).
Every one of those has to become a protocol call or a locator, or PHASE-05
forks the presenter. The locator table is also where PHASE-05 adds its
`by_shape` fallbacks. Skip it and those fallbacks end up as `if macos:`
branches, which breaks C1.

## Dependencies

- PHASE-00: the fixture format, which shapes `UiElement`, and the AX roles,
  which confirm the `Role` enum covers what macOS shows.
- Can be built in parallel with PHASE-01 and PHASE-02.

## Files to create

```
src/packet_tracer_mcp/infrastructure/ui/backend.py            Role, UiElement, Capture, WindowHandle, errors, WindowBackend
src/packet_tracer_mcp/infrastructure/ui/locators.py           Locator, locate(), locate_all(), the §3 table
src/packet_tracer_mcp/infrastructure/ui/backends/__init__.py   load_backend()
src/packet_tracer_mcp/infrastructure/ui/backends/null.py       NullBackend
src/packet_tracer_mcp/infrastructure/ui/backends/windows/__init__.py
src/packet_tracer_mcp/infrastructure/ui/backends/windows/backend.py   WindowsBackend: adapts win32 + Uia
tests/fakes/fake_backend.py           FakeBackend: scripted windows, elements, actions log
tests/test_presenter_on_backend.py    presenter flow on FakeBackend
tests/test_locators.py                every locator on synthetic elements
tests/test_backend_selection.py       load_backend per OS and override
tests/test_imports_every_os.py        C2: import every module with each OS faked
```

## Files to modify

- `git mv infrastructure/ui/win32.py infrastructure/ui/backends/windows/win32.py`
- `git mv infrastructure/ui/uia.py infrastructure/ui/backends/windows/uia.py`.
  **Only import lines may change in these two files (C4).**
- `infrastructure/ui/presenter.py`: take a `WindowBackend` (constructor argument,
  default `platform.current().ui_backend()`). Replace each `win32.*` and `Uia`
  call. `is_available()` becomes `backend.available()`.
- `adapters/mcp/device_panel_tools.py` and `panel_support.py`: build the
  presenter with the platform backend. `pt_ui_mode("ui")` calls
  `available(request=True)` (C3).
- `infrastructure/platform/base.py`: `Platform.ui_backend()` calls `load_backend()`.
- `devtools/codemap.py`: update the `infrastructure/ui/` description, then
  regenerate `CODEMAP.md`.
- `tests/test_os_checks_confined.py`: empty the PHASE-01 allow-list.
- Existing UI tests (`test_device_panel.py` and the PNG and name-map tests):
  update import paths only.

## Implementation details

### Mapping each presenter call (from `presenter.py` at `bcb2ef3`)

| Today | After |
|---|---|
| `win32.find_window(pid, title)` | `b.find_window(pid, title)` |
| `win32.main_window(pid)` | `b.main_window(pid)` |
| `win32.raise_window(h)` | `b.raise_window(h)` |
| `win32.capture(h)` → `(w, h, bgra)` | `b.capture(h)` → `Capture` |
| `win32.post_click(main, x, y)` | `b.click(main, x, y)`; the step text uses the return value |
| `u.descendants(h, "TabItem")` | `b.elements(h, Role.TAB)` |
| `u.descendants(h)` | `b.elements(h)` |
| `u.select / invoke / toggle_state / range_value / set_value / scroll_to_end` | the same-named protocol methods (`invoke` → `press`) |
| `e.automation_id.endswith(...)` and similar | `locate(els, locators.X)` |
| `e.control_type in {CheckBox, Button, ListItem}` | `e.role in {Role.CHECKBOX, Role.BUTTON, Role.LIST_ITEM}` |
| `e.rect()` | `e.rect` |

`WindowsBackend.elements()` wraps each `uia.Element` into a `UiElement`: name →
name, `automation_id` → ident, control type → Role (`INTERFACES.md` §2 mapping),
`rect()` → rect, and the `uia.Element` kept as `raw`. Every action method
unwraps `raw`. `available()` keeps today's two checks (Windows, comtypes). On
Windows, `request` has no effect.

### Locators

Move each predicate from the presenter into `locators.py` verbatim, as
`by_ident`. Leave `by_shape=None` for now: PHASE-05 fills it in. `locate()` uses
`by_ident` when the element has an ident, and `by_shape` when it does not and a
`by_shape` exists. Otherwise there is no match.

### NullBackend and selection

`NullBackend(reason)`: `available()` → `(False, reason)`, and every other method
raises `BackendUnavailable(reason)`. The reasons are actionable:

- On Linux: "UI mode is not available on Linux yet; every tool works headless.
  See PHASE-08."
- On a backend import failure: the import error plus the `pip install` that fixes
  it.

`load_backend` follows `INTERFACES.md` §2. **Until PHASE-04, macOS gets a
NullBackend** saying the macOS backend is coming.

### The open question this phase must answer

None technical. The risk is a silent behaviour change on Windows that only a
live Windows run would catch (C4, C8). Keep the diff mechanical. Record
`git diff -M --stat main` for the two moved files in PREVIOUS_WORK.

## Inputs / outputs

- In: PHASE-00 fixtures (they shape `UiElement`).
- Out: the seam, with Windows behind it and other OSes answered by the null
  backend.

## Relevant interfaces

`INTERFACES.md` §2 (backend protocol, units, role mapping, errors), §3 (locators).

## Relevant research

`RESEARCH/topics/macos-ui-automation.md` §6 (the call list the protocol must cover).

## Tests

- Presenter flow on `FakeBackend`: a dialog already open; opened by click with
  the Select tool already on and with it toggled on; the Delete-tool refusal
  (**must still refuse to click**); a tab missing; Email's nested close loop;
  `fill_and_go`; `scroll_consoles`; capture writing a PNG with the blank flag.
  **These pin the Windows behaviour the refactor must keep.**
- Locators on synthetic elements: every key in `INTERFACES.md` §3; an element
  with an empty ident and no `by_shape` gives no match.
- `load_backend`: each OS; `PT_MCP_UI_BACKEND=null`; an unknown value; a
  simulated import failure → NullBackend carrying the reason.
- C2: with `sys.platform` patched to `win32`, `darwin` and `linux` in turn,
  import every module under `src/packet_tracer_mcp` (fresh `sys.modules` per
  run, with the OS-only packages made unimportable). No exception.

## Acceptance criteria

- [x] `backend.py`, `locators.py` and `backends/` (null, windows) written; `test_locators.py` and `test_backend_selection.py` pass (watched failing first) — before: collection errors (`No module named ...ui.backend`); after: locators 23 passed, selection 27 passed, plus `test_windows_backend.py` 13 passed (role map, UIA filter names, raw unwrapped, one `Uia()` per call, Windows wording); 2026-10-10
- [x] Presenter speaks only `WindowBackend`; `test_presenter_on_backend.py` pins the Windows flows on `FakeBackend` (dialog open, Select on / toggled, Delete refusal, missing tab, Email close loop, `fill_and_go`, `scroll_consoles`, capture) — 35 passed (also: hidden dialog re-shown, scroll-bar offset, centring, zoomed canvas, second click, `BackendUnavailable` → `PresenterError` verbatim); the Delete refusal and missing-Select cases assert no click at all; existing `test_device_panel.py` `TestOpenApp` ported to the backend API with its assertions unchanged; 2026-10-10
- [x] `test_imports_every_os.py` (C2) passes with `sys.platform` faked to win32, darwin and linux — 3 passed (fresh interpreter each, comtypes/pyobjc blocked, every module of the package walked); mutation check: an `import objc` added to `backends/null.py` failed all three with "objc is blocked", reverted; 2026-10-10
- [x] All tests pass on the Mac; the suite stays ≥ the macOS baseline (`CLAUDE.md` §5) — `.venv/bin/python -m pytest -q`: 1028 passed (927 before this phase; baseline 825); pyflakes on the new and touched tests clean; 2026-10-10
- [x] `git diff -M main -- '**/win32.py' '**/uia.py'` shows only import-line changes (output recorded in PREVIOUS_WORK) — run against `bcb2ef3` (no local `main`): both renames at **similarity index 100%**, 0 insertions, 0 deletions; not even an import line changed (neither file has a relative import); PREVIOUS_WORK 2.7; 2026-10-10
- [x] `presenter.py` contains no `win32`, `uia`, `UIA_` or `automation_id` (grep recorded) — `grep -n "win32\|uia\|UIA_\|automation_id" .../ui/presenter.py` → no output, exit 1; 2026-10-10
- [x] `tests/test_os_checks_confined.py` passes with an empty allow-list — `ALLOW_LIST: set[str] = set()`; 2 passed (in the 1028); 2026-10-10
- [x] Live on the Mac: `pt_ui_mode("status")` reports the null backend's reason; `pt_cli(show=True)` completes headless with that note (C7) — `live_smoke` from this checkout, file channel, released-fix `.pts`: status "PT GUI: NOT available (UI mode is not available on macOS yet: its backend is still being built; every tool works headless.)"; `pt_cli` R1 `show ip interface brief` show=True → "1 ok", the interface table, then "GUI: could not show it (<same reason>). The work was still done through the API." (3 runs; the first returned `[ok]` with empty output once, not reproduced: ISSUES X11); 2026-10-10
- [x] CI windows-latest green (or recorded as pending push); the live Windows check is queued in `FUTURE_WORK.md` §2 — **pending push** (the user asked for no commits; `tests.yml` matrix lists windows-latest on 3.11 and 3.13); `FUTURE_WORK.md` §2 updated with what changed on Windows and what to watch; ISSUES X5 stays open until it runs; 2026-10-10

## Known failure conditions

- A Windows test passes on the Mac but the presenter breaks on Windows → the
  FakeBackend scripted something UIA never returns. Record it in ISSUES X5 and
  compare against `uia.py`'s real wrapping.
- `ImportError` for comtypes on the Mac → `backends/windows/` was imported
  eagerly. Import it only inside `load_backend`.
- The step text changed ("click posted, cursor not moved") → the skill and docs
  quote it. Keep the Windows wording. Only macOS adds "cursor restored".
