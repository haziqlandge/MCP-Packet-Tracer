# FUTURE WORK

Ordered by what unblocks what. Open problems are in `ISSUES.md`; finished work is
in `PREVIOUS_WORK.md`.

---

## 0. Start here (written 2026-10-25, after macOS UI mode was fixed and proven live)

Read `CLAUDE.md` first, then this section. Replace this section rather than
appending another one.

### The situation

PHASE-00 to PHASE-03 and PHASE-05 are complete. PHASE-04 still has its real
permission-revocation gate open. PHASE-06 and PHASE-07 are implemented; their
real-client and fresh-grant gates are open, but every PHASE-07 UI-mode box is now
ticked. Upstream `main` @ `d9bb732` is merged (`f7cb31e`). Nothing since
`f7cb31e` is committed or pushed, so CI has not run on it. The user commits
through their own `/commitskill`.

### Verification state

Mac (macOS 26.6, PT 9.0.1): **1389 passed** in 38.43 s
(`.venv/bin/python -B -m pytest -q -p no:cacheprovider`), 2026-10-25. Planning
checker skipped: not installed. Windows backend files unchanged.

macOS UI mode works live end to end with Claude in front, PT in full screen and
the canvas zoomed out (PREVIOUS_WORK 2.12, last two subsections). Closed today:
X4, X13, X16, X18, X19. Open: X20 (a tool switch before the click, now guarded,
cause unconfirmed), X12 (no canvas scroll bars on macOS).

### What this session did

Built a DHCP lab and wrote the user a Word write-up with 11 UI-mode captures
(`projects/dhcp-lab/`). Then fixed UI mode test-first: activate PT when its
windows are off the current Space, leave full screen, reset the zoom before a
canvas click, and re-check the Select tool right before the click. Docs updated:
README, `docs/tools.md`, `skill/reference/rough-edges.md`, `pt://guide`, and a
PHASE-05 amendment. The lab's call lists live only in the session scratchpad.
The OSPF canvas is backed up as `projects/ospf-lab/lab-ospf-live-backup.pkt`.

### NEXT, in order

1. The user commits through `/commitskill`, then, with their OK, push
   `cross-platform` and record the CI result.
2. X20: ask whether keys were typed on the Mac during the runs; if it recurs,
   the guard's refusal names the tool that was active.
3. The OSPF write-up in the user's CCE2 format still waits on their details
   (experiment number, title, group). Retake its UI captures with the fixes.
4. Optional: save the DHCP lab call lists under `tests/live/labs/` like the
   others (`dhcp-*`), if the user wants them in the repo.
5. A release `.pts` should carry the fixed `main.js` and the new webview (X3).
6. Keep the Windows live regression (§2, now including the presenter's Zoom
   Reset, X5) and the PHASE-04 revocation gap honest.

### Waiting on the user

Commit, push, the OSPF document details, and the fresh-client acceptance run
(back up/reset setup, reset grants). An upstream PR requires separate approval;
see §2 for Windows live regression and §3 for the upstream-PR cleanup rules.

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
