# PHASE-02 — Pairing on every OS

## Objective

Both channels pair on macOS (and, by construction, Linux) with the **released
V5.2 `.pts`**, with no rebuild. The tracked `main.js` is fixed so a future build
needs no legacy fallback. The headless smoke list passes on the Mac.

## Why it exists

This is requirement (d) in `RESEARCH/SYNTHESIS.md` §1. Without the file channel,
PT on a Mac only works while the Control Center window stays open: closing it
kills every command (`file_bridge.py` docstring). Fixing only `main.js` would
help nobody until a new `.pts` reaches Releases, and nobody knows yet how to
build one on a Mac (`RESEARCH/topics/pt-on-macos.md` §3). That is why the server
side must adapt to the extension already in the field (C5). PHASE-06's
diagnostics and PHASE-07's out-of-the-box test both assume both channels work.

## Dependencies

- PHASE-00: which directory V5.2 polls, whether it creates missing parents, the
  `getUserFolder()` value, and whether a `.pts` can be built.
- PHASE-01: `paths.mailbox_candidates()` and `state_dir()`.

## Files to create

```
tests/test_file_bridge_discovery.py   heartbeat-driven mailbox choice
tests/test_main_js_paths.py           runs main.js path functions under node with a stub ipc
tests/js/main_paths_harness.js        loads main.js, stubs ipc/fm, prints JSON results
```

## Files to modify

- `infrastructure/execution/file_bridge.py`: `bridge_dir()` and `FileBridge`
  choose among `mailbox_candidates()` (`INTERFACES.md` §5). `pt_alive()`
  reports which candidate is alive.
- `infrastructure/execution/` server start (where the HTTP bridge starts):
  pre-create the legacy directory on macOS and Linux **only if PHASE-00 showed
  V5.2 needs it**.
- `adapters/mcp/bridge_context.py`: the channel pick keeps its logic; it reads
  aliveness through the new `FileBridge`.
- `EXTENSION/script-engine/main.js`: `mcpTokenCandidates()` and
  `mcpBridgeDir()` per `INTERFACES.md` §5.
- `EXTENSION/README.md`, `EXTENSION/script-engine/README.md`,
  `infrastructure/execution/README.md`, `infrastructure/README.md`: replace
  "`%LOCALAPPDATA%`" with the per-OS table (one sentence plus a link to
  `docs/live-deploy.md`, which PHASE-07 rewrites).

## Implementation details

### Server side: follow the heartbeat

1. `FileBridge.__init__(directory=None)`. An explicit directory (tests,
   config) wins as today. Otherwise the instance holds the candidate list.
2. `_active_dir()`: stat `alive.txt` in each candidate and pick the freshest
   one younger than `HEARTBEAT_FRESH_S`. With none fresh, use candidate 1.
   Re-evaluate on every `send` / `send_and_wait`. The cost is a few `stat`
   calls, which is cheap next to PT's 250 ms tick.
3. Keep `_write_atomic` byte-exact (binary write + `os.replace`). Its comment
   explains why.
4. Directories are created with mode 0700 (`file_bridge.py` already does this).
   **Never create the legacy `~/AppData` tree on Windows**, where candidate 1
   is already that directory.

### Extension side: fixed `main.js`

1. A pure helper, `mcpHomeFromUserFolder(uf)`, implements the regex list in
   `INTERFACES.md` §5, with the parent folder as fallback.
2. `mcpTokenCandidates()` orders the candidates by home shape.
3. `mcpBridgeDir()` returns the directory of the first candidate whose
   `bridge_token` exists. Otherwise it returns the OS default.
   `fileBridgeTick()` caches `_fileBridgeDir` only once a token was found.
4. **This is compiled `.pts` code, so multi-line JS is fine.** The AGENTS
   single-line rule is for pasted snippets.
5. Building the `.pts`: follow PHASE-00's finding. If no build route exists on
   the Mac, the fix ships as source. ISSUES X3 stays open for the build, and the
   server-side discovery carries users meanwhile.

### Testing `main.js` without PT

`tests/js/main_paths_harness.js` defines stub `ipc` and `systemFileManager`
objects with an in-memory file set, evaluates `main.js` with Node's
`vm.runInNewContext`, and prints the results of `mcpTokenCandidates()` and
`mcpBridgeDir()` as JSON. `tests/test_main_js_paths.py` runs it with
`subprocess` when `shutil.which("node")` exists, and skips otherwise. **Write
this test first. It must fail on the current `main.js` for a macOS user folder
with the token under `.local/state` (AGENTS rule 5).** If `main.js` refers to
globals at load time that the stub lacks, add them to the stub. Do not change
`main.js` to suit the test.

### The open question this phase must answer

Can a `.pts` carrying the fixed `main.js` be produced on the Mac? A "no" is a
finding. Record it, keep X3 open, and rely on the server-side discovery.

## Inputs / outputs

- In: PHASE-00 pairing facts; PHASE-01 paths.
- Out: both channels working with V5.2 on macOS; fixed `main.js` source; headless
  smoke results.

## Relevant interfaces

`INTERFACES.md` §5 (pairing contract), §4 (external interfaces).

## Relevant research

`RESEARCH/topics/pt-on-macos.md` §1 (user folder), §3 (mailbox analysis).

## Tests

- Discovery: canonical fresh → canonical; only legacy fresh → legacy; both stale
  → canonical; both fresh → the fresher one. **The one C5 rests on.**
- An explicit directory still wins (existing `tests/test_file_bridge.py` passes
  unchanged).
- Windows: one candidate, and no legacy directory is ever created.
- `main.js` under node: a macOS user folder with the token in `.local/state` →
  that bridge directory. A Windows user folder → `AppData/Local`. Linux `~/pt` →
  `.local/state`. A user folder nested under `~/Documents` → still home. No token
  anywhere → the OS default, not cached.

## Acceptance criteria

- [ ] New tests pass; `test_main_js_paths.py` failed before the `main.js` change (record the failing output in PREVIOUS_WORK)
- [ ] Live, Mac, V5.2: HTTP pairs and `pt_bridge_status` shows the token fingerprint (`EVALUATION.md` §3)
- [ ] Live, Mac, V5.2, Control Center closed: `pt_query_topology` answers through the mailbox; `mailbox.legacy` reported correctly
- [ ] Live, Mac: both start orders pair within 10 s (`EVALUATION.md` §3)
- [ ] Live, Mac: `tests/live/headless.json` passes every call (`EVALUATION.md` §4)
- [ ] `.pts` build route recorded (built and tested, or "none found" with ISSUES X3 kept open)

## Known failure conditions

- Mailbox "alive" flips between candidates → two PTs running, or a stale
  `alive.txt` from an old session. Freshness is by mtime; delete stale
  heartbeats on server start only if older than `HEARTBEAT_FRESH_S` × 10.
- The node test cannot load `main.js` → it needs more PT globals (`window`,
  `builder`, `ipc.appWindow`). Extend the stub.
- `req_*.js` files pile up in the canonical directory while PT polls the legacy
  one → `_active_dir()` was evaluated once and cached. Re-evaluate on every send.
- CR/LF SyntaxError inside PT → a text-mode write slipped in. Keep `write_bytes`.
