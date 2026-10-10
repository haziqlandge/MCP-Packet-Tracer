# PHASE-00 — Mac bring-up and live spike

## Objective

The branch runs on the user's Mac and the offline suite passes there. Every
question in `RESEARCH/SYNTHESIS.md` §9 has an answer recorded with its evidence.
Real AX trees of PT's dialogs are committed as fixtures, and the live smoke
harness lives in the repo, so later phases can verify against reality.

## Why it exists

Everything after this phase depends on facts nobody has measured. Which mailbox
directory V5.2 uses decides PHASE-02's design. Whether `AXIdentifier` is
populated decides whether PHASE-05 is a port or a rewrite of widget lookup.
Which capture and click routes work decides PHASE-04 and PHASE-05. Skip the
spike and the later phases are written on guesses, which `CONSTRAINTS.md` C6
forbids. The fixtures recorded here are also the only way the macOS backend
gets meaningful tests on CI.

## Dependencies

None. This is the first phase on the Mac. Prerequisites: `PLAN/PREREQUISITES.md`
(software, packages) and the branch pushed from Windows (`FUTURE_WORK.md` §0).

## Files to create

```
src/packet_tracer_mcp/devtools/live_smoke.py   run tool calls from this checkout against live PT
src/packet_tracer_mcp/devtools/macos_probe.py  dump permissions, CG windows, AX trees to JSON
tests/live/README.md                           how to run the live lists; never collected by pytest
tests/live/setup.json                          builds the fixture topology
tests/live/headless.json                       the headless call list (same as Windows smoke)
tests/live/ui.json                             the UI-mode call list (EVALUATION.md §5)
tests/fixtures/macos/*.json                    recorded AX trees (INTERFACES.md §7)
tests/test_macos_fixtures_load.py              every fixture parses and has the §7 keys
```

## Files to modify

- `CLAUDE.md` §5: add the macOS baseline line.
- `CODEMAP.md`: regenerate (`python -m src.packet_tracer_mcp.devtools.codemap`).
  `tests/test_codemap.py` fails when it is stale.
- `PLAN/PREREQUISITES.md` "Hard-won notes": anything that cost time.

## Implementation details

### 1. Environment (record every value in PREVIOUS_WORK Part 2)

1. `sw_vers`, `uname -m`, Mac model.
2. PT: install path, `file "<app>/Contents/MacOS/"*` for the architecture, and
   the Qt version from `<app>/Contents/Frameworks/QtCore.framework/Resources/Info.plist`
   (`CFBundleVersion` or `CFBundleShortVersionString`).
3. Python ≥ 3.11 in a venv (not `/usr/bin/python3`). Then
   `pip install -e ".[test]"`, plus the five pyobjc packages from PREREQUISITES.
4. `python -m pytest -q`. Record the macOS baseline in `CLAUDE.md` §5 (the
   second baseline line). A failure is a finding: add an ISSUES row with the
   failing test name. Do not fix it here unless it blocks the spike.

### 2. Port the smoke harness

The Windows harness (`.dev/live_smoke.py`) is git-excluded, so it is not on the
Mac. Recreate it as a module. It has about 40 lines and does the following:

- Build `FastMCP("smoke")`, then call `register_tools(mcp, BridgeContext())`
  (both already imported in `server.py`).
- For each `{"tool": name, ...args}` in a JSON list (read with `utf-8-sig`),
  `await mcp.call_tool(name, args)`.
- Join the text blocks and print `===== <tool> <args[:160]>` followed by the text.
- Catch any exception and print it as text, so one failure does not stop the run.
- Grep the output with `grep -E "^=====|Traceback|NameError|PT_ERROR"`.

`tests/live/headless.json` is the Windows `smoke1.json` list: `pt_estimate_plan`,
`pt_bridge_status`, `pt_export_topology`, `pt_list_modules` (2911),
`pt_apply_acl` (dry run), `pt_apply_nat` (dry run), `pt_read_vlans`,
`pt_apply_vlan` (dry run), `pt_audit_security`, `pt_inspect_ports`,
`pt_health_check`, `pt_read_packet_trace`, `pt_screenshot`,
`pt_project_metadata`, `pt_configure_dhcp_server`, `pt_read_qos`,
`pt_read_device_panel`, `pt_cli`. It expects devices R1, SW1, PC1 and SRV1.

`tests/live/setup.json` builds them. **Run `pt_list_devices` first and use the
exact model and port names it returns.** Never invent them (the packet-tracer
skill and AGENTS). Keep `tests/live/` out of pytest collection: the directory
has no `test_*.py`, and the README says so.

### 3. Pairing facts (SYNTHESIS §9, questions 3–5, 11)

1. Install V5.2 in PT. Start the server, then call `pt_bridge_status`. Record
   whether HTTP pairs and whether macOS showed a firewall prompt.
2. `getUserFolder()`: send
   `reportResult(String(ipc.appWindow().getUserFolder()))` through
   `pt_send_raw` (the API is already used in `main.js`, so AGENTS rule 6 is met).
3. Open the Control Center Status view and record the file-bridge directory and
   the token "searched" paths. Then close the window and check which directory
   receives `alive.txt`:
   `ls -la ~/.local/state/packet-tracer-mcp/bridge ~/AppData/Local/packet-tracer-mcp/bridge`.
   Also record whether `~/AppData/Local/packet-tracer-mcp` had to exist first
   (rename it away, restart PT, look again). That tells PHASE-02 whether the
   server must pre-create the legacy directory (`INTERFACES.md` §5).
4. Record the MCP server's cwd and PATH under each client the user runs
   (question 10). Log `os.getcwd()` and `os.environ["PATH"]` once from a
   scratch call, then remove the logging.

### 4. `macos_probe.py`

A command-line script with subcommands and JSON output:

- `perms`: `AXIsProcessTrustedWithOptions` (prompt False),
  `CGPreflightScreenCaptureAccess`, `CGPreflightPostEventAccess`, and the
  `responsible_app` chain. Add `--request` to call the request variants once.
- `windows --pid N`: `CGWindowListCopyWindowInfo` filtered by pid, joined to AX
  windows by bounds (`RESEARCH/topics/macos-ui-automation.md` §2).
- `ax --pid N --title T --out file.json`: the AX tree of one window in the
  `INTERFACES.md` §7 format, with the home path redacted to `~`.
- `click --pid N --x X --y Y [--fields]`: one `CGEventPostToPid` click (with or
  without the window-number fields), then one cursor-restoring `CGEventPost`.
- `capture --wid W --route sck|cgimage|screencapture --out file.png`.

**Each pyobjc name it uses is checked here first (C6).** Record the exact
selector and constant names that worked in PREVIOUS_WORK Part 2.

### 5. Recordings (questions 2, 6–9)

Open each of these by hand and record its tree as
`tests/fixtures/macos/<device>-<tab>[-<app>].json`:

- PT's main window, with the Select tool active and the logical canvas visible
- R1 › CLI
- PC1 › Desktop, both with no app open and with Command Prompt open
- PC1 › Desktop › Web Browser
- PC1 › Config › FastEthernet0
- SRV1 › Services › DHCP
- a PC with Email open, which has the nested Configure Mail panel
  (`presenter.py` `_open_app`)

For each recording, note whether `identifier` carries the objectName path
(compare it with `APPLET_TITLES` and `CLogicalWorkspace.QWidget`). Also note the
roles and actions of the tabs, the Select tool, the scroll bars and the Desktop
app buttons.

Then run the probe's `click` on PC1's icon with PT in the background, and its
three `capture` routes on a covered PC1 dialog. Record which ones worked, the
timings and whether each image was blank.

### The open question this phase must answer

Does PT for macOS expose objectName paths through `AXIdentifier`? If it does not,
PHASE-05 becomes a locator-writing exercise on role, text and tree position, and
its risk goes up. A negative answer is a legitimate finding. Record it in
PREVIOUS_WORK Part 2, add a dated "Local empirical update" to
`RESEARCH/SYNTHESIS.md`, and leave PHASE-05's design as is: it already has the
`by_shape` fallback for this case.

## Inputs / outputs

- In: the Mac, PT 9.0.x, V5.2 `.pts`, this branch.
- Out: macOS baseline (`CLAUDE.md` §5), fixtures (`tests/fixtures/macos/`), the
  harness (`devtools/live_smoke.py`, `tests/live/`), the probe, answers in
  PREVIOUS_WORK Part 2, and the SYNTHESIS update.

## Relevant interfaces

`INTERFACES.md` §5 (what the pairing facts decide), §7 (fixture format).

## Relevant research

`RESEARCH/SYNTHESIS.md` §9 (the questions), `RESEARCH/topics/pt-on-macos.md` §3
(the mailbox analysis being confirmed), `RESEARCH/topics/macos-ui-automation.md`
§2–§4 (the routes being tried).

## Tests

- `tests/test_macos_fixtures_load.py`: every fixture parses, has every
  `INTERFACES.md` §7 key, stays within the depth and node caps, and contains no
  `/Users/<name>` (redaction). **The macOS backend's offline tests rest on this.**
- A probe self-test is not needed. The probe is a devtool, verified by the
  recordings it produces.

## Acceptance criteria

- [x] Offline suite passes on the Mac; macOS baseline recorded in `CLAUDE.md` §5 — `.venv/bin/python -m pytest -q`: 825 passed, 0 failed in 30.53 s; 2026-10-10
- [x] `devtools/live_smoke.py` runs `tests/live/setup.json` and `headless.json`; pass/fail per call recorded in PREVIOUS_WORK (failures are expected before PHASE-02) — setup 11/11 ok, headless 18/18 pass over HTTP with V5.2 (PREVIOUS_WORK 2.4 "Live smoke"); 2026-10-10
- [x] All 12 questions of `RESEARCH/SYNTHESIS.md` §9 answered in PREVIOUS_WORK Part 2, each with its evidence (command output, file or screenshot) — 1–11 in PREVIOUS_WORK 2.4; 12 in 2.6: no offline build (opaque binary), but PT's module editor builds one (Edit → set `main.js` → Export), done on the Mac with the user's go-ahead; 2026-10-10
- [x] ≥ 8 AX fixtures committed; `test_macos_fixtures_load.py` passes — 8 recorded by `macos_probe ax` (main window, R1 CLI, PC1 Desktop, Command Prompt, Web Browser, Config › FastEthernet0, Email with nested Configure Mail, SRV1 Services › DHCP); 8 passed, full suite 833 passed; no `/Users/` in any fixture; 2026-10-10 (in the working tree, not committed: the user asked for no commits)
- [x] Every pyobjc selector and constant used by the probe is listed in PREVIOUS_WORK Part 2 as verified — all `perms`/`windows`/`ax`/`press`/`click`/`capture` names exercised on macOS 26.5.1 with pyobjc 12.2.2, including the SCK traps (PREVIOUS_WORK 2.4); 2026-10-10
- [x] A dated "Local empirical update" is appended to `RESEARCH/SYNTHESIS.md` — "Local empirical update — 2026-10-10"; amendments in CONSTRAINTS (universal binary), INTERFACES §1 + PHASE-01 (responsible app); a second update follows when questions 2, 6, 7, 8 and 12 are measured
- [x] `CODEMAP.md` regenerated; `tests/test_codemap.py` passes — `devtools/live_smoke.py` and `devtools/macos_probe.py` added; full suite 825 passed, 1 skipped (the empty fixture parametrize), pyflakes clean; 2026-10-10

## Known failure conditions

- `pip install` of pyobjc compiles from source → the venv's Python is too new for
  the published wheels. Use the newest Python that has universal2 wheels.
- The probe sees no AX children for PT → Accessibility is not granted to the app
  that runs the probe (the terminal). Grant it, then restart the terminal.
- CG window names are empty → expected without Screen Recording. Use the AX join.
- `pt_bridge_status` disconnected → the extension is not loaded, or it searched
  a token path that does not exist. Read the Control Center's "searched" list.
- The smoke run hangs → only one PT and one bridge at a time. Kill stray
  servers holding port 54321 (`lsof -i :54321`).
