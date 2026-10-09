# DATA

Where everything outside the source tree lives, which copy is authoritative, and
what is cheap to regenerate. Gitignored: `projects/`, `/screenshots/`, `data/`,
`EXTENSION/script-engine/*.js` except `main.js`, `.dev/`, `PLAN.md`,
`STATUS.md` (see `.gitignore`).

## 1. Path and environment traps

- The state directory differs per OS, and so does what the extension expects:
  `PLAN/INTERFACES.md` §5 is the one table. On a Mac today the extension looks
  in `~/AppData/Local/...` for the mailbox (ISSUES X1).
- Tests must never touch the real state directory. Set `PT_MCP_BRIDGE_TOKEN`
  and use the `isolated` fixture (`tests/test_bridge_token.py`).
- The Windows-only harness in `.dev/` (git-excluded) does not exist on the Mac.
  Its replacement is `devtools/live_smoke.py` + `tests/live/` (PHASE-00).

## 2. Sources

| Record | Name | On disk | Contents |
|---|---|---|---|
| Extension build | `V5.2.pts` | upstream GitHub Releases; installed copy inside PT's user folder | The compiled webview + script engine. **Authoritative for what runs in PT** |
| Extension source | `EXTENSION/` | git | `main.js`, the webview. Not necessarily equal to V5.2 (PREVIOUS_WORK 2.2) |
| PTBuilder reference files | `EXTENSION/script-engine/*.js` | gitignored; from kimmknight/PTBuilder | Needed only to build a `.pts` (ISSUES X3) |

## 3. Derived data

| Data | Where | Authoritative? |
|---|---|---|
| AX recordings | `tests/fixtures/macos/*.json` (git) | Yes. Recorded by `devtools/macos_probe.py`; re-record rather than edit |
| Tool API snapshot | `tests/fixtures/tool_api.json` (git) | Yes. Regenerate only on purpose (`UPDATE_TOOL_API=1`) |
| CODEMAP | `CODEMAP.md` (git) | Generated: `python -m src.packet_tracer_mcp.devtools.codemap` |

## 4. Runtime state (per machine, never in git)

| State | Windows | macOS / Linux |
|---|---|---|
| Token | `%LOCALAPPDATA%\packet-tracer-mcp\bridge_token` | `~/.local/state/packet-tracer-mcp/bridge_token` |
| Mailbox | `<state>\bridge\` | `<state>/bridge/`, or the legacy `~/AppData/Local/packet-tracer-mcp/bridge/` while V5.2 is installed (X1) |
| UI mode setting | under the state dir (`shared/ui_mode` store) | same |
| Screenshots, exports | `<output_root>/screenshots`, `<output_root>/projects` | same; `output_root` from PHASE-01 |

## 5. Irreplaceable versus regenerable

| Irreplaceable | Regenerable (with the command) |
|---|---|
| The user's saved `.pkt` topologies (never overwrite without `pt_query_topology` first) | Token (deleted → recreated on server start; the extension re-reads it) |
| AX recordings of a PT version no longer installed | CODEMAP (`python -m src.packet_tracer_mcp.devtools.codemap`) |
| | Smoke screenshots (rerun `devtools/live_smoke.py`) |

## 6. Credentials

`bridge_token`: local shared secret, generated, mode 0600. It is shown only by
fingerprint (`pt_bridge_status`). No other credentials are involved.
