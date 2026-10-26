# FUTURE WORK

Ordered by what unblocks what. Open problems are in `ISSUES.md`; finished work is
in `PREVIOUS_WORK.md`.

---

## 0. Start here (written 2026-10-26, after the simulation demos were installed)

Read `CLAUDE.md` first, then this section. Replace this section rather than
appending another one.

### The situation

PHASE-00 to PHASE-03 and PHASE-05 are complete. PHASE-04 still has its real
permission-revocation gate open. PHASE-06 and PHASE-07 are implemented; their
real-client and fresh-grant gates are open. The Control Center webview now has a
SIMULATION tab with four ready-made demos (PREVIOUS_WORK 2.14). That work is on
the branch `cross-platform-sim`, pushed to origin, not yet merged into
`cross-platform`. Commits go through the user's `commitskill`: no AI
attribution and no `feat:`-style prefixes.

### Verification state

Mac (macOS 26.6, PT 9.0.1): **1455 passed** in 40.0 s
(`.venv/bin/python -m pytest -q`), 2026-10-26. Planning checker not run this
session. Windows backend files unchanged.

Live on the Mac: the installed module is
`~/Cisco Packet Tracer 9.0.1/extensions/MCP-BUILDER-sim-demos.pts`. From its
buttons on SLA2: PC to PC 1/1, server to PC 1/1, broadcast 20 replies. Server to
all PCs was started but the result was left to the user.

### What this session did

Pasted the new `index.html` and `interface.js` into the MCP-BUILDER module,
exported and installed it. Found that `$se("runCode", ...)` loses newlines, so
the demo helpers never loaded; now sent as one line, with a test.

### NEXT, in order

1. Hear back from the user on "Server to all PCs" and the demos in general.
2. Merge `cross-platform-sim` into `cross-platform` once the user is happy.
3. Windows live regression (§2), now also the SIMULATION tab and
   `pt_simulate_pdu(animate=True)`.
4. X20: ask whether keys were typed on the Mac during the runs.
5. The OSPF write-up in the user's CCE2 format still waits on their details.
6. A release `.pts` should carry the fixed `main.js` and the new webview (X3).
7. Keep the PHASE-04 revocation gap honest.

### Waiting on the user

Their check of the four demos, the OSPF document details and the fresh-client
acceptance run. An upstream PR requires separate approval; see §2 for Windows
live regression and §3 for the upstream-PR cleanup rules.

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
