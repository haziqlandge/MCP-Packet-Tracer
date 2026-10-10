# FUTURE WORK

Ordered by what unblocks what. Open problems are in `ISSUES.md`; finished work is
in `PREVIOUS_WORK.md`.

---

## 0. Start here (written 2026-10-10, after PHASE-06/07 implementation)

Read `CLAUDE.md` first, then this section. Replace this section rather than
appending another one.

### The situation

PHASE-00 to PHASE-03 and PHASE-05 are complete. PHASE-04 still has its real
permission-revocation gate open (previously declined). PHASE-06 diagnostics,
onboarding and platform status are implemented. PHASE-07 docs, installed skill,
API snapshot and CODEMAP are updated. Neither phase is complete until its real
client/UI acceptance gates pass; do not replace those checks with offline tests.

### Verification state

Mac: **1233 passed** in 34.72 s using `.venv/bin/python -B -m pytest -q -p
no:cacheprovider`. Registry/CODEMAP: 8 passed. Tool snapshot changes only two
descriptions (`pt_deploy`, `pt_ui_open`); schemas and names unchanged. Strict
MkDocs build passes; installed skill diff empty. Planning checker skipped:
its skill is not installed. The current implementation's CI matrix is pending.

Live: headless doctor passes with PT and extension; platform status reports
both channels and the legacy V5.2 mailbox. ChatGPT is the responsible app for
this executor: Accessibility false, Screen Recording true. The missing-grant
remedy is correct and no preflight check prompts. Headless smoke: all 17
non-capture calls completed; the first R1 CLI response was empty (X11), and
both commands on a repeat produced the expected interface table. The optional
screenshot call was omitted at the user's request.

### What this session did

Implemented doctor/client config/--port, status diagnostics and degraded UI
onboarding. Updated per-OS documentation, CHANGELOG, CONTRIBUTING and CODEMAP;
regenerated the API snapshot deliberately; synced the installed skill. Evidence
is in PREVIOUS_WORK 2.10 and 2.11.

Separately completed the user's two live assessments via MCP. The first was
submitted by the user. The second used the on-screen diagram: Central-SW Fa0/5
uplink and Fa0/6 User-A, with Central-RT/User-B on G0/0/0. Both hosts and rack
network devices were powered on; addressing, saved IOS security configuration,
24 unused-port shutdowns, host connectivity and authenticated SSH were checked.
No assessment screenshots were saved. The MCP disconnected after verification.

### NEXT, in order

1. Commit and push the implementation to this fork's cross-platform branch,
   then record its six-job CI result.
2. Finish PHASE-06/07 fresh-client and real-grant acceptance only after the
   pending user approval. Back up setup before reset; count real user actions.
3. Keep Windows live regression and PHASE-04 revocation gaps honest.

### Waiting on the user

A permission question is pending for the fresh acceptance run: back up/reset
MCP setup, configure a fresh Claude client, reset its grants, then have the
user grant Accessibility and Screen Recording. No elapsed time is approval.
The Claude desktop app exists, but Claude Code CLI is not available in PATH.
An upstream PR still requires separate user approval. See §2 for Windows live
regression and §3 for the upstream-PR cleanup rules.

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
