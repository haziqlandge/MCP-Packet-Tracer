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

**Amendment 2026-10-10 (PHASE-00, PREVIOUS_WORK 2.4 #7, #8).** Bounds alone are
ambiguous: PT opens **every device dialog at the same frame** (R1, PC1 and SRV1 all
at 406,103 700×708) and keeps hidden twins of some windows ("Logs - MCP BUILDER" as
an on-screen and an off-screen CG window). Among equal-bounds CG windows, prefer the
one whose `kCGWindowName` equals the AX title (readable once Screen Recording is
granted, which capture needs anyway), then the on-screen one. Without Screen
Recording and with colliding frames, the join cannot be exact: return the frontmost
candidate and say so in the step text. `devtools/macos_probe.py` `join_window` is the
measured reference.

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
- **Amendment 2026-10-10 (PHASE-00, PREVIOUS_WORK 2.4 #8).** All three routes
  captured a covered dialog correctly on macOS 26.5.1 (identical pixels), so the
  order stays SCK → CGImage → screencapture. SCK traps, each measured: call
  `NSApplication.sharedApplication()` before SCK or the process **aborts**
  (`CGS_REQUIRE_INIT`); the screenshot handler receives the CGImage as a raw pointer,
  wrap it with `objc.objc_object(c_void_p=ptr.pointerAsInteger)` **inside** the
  handler; never let an exception escape a completion handler (it terminates the
  process). CGImage rows were padded (5632 bytes for 1400 px) with bitmap info 8194
  (BGRA); `screencapture`'s PNG read back through ImageIO is RGBA (info 3).
  `macos_probe.cgimage_to_bgra` is the measured reference for the normaliser.
- The question below is answered: a grant took effect in the running Claude Code CLI
  without a restart (PREVIOUS_WORK 2.4 #9).

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

- [x] All tests pass on the Mac and on CI's three OSes; the suite stays ≥ the macOS baseline — Mac: `.venv/bin/python -m pytest -q` 1119 passed (baseline 825), including `test_macos_permissions`, `test_macos_window_join`, `test_macos_capture_normalise`, `test_permission_prompts_confined`, `test_dependency_markers`, `test_presenter_backend_errors`; `test_imports_every_os` covers C2 for the new `backends/macos/`. CI run 38059124205 on `f86cfe9` (pushed with the user's OK): all 6 jobs green — ubuntu 1180 passed + 1 skipped, windows 1178 + 3 skipped, macos 1181, each on 3.11 and 3.13; 2026-10-10
- [x] Live, Mac: `pt_ui_capture` of PT's main window and of a covered PC1 dialog gives non-blank PNGs at pixel size (`EVALUATION.md` §5), ≤ 2 s — through this checkout's tools (`MacBackend`): main window 3024×1754 px (1512×877 pt) in 0.62 s; PC1 under R1's dialog 1400×1416 px in 1.65 s (the presenter raises it first), both SCK, not blank, PC1's own content. Backend-level, unraised: R1 under PC1 → R1's dialog, 0.17 s (`screenshots/phase04-*.png`); 2026-10-10. Re-verified by the session that took PHASE-04 over: `pt_ui_capture` main window 3024×1752 px and PC1 1400×1416 px, both not blank, each image the right window (`screenshots/phase04-verify-*.png`); 2026-10-10
- [ ] Live, Mac, with permissions revoked: `pt_ui_capture` returns the remedy naming the real client app; a headless tool raises no prompt (C3) — **BLOCKED: a real revocation (the user declined to revoke the grant); simulated instead**: with `permissions.state` reporting Screen Recording missing and `_request_one` rigged to raise, the real registry, bridge and process chain gave `pt_ui_capture` → "UI mode needs Screen & System Audio Recording for claude (~/Library/Application Support/Claude/claude-code/2.1.293/8433d0d9cd0d/claude.app). Open System Settings → … turn on claude … no restart needed"; `pt_bridge_status`, `pt_query_topology`, headless `pt_cli` → 0 prompt requests. Not shown: what macOS itself returns after a real revocation (and whether revoking needs a restart). Gap: `pt_ui_mode("status")` says "available" without mentioning the capture remedy (PHASE-06); 2026-10-10
- [x] Live, Mac: the restart-or-not answer for Screen Recording is recorded in PREVIOUS_WORK Part 2 — PREVIOUS_WORK 2.4 #9: the user's grants (Accessibility, Screen Recording) took effect in the running Claude Code CLI with no restart (same pid passed all preflights, AX and captures then worked); the remedy text says "no restart needed"; 2026-10-10
- [x] `pip install -e .` on the Mac installs the pyobjc packages without `[ui]`; Windows CI installs `comtypes`; Ubuntu installs neither — Mac: `pip install -e .` makes `packet-tracer-mcp` require the five pyobjc packages, and a dry-run into a fresh venv pulls them (no comtypes); markers checked offline for win32/linux (`test_dependency_markers.py`). CI run 38059124205 (`.[test]` install): windows-latest installed comtypes 1.4.17 and no pyobjc, macos-latest pyobjc-core 12.2.2 and no comtypes, ubuntu-latest neither; 2026-10-10

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
