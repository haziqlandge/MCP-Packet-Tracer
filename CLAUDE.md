# CLAUDE.md — read this first

Operating rules for agent sessions on the `feat/cross-platform` branch. Short on
purpose. The repo-wide rules live in `AGENTS.md`, imported here:

@AGENTS.md

This file is branch-local working state. It is force-added (the repo's
`.gitignore` ignores `CLAUDE.md`) and must be deleted, together with `PLAN/`,
`RESEARCH/`, `FUTURE_WORK.md`, `ISSUES.md`, `PREVIOUS_WORK.md`, `DATA.md` and
`claude-mods/`, before any upstream PR.

## 1. Environment

- **Executor: the user's Mac with Packet Tracer.** Every phase runs there. The
  model, macOS version and PT path are recorded in PHASE-00 (PREVIOUS_WORK Part 2).
- **The Windows machine** (Windows 10 Pro, PT 9.0.1) wrote the plan. It is
  needed again only for the Windows UI regression check (`FUTURE_WORK.md` §2).
  Never mark a Windows live criterion done from the Mac.
- One PT and one bridge at a time. Run live checks serially, never two agents
  against one PT.
- You may quit and relaunch PT when needed. **Save the topology first**, and
  check `pt_query_topology` before any `pt_save_project`: an empty-canvas save
  overwrites a good `.pkt`.
- The user's Claude Code mods (progress bars, cache timer, cost ticker) are in
  `claude-mods/`. `claude-mods/README.md` says how to load them on the Mac. The
  progress bar reads the phase files' acceptance boxes. Tick them as you go (§7).
- Prefer handing bulk, output-heavy work (mass edits, long smoke loops) to a
  cheap subagent behind a mechanical check you run afterwards (pytest, grep, a
  diff). Keep the judgment calls in the main session.

## 2. Where to look

**If you are a fresh session, read `FUTURE_WORK.md` §0 next.** Then the ISSUES
rows it names, then `PLAN/INDEX.md`'s phase table, then the current phase file,
then only the sections that phase cites. Do not read every document.

| Question | Document |
|---|---|
| What is this, how do I run it | `README.md`, `CODEMAP.md` (which file owns what) |
| What is broken or unproven right now | `ISSUES.md` |
| What was done, and what must not be re-derived | `PREVIOUS_WORK.md` (grep it; do not read it whole) |
| What to do next | `FUTURE_WORK.md` |
| Where the artifacts live (`.pts`, token, mailbox, fixtures) | `DATA.md` |
| What the system is supposed to be | `PLAN/INDEX.md`, then one phase file |
| Why a design decision was made | `RESEARCH/SYNTHESIS.md` |

`PLAN/` is what *should* exist; the repository is what *does*. When they
disagree, the repository wins and `ISSUES.md` records the gap.

## 3. Hard rules

- **C1** Only `infrastructure/platform/` and `infrastructure/ui/backends/` look at the OS.
- **C2** Every module imports on every OS. pyobjc and comtypes are imported lazily, inside backends.
- **C3** Headless paths never trigger a macOS permission prompt.
- **C4** The Windows backend is moved, not rewritten: `win32.py` and `uia.py` bodies stay byte-identical.
- **C5** The released V5.2 `.pts` keeps working on every OS.
- **C6** No guessed API: PT methods per AGENTS rule 6; pyobjc names exercised by `devtools/macos_probe.py` first.
- **C8** No live claim from offline tests. No Windows claim from the Mac.
- **C10** macOS: points for rects and clicks, pixels for captures. Never mix them.

The rest, C7, C9 and C11, are in `PLAN/CONSTRAINTS.md`.

## 4. Do not modify carelessly

| Path | Why |
|---|---|
| `src/packet_tracer_mcp/infrastructure/ui/backends/windows/win32.py`, `uia.py` (today `infrastructure/ui/`) | Cannot be verified live from the Mac (C4) |
| `src/packet_tracer_mcp/infrastructure/execution/bridge_token.py` | Pairing and security. See its docstring and `SECURITY.md` |
| `src/packet_tracer_mcp/infrastructure/execution/file_bridge.py` `_write_atomic` | Byte-exact writes; CR/LF inside JS is a SyntaxError in PT |
| `EXTENSION/script-engine/main.js` | Ships inside the `.pts`; must stay compatible with servers already installed |
| `tests/fixtures/tool_api.json` | Regenerate only in PHASE-07, on purpose (C9) |
| `tests/fixtures/macos/*.json` | Recorded from the real PT; never hand-edited |

## 5. Before claiming anything is complete

```bash
python -m pytest -q
```

```bash
python "$HOME/.claude/skills/planning-mode/scripts/check_plan.py" .
```

For live claims (PT open, extension loaded):

```bash
python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/headless.json | grep -E "^=====|Traceback|NameError|PT_ERROR"
```

Baselines (each OS has its own line; a drop below it is a regression):

- Windows: **825 passed** as of 2026-10-10, Windows 10 Pro, Python 3.14.8, at `bcb2ef3`.
- macOS: **1181 passed** as of 2026-10-10, macOS 26.5.1 (arm64, Mac17,9), Python 3.12.15 (Homebrew, `.venv`), at `f86cfe9`.
- CI (GitHub Actions, run 38059124205 at `f86cfe9`): ubuntu 1180 passed + 1 skipped, windows 1178 + 3 skipped, macos 1181, on 3.11 and 3.13.

These lines are the only place the baseline is recorded. Run the commands and
read the output. "Should pass" is not evidence. If the planning skill is not
installed on the Mac, skip the second command and say so.

## 6. Keeping the docs true (end of every session)

1. Run §5 and record the result in `FUTURE_WORK.md` §0.
2. A new problem becomes an `ISSUES.md` row with its evidence. When one closes,
   delete the row and record the finding in `PREVIOUS_WORK.md` Part 2.
3. An expensive lesson goes to `PREVIOUS_WORK.md` Part 2. A trap that bites
   twice also gets one line in §8.
4. When a design decision changes, add a dated amendment in the PLAN file that
   owns it, then grep `PLAN/` for every other statement of the old decision.
5. Check that every acceptance box met this session was ticked when it was met
   (§7). Untick any whose evidence did not hold up.
6. Rewrite `FUTURE_WORK.md` §0 whole. Never append to it.
7. Commit with the user's git identity and **no AI attribution lines**
   (no `Co-Authored-By`, no "Generated with"). Messages in English.

## 7. Progress tracking: mark it while you work

The user follows the work on the progress-tracker bars (`claude-mods/`). The
bars read the `- [ ]` boxes under `## Acceptance criteria` in each
`PLAN/phases/PHASE-NN.md`. They re-read the files every few seconds, so a box
shows the moment it is saved. The user has asked for this explicitly: the bars
must show where the work really stands, all the time.

- **Tick a box the moment its check passes**, with its evidence
  (`- [x] <criterion> — <command, number or file; date>`), in the same edit or
  commit as the work it proves. Not before the check passes, not at the end of
  the session, and never several boxes in one bulk replace.
- **Never pre-tick at the start and never batch at the end.** A bar that sits at
  0 % for hours and then jumps to 100 % gives the user a wrong picture. That has
  already happened once.
- **Before starting work that no box covers, add a box first.** Make it a
  checkable step in that phase's `## Acceptance criteria` (for example
  `- [ ] Probe dumps the PT main window's AX tree`), then tick it when the step is
  done. Large criteria may be split into a few smaller boxes, so the bar moves in
  reasonable steps.
- **Mark blocked and partial work too.** Leave the box open (`- [ ]`) and append
  `— **BLOCKED: <on what>**`, with what is and is not shown. A blocked box is
  never ticked. Do not use `- [~]`: the tracker drops those boxes from both
  counts, so a phase with only `[~]` left shows as DONE (it happened on
  2026-10-10).
- **The bar follows the open phase file edited most recently.** Touch other
  phase files only when you work on them, or the bar's focus jumps to them.
- A phase is complete when all its boxes are ticked. Record it in
  `FUTURE_WORK.md` §0 and the phase-status table there. Do not edit
  `PLAN/INDEX.md` to mark progress.

## 8. Traps that have already cost time twice

- **The running MCP process keeps old code.** After editing `src/`, the client's
  `packet-tracer` server still runs the previous code until it is reconnected.
  Use `devtools/live_smoke.py` (this checkout) for live checks instead.
- **Editing files through a shell can corrupt them.** On Windows, PowerShell
  `Set-Content` added a BOM and broke UTF-8. Use the editor tools, and write JSON
  as plain UTF-8.
