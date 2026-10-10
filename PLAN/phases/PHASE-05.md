# PHASE-05 — macOS backend: navigation and open-by-click

## Objective

On the Mac, the full UI mode works like Windows. The presenter opens a device's
dialog (shown through PT's API, or by a canvas click when it does not exist
yet), then selects the tab, opens the section or Desktop app, fills fields,
presses buttons, scrolls consoles and closes nested applets. Every flow in
`tests/live/ui.json` passes.

## Why it exists

This is the user's "full parity now" decision (2026-10-10). The panel tools
(`pt_cli`, `pt_host_command`, `pt_server_*`, `pt_web_browser` and the rest) pass
`show=True` and expect the right tab or app on screen. Without navigation,
capture only ever shows whatever dialog the user opened by hand. This phase is
also where the main risk of the plan sits: widget lookup when Qt does not
expose identifiers (`RESEARCH/topics/pt-on-macos.md` §4).

## Dependencies

- PHASE-04: `MacBackend` with windows, capture and permissions.
- PHASE-03: the locator table with empty `by_shape` slots.
- PHASE-00: AX fixtures, the roles and actions found, and the click-route result.

## Files to create

```
src/packet_tracer_mcp/infrastructure/ui/backends/macos/ax.py       AX walk, attribute reads, actions, to_element()
src/packet_tracer_mcp/infrastructure/ui/backends/macos/events.py   posted click; cursor-restoring fallback
tests/test_macos_ax_convert.py      fixtures → UiElements
tests/test_macos_locators.py        every locator finds its element in the recorded fixtures
tests/test_macos_click_route.py     route choice and fallback logic (events stubbed)
```

## Files to modify

- `backends/macos/backend.py`: `elements`, `select`, `press`, `toggle_state`,
  `range_value`, `set_value`, `scroll_to_end`, `click`.
- `infrastructure/ui/locators.py`: the `by_shape` fallbacks, **only if PHASE-00
  found `AXIdentifier` empty or different**.
- `infrastructure/ui/names.py`: only if macOS shows different visible tab or app
  labels. Add aliases; never remove the Windows ones.

## Implementation details

### AX walk and conversion

- `ax.walk(window_el, max_depth=40, max_nodes=5000)` reads, per node, `AXRole`,
  `AXSubrole`, `AXTitle`, `AXDescription`, `AXIdentifier`, `AXValue` (truncated),
  `AXPosition`, `AXSize` and `AXChildren`. **The probe from PHASE-00 and the
  backend share this code**, so fixtures and live data take the same path.
- `ax.to_element(node_dict, window_frame)` → `UiElement`:
  - name: `AXTitle`, else `AXDescription`, else the `AXValue` of static text
  - ident: `AXIdentifier`
  - role: per the `INTERFACES.md` §2 mapping, corrected from the fixtures
  - offscreen: zero size or outside the window frame
  - rect: points (C10)
- Read attributes in batches with `AXUIElementCopyMultipleAttributeValues`
  where PHASE-00 verified it. Each attribute read is an IPC round trip, and the
  target is ≤ 800 ms per dialog (`CONSTRAINTS.md` performance table).

### Actions

| Protocol | AX |
|---|---|
| `select(tab)`, `press(el)` | `AXUIElementPerformAction(raw, "AXPress")` |
| `toggle_state` | `AXValue` as int (0/1/2) |
| `range_value` | `AXValue` as float |
| `scroll_to_end` | set `AXValue` to `AXMaxValue` |
| `set_value(edit, text)` | set `AXValue`; if PHASE-00 showed Qt ignores it, set `AXFocused` first |

An AX error code becomes a `BackendError` with the attribute and the code in
the message.

### Locators without identifiers

**Amendment 2026-10-10:** PHASE-00 answered "identifiers present", but four keys
still need a `by_shape` because their element does not exist on macOS:
`logical_canvas`, `canvas_hbar`, `canvas_vbar`, `console_scrollbar` (INTERFACES §3
amendment). Write those four as below; the rest keep `by_ident`.

Only if PHASE-00 answered "no identifiers". Write each `by_shape` from the
fixtures, using role, visible text, an ancestor's role or text, and relative
size. For example, the logical canvas could be the largest AXScrollArea of the
main window, and its scroll bars that area's AXScrollBar children by
orientation. **Every `by_shape` gets a fixture test before it is used live.** A
locator that cannot be expressed reliably is a finding. Record it in ISSUES with
the fixture name. Do not ship a guess.

### Open-by-click

**Amendment 2026-10-10 (PHASE-00, PREVIOUS_WORK 2.4 #7).** `CGEventPostToPid` mouse
clicks never opened a device dialog (5 variants, PT in the background and frontmost).
The only working route is: activate PT, `AXRaise` its main window, check PT is
frontmost (refuse to click otherwise), `CGEventPost(kCGHIDEventTap)` down/up,
`CGWarpMouseCursorPosition` back (~0.5 s). So the macOS click is always
`"cursor-restored"`, and the step text must say the cursor moved briefly. Prefer
`getDialogManager().getDialog(d).setVisible(true)` whenever the dialog already exists
(a hidden dialog re-showed on click too). Scene coordinates are points from the canvas
origin at zoom 0 (R1 scene 299,150 → screen 299,330); `centerOnComponentByName` does
not scroll when the scene fits, so click the device point, not the viewport centre.
The corner measurement below still applies. The Control Center window may cover the
canvas: check `AXUIElementCopyElementAtPosition` returns the canvas before clicking.

Use `events.click(handle, x, y)` in the PHASE-00 route order. It returns
`"posted"` (no cursor movement) or `"cursor-restored"`, and the presenter's step
text reports which. The Select-tool guard in `_open_by_click` stays exactly as
is. `device_point()` arithmetic is in points: the canvas `rect` comes from AX in
points, and PT's scene coordinates at 100 % zoom are assumed to be points
(`RESEARCH/topics/macos-ui-automation.md` §5). **Measure that assumption on a
device near each corner of the canvas before trusting it.**

### The open question this phase must answer

Does the presenter's zoom-100 % calibration (`presenter.py` `device_point`)
hold in points on Retina? If it does not, record the measured offset and scale
in PREVIOUS_WORK Part 2. Then fix the calibration in the presenter as data,
keyed by backend unit. Do not add an OS branch.

## Inputs / outputs

- In: PHASE-00 fixtures and click-route answer; PHASE-04 backend.
- Out: macOS UI-mode parity; any locator gaps recorded in ISSUES.

## Relevant interfaces

`INTERFACES.md` §2 (protocol, units, role mapping), §3 (locators), §7 (fixtures).

## Relevant research

`RESEARCH/topics/macos-ui-automation.md` §4 (click routes), §5 (units),
§6 (call mapping); `RESEARCH/topics/pt-on-macos.md` §4 (identifiers).

## Tests

- Conversion: every fixture → elements. The roles found match the probe's
  counts, and there are no exceptions.
- **Locators on fixtures: each key finds exactly one element where the presenter
  needs it.** For example, `desktop_app("CommandPrompt")` in PC1's Desktop
  fixture, `applet_close` in the Email fixture, and `canvas_hbar` in the
  main-window fixture. This is the one the phase rests on.
- The presenter flow on a FakeBackend fed with fixture elements: open by tab, open
  an app, Email's nested close loop.
- Click route: when the posted click opens nothing within the wait, the fallback
  runs once and restores the cursor (events stubbed).

## Acceptance criteria

- [x] `ax.py` (shared walk, `to_element`) written; the probe uses the same walk; `test_macos_ax_convert.py` converts all 8 fixtures (watched failing first) — before: `ModuleNotFoundError ...macos.ax`; after: 19 passed (roles vs AX counts, tabs only inside the tab group, names from AXDescription, rects in points, offscreen rules). Probe `dump_tree` = `ax.walk`; live: `macos_probe ax` on PC1 → 49 nodes in 23 ms, passes the fixture-format check, converts to 48 elements with the 5 tabs; `windows.py` reuses `ax.attr`/`ax.frame`; 2026-10-10
- [x] Locator fallback for elements whose ident differs on macOS; `test_macos_locators.py` finds every key the presenter needs in the fixtures, and the Windows results are unchanged — `locate_all` gives `by_shape` a second pass over elements *with* an ident only when the first pass found nothing; `logical_canvas` falls back to `...m_pViewArea_Window.m_workspaceWS` (canvas test failed before, passes after). Fixtures: 13 passed (Select tool, canvas rect 0,180→1512,706, 4 desktop apps, Command Prompt and Email applets incl. the innermost pressable closer, browser fields, Config/Services sections, presenter tab/app/Email loop on recorded trees); canvas scroll bars and console scroll bar have no element (pinned, ISSUES). Windows side: `test_locators` (+4 second-pass cases: Windows' QWidget wins even after the mac name), presenter and device-panel tests 124 passed; 2026-10-10
- [x] `MacBackend` navigation (`elements`, `select`, `press` incl. checkable sections, values, `click`) and `events.py` written; `test_macos_click_route.py` passes with events stubbed — 21 passed: the HID click refuses unless PT is frontmost (waits ≤ 1.5 s) and the point hits PT's canvas (`...m_workspaceWS` in the hit element's parent chain), and warps the cursor back even when posting fails; dialog sections switch by focus + Space and are verified checked afterwards, the main window's Select tool by `AXPress`; AX error codes surface in `BackendError`. Presenter step text for the route pinned ("the cursor moved there for a moment and was put back"). Probe `hit` command added and run live (err 0; with Claude on top the chain has no canvas ident, so the guard would refuse). Full suite 1177 passed; 2026-10-10
- [ ] All tests pass on the Mac and CI; the suite stays ≥ the macOS baseline — Mac: `.venv/bin/python -m pytest -q` 1181 passed (baseline 825), CODEMAP regenerated, pyflakes clean on the touched files (only the deliberate import probes). **BLOCKED: CI needs a push (the user asked for no commits)**; 2026-10-10
- [x] Live, Mac: every flow in `tests/live/ui.json` reports `ok`, and its PNG is non-blank with the right tab or app visible (`EVALUATION.md` §5) — third full run 8/8 (HTTP channel): R1 CLI, PC1 Command Prompt (opened by canvas click), IP Configuration, SRV1 Services › DHCP, Web Browser (URL typed through `AXValue`, page shown), all PNGs 1400×1416 not blank and checked by eye (`screenshots/*-20261010-1928*.png`, `ui-pc1-ipconfig.png`). Earlier runs found and fixed: the hit test ran before PT's windows were raised (now polled ≤ 1 s); a section's check lags Space by ~0.15 s (now polled ≤ 1 s); an off-view device was clicked at a stale point (presenter now clicks the centre after centring when no scroll bar says otherwise). One R1 open by click missed right after the canvas changed (4/4 on retry; ISSUES X12); 2026-10-10
- [x] Live, Mac: the timings in `CONSTRAINTS.md` hold (open ≤ 1.5 s when the dialog exists, ≤ 4 s by click; AX walk ≤ 800 ms), measured and recorded — HTTP channel: open with the dialog open 0.34–0.49 s (5 runs), by canvas click 0.84–1.21 s (5 runs), capture 0.31–0.39 s; AX walks R1 14 nodes 18 ms, PC1 55 nodes 24 ms, SRV1 65 nodes 27 ms, main window 111 nodes 32 ms. **File channel** (Control Center closed): by click 1.11–2.73 s, but open with the dialog open 0.68–1.84 s — over 1.5 s twice, because one JS round trip took 0.21–1.42 s (profiled: the backend's own share is < 0.2 s plus the presenter's 0.25 s tab pause; ISSUES X14); PREVIOUS_WORK 2.9; 2026-10-10
- [x] Live, Mac: the Delete-tool guard refuses to click (switch to Delete by hand, run `pt_ui_open`, and the device survives) — Delete made active through AX at the user's request instead of by hand (PT then read Select 0, Delete 1); `pt_ui_open R1` (dialog closed, so by click) → "Select tool activated" first; at the moment of the click Select 1, Delete 0; R1's dialog opened and all 5 devices survived. The refuse branch (Select cannot be turned back on) is covered offline only (`test_refuses_to_click_when_select_cannot_be_turned_on`); 2026-10-10
- [x] The click route used is recorded (`posted` or `cursor-restored`), with the evidence — `cursor-restored`, always: posted clicks never reached the canvas (PHASE-00, 5 variants); every live open by click in this phase returned it (step text "click sent; the cursor moved there for a moment and was put back"), incl. the four canvas corners; the guard refused a click live when Claude's window was on top. PREVIOUS_WORK 2.9; 2026-10-10
- [x] Every `by_shape` added has a fixture test — one added, `logical_canvas` → `...m_pViewArea_Window.m_workspaceWS`: `test_macos_locators.py::TestMainWindow::test_logical_canvas_is_the_workspace_group` (exactly one hit, rect 0,180→1512,706 pt in `main-window.json`); `select_tool`'s name fallback (PHASE-03) found once in the same fixture. Canvas scroll bars and the console scroll bar got **no** `by_shape`: no element exists in any fixture (pinned by `test_no_canvas_scroll_bars_in_the_recording`, `test_console_has_no_scroll_bar_element`; ISSUES X12); 2026-10-10

## Known failure conditions

- Tabs are found but pressing does nothing → AXPress maps to a Qt action the tab
  bar does not implement. Try setting `AXSelected` on the tab or `AXValue` on the
  tab group, whichever the fixture's settable attributes show.
- The walk takes seconds → too many attribute reads per node. Batch them, and
  cap the depth for the canvas, whose devices are not AX children anyway.
- A click opens the wrong device → points versus pixels (C10), or a scroll bar
  value read in different units. Log `rect`, the scroll values and the computed
  point, then compare with a screenshot.
- `set_value` on the browser URL is ignored → Qt needs focus first. Use
  `AXFocused` then `AXValue`. As a last resort, PT's API path, which
  `pt_web_browser` already has (`navigated_by_gui` false).
