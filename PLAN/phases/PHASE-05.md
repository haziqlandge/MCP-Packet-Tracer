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

Only if PHASE-00 answered "no identifiers". Write each `by_shape` from the
fixtures, using role, visible text, an ancestor's role or text, and relative
size. For example, the logical canvas could be the largest AXScrollArea of the
main window, and its scroll bars that area's AXScrollBar children by
orientation. **Every `by_shape` gets a fixture test before it is used live.** A
locator that cannot be expressed reliably is a finding. Record it in ISSUES with
the fixture name. Do not ship a guess.

### Open-by-click

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

- [ ] All tests pass on the Mac and CI; the suite stays ≥ the macOS baseline
- [ ] Live, Mac: every flow in `tests/live/ui.json` reports `ok`, and its PNG is non-blank with the right tab or app visible (`EVALUATION.md` §5)
- [ ] Live, Mac: the timings in `CONSTRAINTS.md` hold (open ≤ 1.5 s when the dialog exists, ≤ 4 s by click; AX walk ≤ 800 ms), measured and recorded
- [ ] Live, Mac: the Delete-tool guard refuses to click (switch to Delete by hand, run `pt_ui_open`, and the device survives)
- [ ] The click route used is recorded (`posted` or `cursor-restored`), with the evidence
- [ ] Every `by_shape` added has a fixture test

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
