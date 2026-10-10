# ISSUES

Everything currently open, in one place. Closed work lives in `PREVIOUS_WORK.md`;
planned work in `FUTURE_WORK.md`.

Each row names its evidence. **When an issue closes, delete the row.** Do not
annotate it in place, or this file becomes the thing it replaced. IDs are never
reused.

## 1. Blocked on a decision or an action (B#)

| # | Issue | Evidence |
|---|---|---|
None open.

## 2. Open acceptance gates (Q#)

| # | Issue | Evidence |
|---|---|---|
| Q1 | PHASE-06/07 real-client and fresh-grant acceptance is pending | Offline suite 1232 passed; live headless doctor passes. This executor lacks ChatGPT Accessibility; Claude Code CLI is absent from PATH. A backup/reset/revocation approval is pending, and prior revocation was declined. No fresh action count or UI capture claim yet |

## 3. Data and integrity (D#)

None open.

## 4. Experiments that cannot support their intended claim (E#)

| # | Issue | Evidence |
|---|---|---|
| E1 | Most macOS API claims in `RESEARCH/` come from docs and web sources, not this Mac. Until the probe has exercised a name, it may not justify code (C6) | `RESEARCH/INDEX.md` grades; the names verified so far are listed in PREVIOUS_WORK 2.4 |

## 5. Environment and integration (X#)

| # | Issue | Evidence |
|---|---|---|
| X3 | The fixed `.pts` (canonical mailbox) is installed and working on the Mac only; it is not in Releases, and it is untested on Windows with PT | Built in PT's module editor and installed with the user's OK (PREVIOUS_WORK 2.6): `fileBridgeStatus().dir` = `~/.local/state/.../bridge`, no legacy note. `tests/test_main_js_paths.py` covers the Windows path offline only. Open: the user decides whether it ships; a Windows live check before it does |
| X4 | macOS UI mode is built but not yet proven live end to end; Linux gets the `NullBackend` | PHASE-04: `MacBackend` windows, capture, permissions (capture verified live). PHASE-05: navigation, the HID click and keyboard section switch are built and tested offline (`test_macos_click_route.py`, `test_macos_locators.py`); `tests/live/ui.json` not yet run on the Mac. Linux is PHASE-08 |
| X5 | After PHASE-03, Windows UI mode is refactored but unverified live (the executor is a Mac) | `CONSTRAINTS.md` C4, C8; check in `FUTURE_WORK.md` §2 |
| X9 | macOS UI mode cannot stay invisible the way Windows' does: opening a dialog by canvas click needs PT activated and the cursor moved and restored (pid-posted clicks never reach the canvas), and switching a Config/Services section needs PT frontmost (`AXPress` only toggles a checkable button; focus + Space works in the foreground only) | PREVIOUS_WORK 2.4 #6, #7. Design: PHASE-05 amendment. Docs must say so (PHASE-07) |
| X10 | For up to 10 s after the Control Center window closes, `pick_channel()` still chooses HTTP (the bridge counts the webview as connected for 10 s after its last poll), so a command queued then is never answered; it may run later, when the window reopens. Every OS, not macOS-specific | Measured 2026-10-10: `pt_query_topology` ~3 s after closing → "No response from PT (timeout)"; at 33 s → answered over the file channel. `live_bridge.py:155` (`< 10.0`), `bridge_context.py` `pick_channel`. Possible fix: prefer the file channel when its heartbeat is fresh and the last poll is older than the 2 s long-poll |
| X8 | PT itself listens on `*:39000`, the MCP server's default streamable-HTTP port: `python -m packet_tracer_mcp` (no `--stdio`) cannot bind while PT runs on a Mac. stdio clients are unaffected | `lsof -iTCP:39000` → `PacketTra 10015 ... TCP *:39000 (LISTEN)`; `server.py` `TRANSPORT_PORT = 39000`. Fix: a `--port` option and a doctor check (PHASE-01 or PHASE-06) |
| X11 | Twice, the first `pt_cli` command with `show=True` came back `[ok]` with **empty output**, and the second time PT's own CLI tab showed no trace of the command (it ends at `Router>`) | 2026-10-10: PHASE-03 live run (null backend) and the first PHASE-05 `ui.json` run (R1 CLI tab open). The same command headless, twice, and in the next `ui.json` run printed its output. Not the UI backend: `run_commands` sends the command; why PT drops it is unknown (prompt detection? the console just shown?). `console_session.py` |
| X12 | macOS exposes no canvas scroll bars (not even when the scene does not fit the view), so the presenter reads the canvas scroll as 0. With a scrolled view the first click can land on another device (a stray dialog), and the second attempt clicks the view's centre after centring | Live 2026-10-10: SRV1 at 2200,900 and 1800,300 → no AXScrollBar in the main window; opened by clicking the centre after centring (PREVIOUS_WORK 2.9). One R1 open missed right after the canvas changed (4/4 on retry). Console scroll bars do appear once the console overflows. A real fix needs the view's scroll offset from PT's API (unverified, AGENTS rule 6) |
| X13 | For over a minute, PT's `AXWindows` read empty while every PT window was off the current Space (CG `onscreen` false, no frontmost app reported), so `find_window` returned None and a capture would say "not open" | 2026-10-10 PHASE-05 session: `macos_probe windows` ×3 → `ax: []`; minutes later all 3 windows listed again with Claude frontmost. Once, the app element's `AXChildren` listed the 3 windows while `AXWindows` was empty, but the user may have switched Space in between. Not fixed: a fallback to `AXChildren` would be a guess until reproduced (move PT to another Space, read both) |
| X14 | Over the file channel (Control Center closed) one PT round trip took 0.21–1.42 s, so `pt_ui_open` of an already-open dialog took up to 1.84 s against the 1.5 s target; over HTTP it took 0.34–0.49 s | Profiled 2026-10-10 (PREVIOUS_WORK 2.9): the macOS backend's share is < 0.2 s. The latency is the extension's file polling; tuning it means a `main.js` change (C5) |

## 6. Docs (F#)

| # | Issue | Evidence |
|---|---|---|

## 7. What must not be claimed

- That anything works on macOS before PHASE-00 has run there.
- That Windows UI mode still works after PHASE-03, before `FUTURE_WORK.md` §2 has run.
- That Linux UI mode exists (PHASE-08 is gated).
- "Zero setup": the `.pts` install and the macOS grants remain user actions.
