# FUTURE WORK

Ordered by what unblocks what. Open problems are in `ISSUES.md`; finished work is
in `PREVIOUS_WORK.md`.

---

## 0. Start here (written 2026-10-10, on the Mac, after PHASE-05's live run)

Read `CLAUDE.md` first, then this section. **Replace this section when its
contents are done. Do not append a second one.**

### The situation

PHASE-00 to PHASE-03 and PHASE-05 are complete. PHASE-04 has one open box: the
real-revocation check (the user declined to revoke a grant; a simulated check
passed). macOS UI mode works end to end (`tests/live/ui.json` 8/8). The work is
committed as `f86cfe9` and pushed to `haziqlandge/MCP-Packet-Tracer`
`cross-platform`; CI is green on Windows, Ubuntu and macOS. Only one session
should touch this checkout (a parallel session wrote PHASE-04's code earlier).

### Progress

Phases complete: 00, 01, 02, 03, 05. PHASE-04: 4 of 5 (open: a real
revocation). Overall 71.9 % on the tracker.

### What the last session did

- Reloaded the mods into this session's hot-reload folder (the user enabled it).
- PHASE-03 complete (PREVIOUS_WORK 2.7).
- PHASE-04: reviewed the parallel session's `backends/macos/`, re-verified its
  capture box live, recorded it (2.8); simulated the revoked-grant check.
- PHASE-05 (2.9): `ax.py` (walk shared with the probe), locator second pass
  (macOS canvas name), `events.py` (HID click with PT frontmost and the canvas
  under the point, cursor restored; sections by focus + Space), `MacBackend`
  navigation; three live bugs fixed test-first (hit test raced the window
  raise; section check lags Space by ~0.15 s; off-view device clicked at a stale
  point). Calibration verified at all four canvas corners; timings measured;
  the Delete-tool guard checked live. Probe `hit` command; `live_smoke` timings.
- ISSUES: X4 rewritten; X11 updated (second empty-output case); new X12 (no
  canvas scroll bars on macOS), X13 (`AXWindows` empty off-Space), X14 (file
  channel latency).

### Verification state

macOS: `.venv/bin/python -m pytest -q` **1181 passed**, 2026-10-10. CI run
38059124205 at `f86cfe9`: 6/6 jobs green. `check_plan.py`: skipped (planning
skill not installed on the Mac). Live (HTTP channel, Control Center open):
`tests/live/ui.json` 8/8 with PNGs checked by eye; `headless.json` not re-run
this session. Windows live: nothing run (§2).

### NEXT, in order

1. PHASE-06 (out of the box: `pt-mcp doctor`, onboarding, the `platform` block
   in `pt_bridge_status`). Include `pt_ui_mode("status")` showing the capture
   remedy when only Screen Recording is missing (PHASE-04 box note).
2. Re-run `tests/live/headless.json` once (last full run was PHASE-02).
3. Watch X11 and X13 in live runs; X12 needs PT's scroll offset (unverified API).

### Waiting on the user

- Whether a real Screen Recording revocation should ever be measured (the last
  PHASE-04 box).
- Later: a session on the Windows machine for §2; whether the fixed `.pts`
  ships (ISSUES X3); an upstream PR only with the user's OK (§3).

---

## 1. Automatic `.pts` installation (investigate; not scheduled)

Context: installing the `.pts` is the one manual step left on every OS
(`EVALUATION.md` §9). PT keeps its script modules somewhere under the user folder
(`PT.conf` per the Cisco FAQ, RESEARCH S1), but the format is unknown, and
guessing it breaks AGENTS rule 6.

Steps:

1. On any machine with PT, diff the user folder before and after adding a
   `.pts` through the menu.
2. If one file changes predictably and PT accepts an edited copy, propose a
   `pt-mcp install-extension` to the user.
3. Otherwise, record "not automatable" in PREVIOUS_WORK.

Done when: either a tested installer exists, or the finding is recorded.

## 2. Windows UI regression check (after PHASE-03; needs the Windows machine)

Context: PHASE-03 moved the Windows UI code behind `WindowsBackend` on a Mac,
where it cannot run (`CONSTRAINTS.md` C4, ISSUES X5). `win32.py` and `uia.py`
are byte-identical (100 % renames); what is new on Windows is
`ui/backends/windows/backend.py` (one `Uia()` per call, roles from `u.m`'s
`UIA_*ControlTypeId`, rects read lazily) and the presenter's locator lookups.

Steps, on the Windows machine:

1. Pull the branch and run `python -m pytest -q` (≥ the Windows baseline in
   `CLAUDE.md` §5). This is also the first CI-equivalent run of the PHASE-03
   tests on Windows (not pushed yet).
2. Launch PT 9.0.1 and run the live smoke list with UI mode, show and capture
   (`EVALUATION.md` §7), at least `tests/live/ui.json`.
3. Compare with the 2026-10-10 result (28/28). Watch for: the step text
   "dialog opened (click posted, cursor not moved)", the Select-tool refusal,
   Email's nested close loop, and COM errors on worker threads.

Done when: 28/28 again (close X5), or each regression is an ISSUES row.

## 3. Upstream PR (only with the user's OK)

Delete the plan docs (`CLAUDE.md` header lists them), rebase on upstream `main`,
and open one PR to Mats2208/MCP-Packet-Tracer.

## 4. Phase status

| Phase | State |
|---|---|
| 00 | complete (7/7) |
| 01 | complete (6/6) |
| 02 | complete (6/6) |
| 03 | complete (9/9); Windows live check pending (§2) |
| 04 | 4 of 5 (open: a real revocation) |
| 05 | complete (9/9) |
| 06 | next |
| 07 | waiting on 01–06 |
| 08 | gated (entry criteria in its file) |
