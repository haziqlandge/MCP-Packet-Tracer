# tests/live — call lists for a running Packet Tracer

These lists drive `devtools/live_smoke.py` against a real Packet Tracer with the
MCP Control Center extension loaded. **pytest never collects them**: this
directory holds no `test_*.py`, only JSON call lists.

Each file is a JSON list of `{"tool": "<name>", ...arguments}`. The harness
registers the tools of this checkout (not the client's running server) and runs
the calls in order, printing `===== <tool> <args>` before each result.

| File | What it does | Needs |
|---|---|---|
| `setup.json` | Builds the fixture topology: R1 (2911), SW1 (2960-24TT), PC1 (PC-PT), SRV1 (Server-PT) on 192.168.10.0/24 | An empty canvas (save the current one first) |
| `headless.json` | The headless smoke list (same calls as the Windows smoke) | The fixture topology |
| `ui.json` | UI mode: show and capture R1 CLI, PC1 Command Prompt, IP Configuration and Web Browser, SRV1 DHCP | The fixture topology; UI backend for the OS |

Run from the repo root, one PT and one bridge at a time:

```bash
python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/setup.json
python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/headless.json | grep -E "^=====|Traceback|NameError|PT_ERROR"
```

A call passes when its output has no `Traceback`, `NameError`, `PT_ERROR` or
`EXCEPTION`. Read the result text too: a reply can be well-formed and still
report a failure.
