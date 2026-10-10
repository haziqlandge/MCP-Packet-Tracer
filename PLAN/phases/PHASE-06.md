# PHASE-06 — Out of the box

## Objective

A user on any OS can tell in one command what works and what to do about what
doesn't. `pt-mcp doctor` checks the whole chain and prints a ready-made MCP
config. `pt_bridge_status` carries the `platform` block. The first UI-mode use
on macOS walks the user through the two grants, naming the right app. Nothing
needs manual configuration beyond the `.pts` install and those grants.

## Why it exists

The user's bar is "just connect mcp and it works out of box on any os"
(2026-10-10). PHASE-01 to PHASE-05 make it work when everything is in place.
This phase covers the cases where something is not in place: the extension is
not installed, a grant went to the wrong app, the client started the server with
the wrong Python or with cwd `/`, a stale server holds port 54321. Without it,
each of those is a support thread. `EVALUATION.md` §6 (≤ 4 user actions) cannot
pass without it.

## Dependencies

- PHASE-02: mailbox discovery and pairing state to report.
- PHASE-05: the complete `MacBackend` (permission state and availability).
- PHASE-01: `host_info()`, `pt_processes()`, `output_root()`, the clipboard.

## Files to create

```
src/packet_tracer_mcp/infrastructure/platform/doctor.py   checks as data: id, required, run() -> (ok, detail, fix)
tests/test_doctor.py                                      every check with stubbed probes; exit codes; --json shape
tests/test_bridge_status_platform.py                      the platform block: keys, order, ~ paths, no prompts
```

## Files to modify

- `server.py` `main()`: `pt-mcp doctor [...]` (`INTERFACES.md` §6) before the
  transport switch. The existing `--stdio` stays as it is.
- `adapters/mcp/tools/live.py` `pt_bridge_status`: add the `platform` block
  (`INTERFACES.md` §6), computed with preflight calls only (C3).
- `adapters/mcp/device_panel_tools.py` `pt_ui_mode`: on `"ui"`, call
  `available(request=True)` and return the remedy when something is missing. On
  `"status"`, show permissions and `grant_to` on macOS.
- `settings.py` `GUIDE` (served as `pt://guide`): a short "per-OS setup" section.
  `SERVER_INSTRUCTIONS` stays under 2,000 characters (C9). Add at most one
  sentence there, pointing to `pt-mcp doctor`.

## Implementation details

### Checks (in order; `required` unless marked)

1. Python ≥ 3.11 and the package importable.
2. State directory writable (the token file is never read into the output; only
   its fingerprint is shown).
3. Output root resolved, and whether the fallback root is in use.
4. PT running (`pt_processes()`).
5. Extension seen: a fresh heartbeat in any mailbox candidate **or** an HTTP
   poll within 10 s. When the server is not running, only the heartbeat can be
   seen. Say so in `detail`.
6. Port 54321 free, or held by this server. Port held by another process → the
   fix names it (`lsof -i :54321` / `netstat -ano`).
7. Clipboard tool (not required).
8. UI backend available and permissions (required only with `--ui`), with
   `grant_to` from `responsible_app()`.

`--request-permissions` triggers the macOS prompts (allowed by C3).
`--print-config claude-code` prints the `claude mcp add` line.
`--print-config claude-desktop` prints the JSON block for the client's config
file. Both use the absolute `sys.executable` and `-m packet_tracer_mcp.server
--stdio`. Before writing that line, check how `pt-mcp` is wired in
`pyproject.toml` `[project.scripts]` and the README.

### Onboarding flow on macOS

1. The user (or the model) calls `pt_ui_mode("ui")`.
2. `available(request=True)` shows the system prompts once.
3. The reply says what was requested and for which app, and whether a restart of
   that app is needed (the PHASE-04 finding).
4. The mode is saved as `ui` anyway, so after the grant nothing needs repeating.
   Until then, every panel tool works headless and adds the remedy note (C7).

### The open question this phase must answer

Can the extension's presence be detected while the server is down? The
heartbeat only exists while PT runs with the extension loaded. If the
heartbeat is missing but PT is running, the doctor cannot tell "extension not
installed" from "extension broken". Report both possibilities. Do not guess one.

## Inputs / outputs

- In: everything from PHASE-01 to PHASE-05.
- Out: `pt-mcp doctor`, the `platform` block, and the onboarding flow.

## Relevant interfaces

`INTERFACES.md` §6 (diagnostics schema), §2 (`available(request=...)`).

## Relevant research

`RESEARCH/topics/macos-ui-automation.md` §1 (permissions, responsible app);
`RESEARCH/SYNTHESIS.md` §6 (PATH and cwd failure modes).

## Tests

- Each check with stubbed probes: ok, failing (with its fix text), and not
  applicable on this OS.
- Exit code 0 when only optional checks fail; 1 when a required one fails;
  `--ui` makes the UI checks required.
- `--json` matches `INTERFACES.md` §6 exactly (keys and order).
- `pt_bridge_status` platform block: keys in order, `~` paths, and a request API
  that raises is never reached (C3). **This is the guard against surprise
  prompts.**
- `pt_ui_mode("ui")` with permissions missing: the remedy text names the app, and
  the stored mode is `ui`.
- `SERVER_INSTRUCTIONS` and tool description caps still pass (existing tests).

## Acceptance criteria

- [x] Full offline suite passes on the Mac — 1233 passed in 34.72 s, 2026-10-10
- [x] Live platform block and UI preflight report both grants without prompts — macOS 26.5.1; ChatGPT Accessibility false, Screen Recording true; 2026-10-10

- [x] Doctor checks, config rendering and CLI dispatch pass targeted tests — doctor/entrypoint coverage in 96-test targeted run, 2026-10-10
- [x] Status diagnostics and degraded UI onboarding pass targeted tests without permission prompts — 96 passed including C3 and device-panel tests, 2026-10-10

- [ ] All tests pass on the Mac and CI; the suite stays ≥ the macOS baseline
- [ ] Live, Mac: `pt-mcp doctor --ui` is all green with PT + extension + grants; each failure injected by hand (PT closed, `.pts` removed, a grant revoked, port held by `nc -l 54321`) gives the matching fix text — **BLOCKED: Missing ChatGPT Accessibility; live failure injection needs the pending reset approval**
- [ ] Live, Mac: `pt-mcp doctor --print-config claude-code` output, pasted as is, gives a working server in Claude Code — **BLOCKED: Claude Code CLI absent; fresh-client setup approval pending**
- [ ] Live, Mac: from revoked grants, `pt_ui_mode("ui")` brings up the prompts once, and after the grant (plus a restart if PHASE-04 says so) `pt_ui_capture` works with no further steps — **BLOCKED: Prior real revocation declined; new reset approval pending**
- [ ] `pt_bridge_status` shows the `platform` block on the Mac; on Windows CI the block's test passes

## Known failure conditions

- The doctor says the port is busy, but it is this server → compare the PID of
  the listener with the doctor's own server, or mark it "held, PID n" and let the
  user judge.
- The prompt never appears → the request API was already answered for this app,
  so macOS no longer prompts. The remedy must give the System Settings path,
  not only "accept the prompt".
- `grant_to` shows "python3" → `responsible_app` stopped at a non-`.app`
  ancestor. Walk further, and check the chain fixture covers this client.
