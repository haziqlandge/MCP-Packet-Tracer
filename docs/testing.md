# Testing

The offline suite covers domain/application logic, the MCP tool contract,
platform paths and probes, bridge security, and UI backends.

```bash
pip install -e ".[test]"
python -m pytest -q
```

Run it on each supported OS; offline checks do not establish live Packet Tracer
behavior.

## What's covered

- **IP planning** — LAN/link subnet assignment, masks.
- **Plan validation** — typed error codes, warnings.
- **Auto-fixer** — cable correction, port reassignment, model upgrades.
- **Plan explanation** & **estimation**.
- **Generators** — PTBuilder script and IOS CLI config generation.
- **ACL** — standard/extended/named CLI generation.
- **Full build** — end-to-end pipeline integration.
- **Runtime regressions** — guards against known issues.

## Live (manual) testing

The bridge/PT-facing tools (`pt_live_deploy`, `pt_add_*`, `pt_delete_*`,
`pt_apply_acl`, …) require a running Packet Tracer with the
[live bridge](live-deploy.md) connected; they're validated manually against PT.
A full QA pass of the first 46 tools was performed on **PT 9.0.0**. The four
inspection tools added later — `pt_audit_security`, `pt_inspect_ports`,
`pt_read_vlans` and `pt_device_power` — were each verified individually against
**PT 9.0.0.0810** when they landed, against a live 2911 and 2960-24TT.

The reproducible call lists are in `tests/live/`: `setup.json` builds the fixture,
`headless.json` exercises API tools, and `ui.json` opens and captures panels. Run
one PT and one bridge at a time, and save the existing topology before using setup
on an empty canvas:

```bash
python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/headless.json
python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/ui.json
```

The harness uses the current checkout; reconnect a client's server after source
changes. Read results as well as exceptions. macOS UI checks require grants for
the harness launcher. The fixture recorder is
`python -m src.packet_tracer_mcp.devtools.macos_probe ax --pid <PT_PID> --title PC1
--out /tmp/pc1-ax.json`; record real windows and keep AX frames in points and
captures in pixels.

!!! note "Unit tests don't start the MCP server"
    They exercise domain/application code directly. To verify the server actually
    boots (and that dependencies are compatible), run
    `python -m packet_tracer_mcp --stdio` — it should start without errors.
