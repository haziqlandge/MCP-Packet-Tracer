# PHASE-04 — macOS backend: windows, capture, permissions

## Objective

On the Mac, `MacBackend` finds PT's windows, raises them and captures them as
PNGs (even when covered). It reports permissions with the exact remedy and asks
for them only from UI-mode entry points. `pt_ui_capture` and `capture=True`
work on macOS. The pyobjc dependencies install automatically on macOS.

## Why it exists

Capture is the most visible half of UI mode ("I want screenshots" in
`pt_ui_mode`'s description), and it is the half that needs Screen Recording.
Building it before navigation (PHASE-05) puts the permission onboarding in place
early. It also proves the window handle (CGWindowID via the AX join), which
every other backend call takes. If the handle or the units are wrong, PHASE-05
clicks in the wrong place (C10).

## Dependencies

- PHASE-03: the protocol, the null fallback and the presenter seam.
- PHASE-01: `responsible_app()` for the remedy text.
- PHASE-00: the working capture route, the window-join evidence and the
  verified selector names (C6).

## Files to create

```
src/packet_tracer_mcp/infrastructure/ui/backends/macos/__init__.py
src/packet_tracer_mcp/infrastructure/ui/backends/macos/permissions.py  preflight/request; remedy text
src/packet_tracer_mcp/infrastructure/ui/backends/macos/windows.py      CG list, AX windows, bounds join
src/packet_tracer_mcp/infrastructure/ui/backends/macos/capture.py      SCK → CGWindowListCreateImage → screencapture; BGRA normalise
src/packet_tracer_mcp/infrastructure/ui/backends/macos/backend.py      MacBackend (windows + capture now; navigation in PHASE-05)
tests/test_macos_permissions.py
tests/test_macos_window_join.py
tests/test_macos_capture_normalise.py
tests/test_permission_prompts_confined.py   C3
```

## Files to modify

- `pyproject.toml`: add the platform dependencies to `dependencies` with
  markers (`; sys_platform == 'darwin'` for the pyobjc packages,
  `; sys_platform == 'win32'` for `comtypes`). Use the version floors PHASE-00
  installed. Keep `ui = []` as an empty alias with a comment. Add the
  classifier `Operating System :: MacOS`.
- `infrastructure/ui/backends/__init__.py`: macOS → `MacBackend`.
- `CHANGELOG.md` (Unreleased): UI dependencies now install automatically.

## Implementation details

### Permissions

- `state()` → `{"accessibility": bool, "screen_recording": bool, "post_events": bool}`
  from the preflight APIs only.
- `request(missing)` calls the matching request APIs, at most once per process
  for each permission. Showing the system dialog twice in one session is noise.
- `remedy(missing, app)` builds the message, for example: *"UI mode needs
  Accessibility and Screen Recording for **Claude**. Open System Settings →
  Privacy & Security → Accessibility (and → Screen Recording), turn on Claude,
  then quit and reopen Claude."*. Use "the app that runs this MCP server" when
  `responsible_app` returns None.
- `MacBackend.available(request)`: pyobjc importable? (if not: the `pip install`
  remedy), then `state()`. With `request` and something missing, call
  `request()` first, then check again.
- Navigation needs Accessibility. Capture also needs Screen Recording.
  `available()` reports both. `capture()` raises `BackendUnavailable` with the
  Screen Recording remedy when that is the only one missing.

### Windows and the handle

`windows.py` follows `RESEARCH/topics/macos-ui-automation.md` §2. The join and
the AX frame unpacking are pure functions over plain dicts and tuples, so tests
feed them PHASE-00 recordings.

- `find_window(pid, title)`: the AX window whose `AXTitle` equals the title (or
  starts with it, as the Windows `find_window` does; check `win32.py`), joined
  to its CGWindowID. Match within ±1 point on each bound, to allow for rounding.
- `main_window(pid)`: the AX `AXMainWindow`, joined the same way.
- `raise_window`: `AXRaise`, then activate the app.
- **`WindowHandle` is the CGWindowID (an int)**, so `presenter.open()` can still
  return it as `"hwnd"` in JSON.

### Capture

`capture.py` tries the routes in `macos-ui-automation.md` §3 order, starting
with the one PHASE-00 proved. Rules:

- SCK runs asynchronously: wait on a `threading.Event` with a 5 s timeout, then
  raise `BackendError("capture timed out")`.
- Normalise every CGImage to tightly packed top-down BGRA, using its bitmap
  info and bytes per row. **The pure normaliser is what the tests cover.**
- `screencapture -l` writes a PNG. Decode it to BGRA through
  `NSBitmapImageRep` so `png.looks_blank` and the shared encoder still apply.
- Retina: SCK's configuration size is frame × `backingScaleFactor` of the
  window's screen. `Capture` reports pixels (C10).

### The open question this phase must answer

Does a Screen Recording grant take effect in a running client, or only after a
restart (SYNTHESIS §9, question 9)? Measure it. Whatever the answer, the remedy
text must state it, and PREVIOUS_WORK Part 2 must record it.

## Inputs / outputs

- In: PHASE-00 recordings and verified names.
- Out: `MacBackend` with window, capture and permission support; automatic
  dependencies.

## Relevant interfaces

`INTERFACES.md` §2 (`available`, `capture`, units, errors), §6 (permission
fields the diagnostics will show).

## Relevant research

`RESEARCH/topics/macos-ui-automation.md` §1 (permissions), §2 (windows),
§3 (capture), §5 (units).

## Tests

- Permissions: every combination of states → the right remedy, with the app
  name present or absent. `request` is called at most once per permission.
- C3: monkeypatch the request functions to raise. Run `pt_bridge_status`,
  `pt_query_topology` and a headless `pt_cli` through the registry. No call
  reaches them. Then run `pt_ui_mode("ui")`: it does reach them.
- The window join on recorded CG lists and AX frames: an exact match, ±1 rounding,
  two windows with the same title (pick the frontmost layer-0), no match.
- The capture normaliser: padded rows; BGRA, ARGB and RGBA layouts; premultiplied
  alpha left as is. All checked byte-exact on synthetic 3×2 images.
- `pyproject.toml`: markers parse (`packaging.requirements.Requirement`), and the
  pyobjc packages carry the darwin marker and `comtypes` the win32 marker.

## Acceptance criteria

- [ ] All tests pass on the Mac and on CI's three OSes; the suite stays ≥ the macOS baseline
- [ ] Live, Mac: `pt_ui_capture` of PT's main window and of a covered PC1 dialog gives non-blank PNGs at pixel size (`EVALUATION.md` §5), ≤ 2 s
- [ ] Live, Mac, with permissions revoked: `pt_ui_capture` returns the remedy naming the real client app; a headless tool raises no prompt (C3)
- [ ] Live, Mac: the restart-or-not answer for Screen Recording is recorded in PREVIOUS_WORK Part 2
- [ ] `pip install -e .` on the Mac installs the pyobjc packages without `[ui]`; Windows CI installs `comtypes`; Ubuntu installs neither

## Known failure conditions

- A black or desktop-only PNG → Screen Recording is missing for the responsible
  app, or the app was not restarted after the grant. `looks_blank` flags it, and
  the reply must add the remedy.
- The PNG is sheared or diagonal → bytes-per-row padding was not stripped.
- Colours are swapped (blue faces) → the pixel order was ignored. Read the
  bitmap info.
- `find_window` returns None while the dialog is visible → the title differs
  (PT may add a suffix) or the frames differ by more than the tolerance. Compare
  the probe's `windows` output.
- The process hangs on capture → the completion handler never fired. Keep the
  timeout, and make sure `pyobjc` is ≥ the PHASE-00 floor.
