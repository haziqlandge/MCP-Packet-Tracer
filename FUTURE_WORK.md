# FUTURE WORK

Ordered by what unblocks what. Open problems are in `ISSUES.md`; finished work is
in `PREVIOUS_WORK.md`.

---

## 0. Start here (written 2026-10-10)

Read `CLAUDE.md` first, then this section. **Replace this section when its
contents are done. Do not append a second one.**

### The situation

The plan was written on the Windows machine on branch `feat/cross-platform`
(from `main` @ `bcb2ef3`). No code has changed yet: the branch holds only the
plan docs. **The next session runs on the user's Mac**, which has Packet Tracer.
It starts with PHASE-00, the bring-up and spike. Everything the later phases
assume about macOS is unmeasured until then (`RESEARCH/SYNTHESIS.md` §9).

### Progress

PHASE-00: 0 of 7 acceptance items. Overall: 0 of 9 phases (8 core + 1 gated
bonus), 0 %.

### What the last session did

- Wrote `PLAN/`, `RESEARCH/` and the state docs (`PREVIOUS_WORK.md` Part 1,
  2026-10-10).
- Found by reading the code: the file mailbox cannot work on macOS or Linux
  (ISSUES X1), and `XDG_STATE_HOME` breaks pairing (X6).

### Verification state

Windows: the offline suite matches the `CLAUDE.md` §5 baseline (run 2026-10-10
before branching). macOS: not run yet. `check_plan.py`: 0 errors at commit time.

### NEXT, in order

1. On the Mac: clone the fork and check out `feat/cross-platform`
   (needs B1 done). Load the mods (`claude-mods/README.md`), then follow
   `PLAN/PREREQUISITES.md`.
2. Run PHASE-00 sections 1–2: environment, macOS baseline, smoke harness. Record
   the baseline in `CLAUDE.md` §5. From the first step on, tick each acceptance
   box the moment its check passes (`CLAUDE.md` §7). The user watches the bars.
3. PHASE-00 sections 3–5: pairing facts, the probe, the recordings. Answer every
   question in SYNTHESIS §9 in PREVIOUS_WORK Part 2.
4. Append the dated "Local empirical update" to `RESEARCH/SYNTHESIS.md`. If an
   answer contradicts a locked decision, amend the PLAN file that owns it
   (step 4 of `CLAUDE.md` §6) before starting PHASE-01.
5. PHASE-01 and PHASE-03 next, in either order or in parallel.

### Waiting on the user

- **B1:** push `feat/cross-platform` to the fork so the Mac can clone it.
- Which MCP client(s) the Mac uses (Claude Code, Claude Desktop, both). PHASE-00
  measures each one's cwd, PATH and responsible app.
- Later: a session on the Windows machine for §2 below.

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

Context: PHASE-03 moves the Windows UI code behind `WindowsBackend` on a Mac,
where it cannot run (`CONSTRAINTS.md` C4, ISSUES X5).

Steps, on the Windows machine:

1. Pull the branch and run `python -m pytest -q` (≥ the Windows baseline in
   `CLAUDE.md` §5).
2. Launch PT 9.0.1 and run the live smoke list with UI mode, show and capture
   (`EVALUATION.md` §7).
3. Compare with the 2026-10-10 result (28/28).

Done when: 28/28 again (close X5), or each regression is an ISSUES row.

## 3. Upstream PR (only with the user's OK)

Delete the plan docs (`CLAUDE.md` header lists them), rebase on upstream `main`,
and open one PR to Mats2208/MCP-Packet-Tracer.

## 4. Phase status

| Phase | State |
|---|---|
| 00 | next (on the Mac) |
| 01 | waiting on 00 |
| 02 | waiting on 00, 01 |
| 03 | waiting on 00 |
| 04 | waiting on 01, 03 |
| 05 | waiting on 04 |
| 06 | waiting on 02, 05 |
| 07 | waiting on 01–06 |
| 08 | gated (entry criteria in its file) |
