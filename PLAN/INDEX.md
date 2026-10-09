# PLAN — Index

Making the Packet Tracer MCP server work out of the box on Windows, macOS and
Linux, with UI mode at full parity on macOS. Research backing lives in
`RESEARCH/`. `RESEARCH/SYNTHESIS.md` is the document to read alongside this one.

## The problem

In the user's words (2026-10-10): *"plan the mcp to work with mac"*, *"i want
cross modularity"*, and the bar for done: *"best one that may take time to build
for us right now but genuinely just makes users experience the most convenient
just connect mcp and it works out of box on any os"*. UI mode: *"Full parity
now"*. Execution: *"i will execute it on my mac it has pt and all"*.

Required capabilities:

(a) The token and mailbox state directory agrees between Python and the
extension on every OS.
(b) The file channel works on macOS and Linux with the extension already in
Releases.
(c) Clipboard and output folders work on every OS and under GUI clients.
(d) UI mode (open, navigate, fill, capture) works on macOS as it does on Windows.
(e) OS-specific code is modular: one interface per concern, one backend per OS.
(f) A new user needs no manual configuration beyond installing the `.pts` and
granting the macOS permissions, and is told exactly what to do when something
is missing.

## The approach in one paragraph

A new `infrastructure/platform/` package becomes the single home of OS facts:
state dir, clipboard, output root and host info. The server finds the mailbox by
following the extension's heartbeat across candidate directories, so the
released `.pts` works on a Mac unchanged, while `main.js` is fixed for future
builds. UI mode is split into an OS-agnostic presenter and a small
`WindowBackend` protocol. Widget lookup becomes data (locators with an
identifier rule and a fallback rule). The Windows Win32/UIA code moves behind the
protocol untouched. A macOS backend built on pyobjc (Accessibility for the tree
and actions, Core Graphics for windows and clicks, ScreenCaptureKit for capture)
plugs in beside it. It is developed against AX trees recorded from the real PT.
`pt-mcp doctor` and a `platform` block in `pt_bridge_status` close the loop for
users.

## Locked decisions

| Decision | Value |
|---|---|
| Target | Connect the MCP and it works on Windows, macOS and Linux. Headless parity on all three. UI mode at full parity on Windows and macOS on this branch. Linux UI gated (PHASE-08) |
| Execution machine | The user's Mac with PT runs every phase. The Windows machine wrote this plan and is used only for the Windows UI regression check (`FUTURE_WORK.md` §2) |
| Branch | `feat/cross-platform`, from `main` @ `bcb2ef3`. Plan docs are committed on it and removed before any upstream PR. Upstream PR only with the user's OK |
| Modularity | One Protocol per concern. Backends in-package, chosen by `sys.platform` at runtime. `PT_MCP_UI_BACKEND` override. No entry-point plugins (no user benefit) |
| Install | Platform dependencies as environment markers in core `dependencies`. `[ui]` kept as an empty alias |
| Extension compatibility | The released V5.2 `.pts` must keep working on every OS (C5). `main.js` fixed for the next build |
| Stack | Python ≥ 3.11, FastMCP (unchanged), pyobjc on macOS, comtypes on Windows |
| macOS floor | UI capture through SCK on 14+. CGWindowListCreateImage on 12.3–13, best effort. Headless wherever PT 9.0 and Python 3.11 run |
| Language | English in everything written to the repo. Replies in the user's language |
| Commits | The user's identity, no AI attribution lines (user rule) |

## Documents

| File | Contents |
|---|---|
| **ARCHITECTURE.md** | System diagram, data flow, components, technology choices, non-goals |
| **INTERFACES.md** | Platform layer, UI backend protocol, locators, external interfaces, pairing contract, diagnostics, fixture format |
| **CONSTRAINTS.md** | Integrity constraints C1–C11, technical constraints, performance targets, scope, machine limits |
| **EVALUATION.md** | Offline, fixture, pairing, smoke, UI, out-of-the-box and Windows-regression checks; what we will not claim |
| **PREREQUISITES.md** | Software, packages, accounts, macOS permissions, hard-won notes |

## Phases

Dependency-ordered. After PHASE-00, PHASE-01 and PHASE-03 can be built in
parallel. PHASE-02 and PHASE-04 can then run in parallel (they touch different
files).

| Phase | Title | Depends on | Key output |
|---|---|---|---|
| [00](phases/PHASE-00.md) | Mac bring-up and live spike | — | macOS baseline, answers to SYNTHESIS §9, AX fixtures, smoke harness in the repo |
| [01](phases/PHASE-01.md) | Platform layer | 00 | `infrastructure/platform/`, clipboard and output root on every OS, CI on macOS |
| [02](phases/PHASE-02.md) | Pairing on every OS | 00, 01 | Both channels on the Mac with V5.2, fixed `main.js`, headless smoke green |
| [03](phases/PHASE-03.md) | UI backend seam | 00 | `WindowBackend`, locators, Windows backend moved, null backend |
| [04](phases/PHASE-04.md) | macOS backend: windows, capture, permissions | 01, 03 | `pt_ui_capture` on the Mac, automatic UI dependencies |
| [05](phases/PHASE-05.md) | macOS backend: navigation and open-by-click | 04 | `pt_ui_open` parity on the Mac |
| [06](phases/PHASE-06.md) | Out of the box | 02, 05 | `pt-mcp doctor`, onboarding, `platform` block |
| [07](phases/PHASE-07.md) | Docs, skill and end-to-end acceptance | 01–06 | Per-OS docs, tool API snapshot, fresh-install run |
| [08](phases/PHASE-08.md) | **Bonus** — Linux UI backend | **00–07 all complete** | Gated: do not start until the core works end to end and a Linux PT machine exists |

## Validation fixtures

| Case | Data | Expected | What it tests |
|---|---|---|---|
| File channel, window closed, **released V5.2** | fixture topology, Control Center closed | `pt_query_topology` answers through the mailbox | **The case that separates the chosen design from "just fix main.js".** It must pass with no rebuilt `.pts` (C5) |
| PC1 › Desktop › Command Prompt | recorded AX fixture + live | app opened, PNG non-blank | navigation by locator, applet detection |
| PC1 › Email (nested Configure Mail) | fixture + live | the close loop leaves no applet open | the `applet_close` locator and loop |
| R1 › CLI with `pt_cli(show=True)` | live | the CLI tab shown, output returned | console scroll locator; headless + GUI together |
| Covered dialog capture | live | correct pixels, not the covering window | the SCK route, pixel units |
| Permissions revoked | live | remedy text naming the client app; no prompt on headless tools | C3, C7 |
| Fresh install | `EVALUATION.md` §6 | ≤ 4 user actions | the user's actual requirement |

## Reading rule

Do not read every document each session. Start with `CLAUDE.md` and
`FUTURE_WORK.md` §0, then this index, then the **current phase file**, then only
the sections of ARCHITECTURE, INTERFACES, CONSTRAINTS and EVALUATION that the
phase cites. Reach `RESEARCH/` through `RESEARCH/INDEX.md`.

## Source of truth

```
repository        what actually exists
PLAN/             what should exist
PREVIOUS_WORK.md  what is done
ISSUES.md         what is broken
FUTURE_WORK.md    what is next
RESEARCH/         what was learned externally
```

When the repository and PLAN disagree, the repository wins and `ISSUES.md`
records the gap.
