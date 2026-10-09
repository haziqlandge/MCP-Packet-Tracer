# ISSUES

Everything currently open, in one place. Closed work lives in `PREVIOUS_WORK.md`;
planned work in `FUTURE_WORK.md`.

Each row names its evidence. **When an issue closes, delete the row.** Do not
annotate it in place, or this file becomes the thing it replaced. IDs are never
reused.

## 1. Blocked on a decision or an action (B#)

| # | Issue | Evidence |
|---|---|---|
| B1 | The Mac cannot start until `feat/cross-platform` is pushed to the fork | The branch exists only on the Windows machine (created 2026-10-10) |

## 2. Open acceptance gates (Q#)

| # | Issue | Numbers |
|---|---|---|
| Q1 | No macOS baseline yet; every "≥ the macOS baseline" criterion is unmeasurable until PHASE-00 | `CLAUDE.md` §5 macOS line empty |

## 3. Data and integrity (D#)

None open.

## 4. Experiments that cannot support their intended claim (E#)

| # | Issue | Evidence |
|---|---|---|
| E1 | Every macOS API claim in `RESEARCH/` comes from docs and web sources, not this Mac. Until PHASE-00, none may justify code (C6) | `RESEARCH/INDEX.md` grades; no probe run yet |

## 5. Environment and integration (X#)

| # | Issue | Evidence |
|---|---|---|
| X1 | The file mailbox cannot work on macOS or Linux: the extension polls `~/AppData/Local/packet-tracer-mcp/bridge`, while Python writes to `~/.local/state/packet-tracer-mcp/bridge` | `EXTENSION/script-engine/main.js:121-129` returns the first candidate unchecked; `bridge_token.py:47-53`. Analysis: `RESEARCH/topics/pt-on-macos.md` §3. Fix: PHASE-02 |
| X2 | `pt_deploy`'s clipboard copy is Windows-only | `infrastructure/execution/deploy_executor.py:19-31` (`clip.exe`, returns False elsewhere). Fix: PHASE-01 |
| X3 | No known way to build a `.pts` on the Mac, so a fixed `main.js` cannot reach PT | `EXTENSION/script-engine/README.md` ("package with the webview UI", no steps); PTBuilder files are gitignored. PHASE-00 §3 / PHASE-02 |
| X4 | UI mode is Windows-only (Win32 + UIA, imported directly by the presenter) | `infrastructure/ui/presenter.py:94-104` (`is_available`), plus five `from . import win32` and four `from .uia import Uia` sites inside its methods. Fix: PHASE-03 to PHASE-05 |
| X5 | After PHASE-03, Windows UI mode is refactored but unverified live (the executor is a Mac) | `CONSTRAINTS.md` C4, C8; check in `FUTURE_WORK.md` §2 |
| X6 | `XDG_STATE_HOME` moves the token where the extension cannot look, which breaks pairing on Linux and macOS | `bridge_token.py:49-51` honours it; `main.js:44-56` has no env access. Fix: PHASE-01 |
| X7 | Tool outputs land relative to the cwd; a GUI client may start the server in `/` (read-only) | `tools/canvas.py:80`, `tools/planning.py:355,383,429,443`, `tools/live.py:275,281`, `panel_support.py:43-45`. To be confirmed in PHASE-00 (SYNTHESIS §9, question 10); fix: PHASE-01 |

## 6. Docs (F#)

| # | Issue | Evidence |
|---|---|---|
| F1 | Docs present Windows paths and Windows-only UI mode as universal | `README.md:99,191,260`; `docs/architecture.md:55,60`; `docs/live-deploy.md:11,19`; `docs/tools.md:47,110`; `skill/reference/tools.md:79`; `skill/reference/rough-edges.md:129`; `device_panel_tools.py:188`. Fix: PHASE-07 |

## 7. What must not be claimed

- That anything works on macOS before PHASE-00 has run there.
- That Windows UI mode still works after PHASE-03, before `FUTURE_WORK.md` §2 has run.
- That Linux UI mode exists (PHASE-08 is gated).
- "Zero setup": the `.pts` install and the macOS grants remain user actions.
