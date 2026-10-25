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
| Q1 | PHASE-06/07 real-client and fresh-grant acceptance is pending | Offline suite 1368 passed (2026-10-24); live headless doctor passes. This executor lacks ChatGPT Accessibility; Claude Code CLI is absent from PATH. A backup/reset/revocation approval is pending, and prior revocation was declined. No fresh action count or UI capture claim yet |

## 3. Data and integrity (D#)

None open.

## 4. Experiments that cannot support their intended claim (E#)

| # | Issue | Evidence |
|---|---|---|
| E1 | Most macOS API claims in `RESEARCH/` come from docs and web sources, not this Mac. Until the probe has exercised a name, it may not justify code (C6) | `RESEARCH/INDEX.md` grades; the names verified so far are listed in PREVIOUS_WORK 2.4 |

## 5. Environment and integration (X#)

| # | Issue | Evidence |
|---|---|---|
| X3 | The fixed `.pts` (canonical mailbox) is not in Releases and is untested on Windows with PT. The Mac now runs `MCP-BUILDER-os-shortcuts.pts`: V5.2 plus the OS-aware webview, with V5.2's `main.js`, so still the legacy mailbox | Mailbox-fix build installed with the user's OK in PREVIOUS_WORK 2.6, later gone (the Mac was reset). 2026-10-24 build: PREVIOUS_WORK 2.12; `pt_bridge_status` → legacy mailbox `~/AppData/Local/...`. A release build should carry both the fixed `main.js` and the new webview. `tests/test_main_js_paths.py` covers the Windows path offline only. Open: the user decides whether it ships; a Windows live check before it does |
| X5 | After PHASE-03, Windows UI mode is refactored but unverified live (the executor is a Mac). Since 2026-10-25 the OS-neutral presenter also presses Zoom Reset before a canvas click when the zoom is not 100 % (if it finds a button named "Zoom Reset"); untested on Windows | `CONSTRAINTS.md` C4, C8; check in `FUTURE_WORK.md` §2. Windows backend files unchanged (`git diff` empty) |
| X9 | macOS UI mode cannot stay invisible the way Windows' does: opening a dialog by canvas click needs PT activated and the cursor moved and restored (pid-posted clicks never reach the canvas), and switching a Config/Services section needs PT frontmost (`AXPress` only toggles a checkable button; focus + Space works in the foreground only) | PREVIOUS_WORK 2.4 #6, #7. Design: PHASE-05 amendment. Docs must say so (PHASE-07) |
| X15 | `license boot module ... securityk9` is dropped silently when it follows `configure terminal` in the same `pt_cli` call; in its own call PT shows the EULA. Cause unknown (timing in PT's console?). Not macOS-specific | 2026-10-24, PT 9.0.1, 2911: same batch → no EULA, `Next reboot None`, 3 of 3; own call → `ACCEPT? [yes/no]:`, 2 of 2 (one of them after an unrelated error line). Worked around in `tests/live/labs/ips-3-licence.json`; noted in `skill/reference/rough-edges.md` |
| X10 | For up to 10 s after the Control Center window closes, `pick_channel()` still chooses HTTP (the bridge counts the webview as connected for 10 s after its last poll), so a command queued then is never answered; it may run later, when the window reopens. Every OS, not macOS-specific | Measured 2026-10-10: `pt_query_topology` ~3 s after closing → "No response from PT (timeout)"; at 33 s → answered over the file channel. `live_bridge.py:155` (`< 10.0`), `bridge_context.py` `pick_channel`. Possible fix: prefer the file channel when its heartbeat is fresh and the last poll is older than the 2 s long-poll |
| X8 | PT itself listens on `*:39000`, the MCP server's default streamable-HTTP port: `python -m packet_tracer_mcp` (no `--stdio`) cannot bind while PT runs on a Mac. stdio clients are unaffected | `lsof -iTCP:39000` → `PacketTra 10015 ... TCP *:39000 (LISTEN)`; `server.py` `TRANSPORT_PORT = 39000`. Fix: a `--port` option and a doctor check (PHASE-01 or PHASE-06) |
| X11 | Twice, the first `pt_cli` command with `show=True` came back `[ok]` with **empty output**, and the second time PT's own CLI tab showed no trace of the command (it ends at `Router>`) | 2026-10-10: PHASE-03 live run (null backend) and the first PHASE-05 `ui.json` run (R1 CLI tab open). The same command headless, twice, and in the next `ui.json` run printed its output. Not the UI backend: `run_commands` sends the command; why PT drops it is unknown (prompt detection? the console just shown?). `console_session.py` |
| X12 | macOS exposes no canvas scroll bars (not even when the scene does not fit the view), so the presenter reads the canvas scroll as 0. With a scrolled view the first click can land on another device (a stray dialog), and the second attempt clicks the view's centre after centring | Live 2026-10-10: SRV1 at 2200,900 and 1800,300 → no AXScrollBar in the main window; opened by clicking the centre after centring (PREVIOUS_WORK 2.9). One R1 open missed right after the canvas changed (4/4 on retry). Console scroll bars do appear once the console overflows. A real fix needs the view's scroll offset from PT's API (unverified, AGENTS rule 6) |
| X14 | Over the file channel (Control Center closed) one PT round trip took 0.21–1.42 s, so `pt_ui_open` of an already-open dialog took up to 1.84 s against the 1.5 s target; over HTTP it took 0.34–0.49 s | Profiled 2026-10-10 (PREVIOUS_WORK 2.9): the macOS backend's share is < 0.2 s. The latency is the extension's file polling; tuning it means a `main.js` change (C5) |
| X20 | macOS UI mode: twice the canvas click landed with another PT tool active although the presenter had seen Select on before PT came to the front: a note editor opened (Place Note, N), then "Create Complex PDU" for PC4 (C). Suspected cause: keys typed on the Mac while UI mode had PT in front (each PT tool has a one-key shortcut; Del is Delete). Guarded, cause unconfirmed | 2026-10-25: tool buttons read live: Select (Esc), Place Note (N), Add Complex PDU (C), Delete (Del), Inspect (I), Draw Line (L)... The macOS click route now re-checks Select with PT in front right before posting, presses it once more, and refuses naming the active tool otherwise (`backend.py` `_select_tool_still_on`, 5 tests). Live after the guard: 7 clicks, no stray note or PDU. Not reproduced on purpose; whether the user was typing is unknown |

## 6. Docs (F#)

| # | Issue | Evidence |
|---|---|---|

## 7. What must not be claimed

- That anything works on macOS before PHASE-00 has run there.
- That Windows UI mode still works after PHASE-03, before `FUTURE_WORK.md` §2 has run.
- That Linux UI mode exists (PHASE-08 is gated).
- "Zero setup": the `.pts` install and the macOS grants remain user actions.
