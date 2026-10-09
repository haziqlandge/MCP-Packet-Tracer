# PREVIOUS WORK

What has been done and proved on `feat/cross-platform`. Open items are in
`ISSUES.md`; next steps are in `FUTURE_WORK.md`. Work before this branch
(device-panel control, context-cost optimisation, English conversion) is in
`CHANGELOG.md` and git history.

Part 1 is the story. Part 2 is the set of things that were expensive to learn and
would be expensive to learn twice. **Grep this file before re-deriving
anything. Do not read it whole.**

---

# Part 1 — Timeline

**2026-10-10 — Cross-platform plan written (Windows machine).** The user asked
for the MCP to work on macOS on a separate branch, with "cross modularity", and
set the bar: connect the MCP and it works out of the box on any OS. User
decisions: full UI-mode parity on macOS now; the plan docs committed on the
branch; every phase executed on the user's Mac, which has PT. Branch
`feat/cross-platform` was created from `main` @ `bcb2ef3`. `PLAN/`, `RESEARCH/`
and the state docs were written. The user's three loaded Claude Code mods were
copied into `claude-mods/` (generated types left out) so the Mac runs the same
setup. `progress-tracker/tests/check.mjs` parses all nine phases. No server code
changed. Tests (Windows, before branching): baseline in `CLAUDE.md` §5.

---

# Part 2 — Findings that must not be re-derived

## 2.1 The file mailbox is mis-addressed on macOS and Linux (code reading, not yet measured)

`mcpBridgeDir()` in `EXTENSION/script-engine/main.js:121-129` takes the
directory of the first token candidate, `<home>/AppData/Local/...`, without
checking that a token exists there. Python writes to
`~/.local/state/packet-tracer-mcp/bridge` on POSIX. HTTP pairing is unaffected,
because `getMcpToken()` does check `fileExists` on each candidate. Read on
2026-10-10 at `bcb2ef3`. PHASE-00 confirms it live. The design that follows is
`PLAN/INTERFACES.md` §5.

## 2.2 This fork has never rebuilt the `.pts`

`git log -- EXTENSION/script-engine/main.js` shows only `ad59a02` (reorganise
into `EXTENSION/`) and `442adef` (English comments). Whatever runs in users'
PT is upstream's V5.2 build. That is why the plan makes the server adapt to the
extension (C5) instead of depending on a new build.

## 2.3 Qt's macOS bridge exposes objectName paths only in recent Qt

qtbase `dev` implements `accessibilityIdentifier` as
`QAccessibleBridgeUtils::accessibleId(iface)`. The 5.15 and 6.2 branches do not
implement it (RESEARCH S4, S5). Whether PT's bundled Qt has it is PHASE-00's
open question.

## Where the detailed evidence lives

| Artifact | Contents |
|---|---|
| `RESEARCH/INDEX.md` | Sources S1–S11, graded |
| `RESEARCH/SYNTHESIS.md` §9 | The 12 questions PHASE-00 answers |
| `tests/fixtures/macos/` | AX recordings (from PHASE-00) |
