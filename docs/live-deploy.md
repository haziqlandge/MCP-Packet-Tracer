# Live Deploy Setup

Live deploy streams commands directly into a **running** Packet Tracer instance,
so devices, cables and configs appear in real time as your AI builds them.

Most desktop clients use **stdio**: the client starts the MCP server, which
starts its internal bridge. The diagram shows the optional streamable-HTTP MCP
transport; if port 39000 is already in use, choose a different MCP port with
`python -m packet_tracer_mcp --port 39001` and point the client to that port.
This does not change the extension's bridge port 54321.

There are **two channels**, and the server picks one per command automatically:

```text
                                   ┌─ HTTP bridge (:54321) ──▶ extension webview ─┐
LLM ──▶ MCP Server (:39000) ──────►┤   (window OPEN)                             ├─▶ PT Script Engine
                                   └─ per-user file mailbox ──▶ Script ──┘
                                       (window CLOSED)               Engine loop
```

- **HTTP** is used while the **MCP Control Center window is open** — the webview
  polls `:54321` and runs each command.
- The **file-bridge** takes over when the **window is closed** but Packet Tracer
  is still open: the Script Engine (which has no `XMLHttpRequest` but *can* read
  files) polls a per-user mailbox
  (`req_*.js` → execute → `res_*.txt`; see the [path table](#per-os-paths)).
  So PT keeps executing with the window minimized or closed.

`_pick_channel()` chooses exactly one per command, so nothing runs twice.

| Port | Service | Purpose |
|------|---------|---------|
| **39000** | MCP server (streamable-http) | Receives tool calls from the LLM/editor |
| **54321** | HTTP bridge | Queues JS commands while the extension window is open |

## Per-OS paths

This is the reference for platform paths. `~` means the current user's home.

| OS | Canonical state directory | Mailbox candidates, in preference order | Default output fallback |
|---|---|---|---|
| Windows | `%LOCALAPPDATA%\packet-tracer-mcp`; if unset, `%APPDATA%\packet-tracer-mcp`, then `~\.packet-tracer-mcp` | `<state>\bridge` | `~\Documents\Packet Tracer MCP` |
| macOS | `~/.local/state/packet-tracer-mcp` | `<state>/bridge`, then `~/AppData/Local/packet-tracer-mcp/bridge` (released V5.2 compatibility) | `~/Documents/Packet Tracer MCP` |
| Linux | `~/.local/state/packet-tracer-mcp` | `<state>/bridge`, then `~/AppData/Local/packet-tracer-mcp/bridge` (released V5.2 compatibility) | `~/packet-tracer-mcp` |

The HTTP token is `<state>/bridge_token`; UI mode is saved in that state directory.
Windows prefers machine-local state; its roaming fallback is retained for
compatibility. `XDG_STATE_HOME` is ignored on macOS and Linux because the extension
cannot read environment variables and must find the same state as the server.

The file bridge selects the freshest `alive.txt` within its freshness window
across these candidates. Without a fresh heartbeat it uses the canonical mailbox.
The released extension creates its compatibility mailbox and heartbeat; the
server discovers that activity without requiring you to edit or relocate V5.2. `pt_bridge_status` reports the selected mailbox and
whether it is a legacy path.

Relative exports and screenshots use the writable working directory unless it
is a filesystem root; otherwise they use the fallback in the table.
`PT_MCP_OUTPUT_DIR` selects the output root, including an absolute destination.
Screenshot tools accept a sanitized single folder name under that root, rather
than an arbitrary absolute path. Project export executors preserve absolute
output directories.

## Install the extension (one-time)

Live deploy uses the project's **own** Packet Tracer extension — the
**MCP Control Center** (a `.pts` script module shipped in this repo's Releases).
You do **not** need any third-party extension.

1. Download the latest extension from
   **[Releases](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest)**
   (the `.pts` file — currently **`V5.2.pts`**).
2. In Packet Tracer: **Extensions → Scripting → Configure PT Script Modules**
3. Click **Add…**, select the downloaded `.pts`, and confirm.

That's it — the module is now registered.

![Installing the MCP Control Center extension in Packet Tracer](https://raw.githubusercontent.com/Mats2208/MCP-Packet-Tracer/main/demo/install-demo.gif)

## Use it (each session)

1. Open **Cisco Packet Tracer 8.2+** (macOS verified on **9.0.1**; older macOS
   builds are unverified)
2. Open **Extensions → MCP BUILDER** — the **MCP Control Center** window appears.
3. It **auto-connects** to the bridge and starts polling. No snippet to paste.

!!! success "No bootstrap needed"
    The MCP Control Center has the polling loop built in (it polls `:54321` every
    500 ms and runs commands via the Script Engine), so it connects on its own. The
    Editor / Terminal / Status / Quick Build tabs let you watch and drive it live.

!!! info "Authentication (nothing to do)"
    Since **v0.6.0** the bridge requires a token unique to your machine — without
    it, any web page you visited while PT was open could inject and run code inside
    Packet Tracer. The MCP server creates the token on first run and the extension
    reads it through PT's Script Engine. Nothing to configure, nothing to paste.

    If the Terminal tab reports that no token was found, start the MCP server once
    and reopen the window. Extensions built before V5.0 cannot authenticate.

!!! tip "Keep it responsive"
    If Packet Tracer feels sluggish while the window is in the background, **minimize**
    it (don't just push it behind PT). See the troubleshooting note below.

## Verify and deploy

Run `pt-mcp doctor` for setup checks and fixes; use `--ui` to require the UI backend
and macOS grants, or `--json` for structured output. It never prompts unless you
pass `--request-permissions`. A terminal run checks its own launcher's grants;
the client's `pt_bridge_status` reports the connected server's state.

```text
pt_bridge_status          # → "Bridge ACTIVE and CONNECTED"
pt_live_deploy(plan_json) # streams the topology into PT
pt_query_topology         # read back what's in PT
pt_export_topology        # full snapshot (positions, per-interface IPs, links)
```

## Troubleshooting

??? question "I don't see `Extensions → MCP BUILDER`"
    The extension isn't registered yet. Repeat the install step
    (**Extensions → Scripting → Configure PT Script Modules → Add…**) and pick the
    `.pts` from [Releases](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest).

??? question "A red error popup appeared (`An error occurred on line N`)"
    A command threw inside the Script Engine. The Control Center's polling loop lives
    in the webview, so it keeps running, but the popup blocks PT's UI until dismissed.
    Click **OK** and re-run. Prefer the validated tools (`pt_add_device`,
    `pt_add_link`, …) which pre-check inputs before sending.

??? question "Packet Tracer becomes very slow when the window is in the background"
    A QtWebEngine compositing limitation: when the webview is behind PT but not
    minimized, Chromium keeps rendering and competes for the GPU. **Minimize** the
    MCP Control Center window to stop its render pipeline. See
    [#5](https://github.com/Mats2208/MCP-Packet-Tracer/issues/5).
