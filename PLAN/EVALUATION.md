# EVALUATION

How we know the server works on every OS. Each phase's acceptance criteria point
to a section here. The full end-to-end run is PHASE-07.

## Guiding principle

The strongest evidence is **a fresh user on a Mac connecting the MCP and using
it**, with nothing configured by hand. Next comes the live smoke harness against
the real PT. Offline tests are supporting evidence. They are strong for the
macOS backend only because they run on AX trees recorded from the real PT,
never on invented ones (`CONSTRAINTS.md` C8).

## 1. Offline suite on every OS (all phases)

| Metric | Target | Basis |
|---|---|---|
| `python -m pytest -q` on the Mac | 0 failed. Passed ≥ the macOS baseline in `CLAUDE.md` §5 | Recorded in PHASE-00 |
| CI matrix | windows-latest, ubuntu-latest, macos-latest × Python 3.11 and 3.13 all green | `.github/workflows/tests.yml` after PHASE-01 |
| Import safety | every module under `src/` imports with each OS faked | C2 |
| OS checks | no `sys.platform` / `os.name` outside the two allowed packages | C1 |

## 2. macOS backend against recorded fixtures (PHASE-04, PHASE-05)

| Metric | Target | Basis |
|---|---|---|
| Fixture conversion | every fixture converts to `UiElement`s with no exception; role counts match the dump | `INTERFACES.md` §7 |
| Locator hits | every locator in `INTERFACES.md` §3 finds exactly one element in the fixture where the live presenter needs it | PHASE-00 recordings |
| Capture normalisation | padded rows and each bitmap-info layout give byte-exact BGRA on synthetic images | `RESEARCH/topics/macos-ui-automation.md` §3 |

A locator that cannot be satisfied from the fixtures is a finding. Report it.
Do not loosen the locator until it matches something.

## 3. Pairing (PHASE-02, live on the Mac)

| Check | Target |
|---|---|
| HTTP channel with released V5.2 `.pts` | `pt_bridge_status` connected, token fingerprint matches |
| File channel with V5.2, Control Center window closed | `pt_query_topology` answers through the mailbox. `platform.mailbox.alive` true |
| File channel with the fixed `main.js` (if a `.pts` can be built) | same, `legacy: false` |
| Restart order | PT before server, and server before PT: both pair within 10 s |

## 4. Headless smoke on the Mac (PHASE-02)

`python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/headless.json`
against the fixture topology (PHASE-00). Target: every call returns without
`Traceback`, `NameError` or `PT_ERROR`. The Windows reference is 28/28 (live
smoke #2, 2026-10-10). The Mac list is the same list.

## 5. UI mode on the Mac (PHASE-05)

`tests/live/ui.json`: open R1 › CLI, PC1 › Desktop › Command Prompt, PC1 ›
Desktop › IP Configuration, SRV1 › Services › DHCP, and PC1 › Web Browser with a
URL typed and Go pressed. Capture each one. Targets: every step reports `ok`,
every PNG is non-blank (`png.looks_blank` false) with the dialog title visible,
and the timings in `CONSTRAINTS.md` hold. A covered window is captured correctly
(cover it with another app first).

## 6. Out-of-the-box acceptance (PHASE-07)

On the Mac, with the state dir and virtualenv deleted, PT running with V5.2
installed, and the MCP not configured:

1. Follow only the README's macOS section.
2. Count the user actions. Target ≤ 4: install uv, add the MCP to the client,
   install the `.pts` (skipped if already installed), and grant two permissions
   on first UI use.
3. `pt-mcp doctor --ui` is all green.
4. Ask the client to build the fixture topology and capture PC1's Command
   Prompt. It works with no manual config edits.

## 7. Windows regression (Windows machine, after PHASE-03)

On the Windows machine: offline suite ≥ the Windows baseline, and live smoke
#2 (headless + UI mode, show and capture) 28/28 as on 2026-10-10. Until then
the Windows UI is "refactored, unverified live" (C8). It is a brief in
`FUTURE_WORK.md` §2, and its gap is ISSUES X5.

## 8. Test suite structure

| Level | Scope | Runs in |
|---|---|---|
| Unit | platform functions, clipboard selection, output root, locators, AX conversion, capture normalisation, permission messages | every OS, CI |
| Contract | presenter against a `FakeBackend`; the same flow tests run for every backend name | every OS, CI |
| Fixture | macOS backend logic on `tests/fixtures/macos/*.json` | every OS, CI |
| JS | `main.js` path functions under `node` with a stubbed `ipc` | CI (node preinstalled); skipped locally without node |
| Live | `devtools/live_smoke.py` + `tests/live/*.json` | the Mac with PT; Windows for §7. Never CI |

## 9. What we will not claim

- That UI mode works on Linux, before PHASE-08 runs on a Linux machine.
- That Windows UI mode is unchanged, before §7 has run on Windows.
- That a PT version other than the one recorded in PHASE-00 works.
- That the macOS fallback capture routes work on macOS versions this Mac does
  not run.
- "Zero setup". The `.pts` install and the two macOS grants are user actions,
  and the docs say so.
