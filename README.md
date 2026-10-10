<div align="center">

<img src="https://raw.githubusercontent.com/Mats2208/MCP-Packet-Tracer/main/demo/banner.png" alt="Packet Tracer MCP — AI-powered Cisco Packet Tracer automation: generate, validate and deploy network topologies from natural-language prompts" width="100%"/>

**Tell your AI _"create a network with 3 routers, OSPF and DHCP"_ — it plans, validates, generates, and deploys the topology directly into Cisco Packet Tracer in real time.**

[![PyPI](https://img.shields.io/pypi/v/packet-tracer-mcp?style=flat-square&logo=pypi&logoColor=white&color=blue&label=pypi)](https://pypi.org/project/packet-tracer-mcp/)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Pydantic v2](https://img.shields.io/badge/pydantic-v2-E92063?style=flat-square&logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![MCP](https://img.shields.io/badge/protocol-MCP-00B4D8?style=flat-square)](https://modelcontextprotocol.io)
[![Website](https://img.shields.io/badge/website-mcpnetwork.top-0A66C2?style=flat-square&logo=googlechrome&logoColor=white)](https://www.mcpnetwork.top)
[![Docs](https://img.shields.io/badge/docs-mats2208.github.io-4051B5?style=flat-square&logo=materialformkdocs&logoColor=white)](https://mats2208.github.io/MCP-Packet-Tracer/)
[![License](https://img.shields.io/github/license/Mats2208/MCP-Packet-Tracer?style=flat-square&color=green)](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/LICENSE)

[![MCP Registry](https://lobehub.com/badge/mcp/mats2208-mcp-packet-tracer)](https://lobehub.com/mcp/mats2208-mcp-packet-tracer)

<br/>

<table>
<tr>
<td align="center"><strong>79 MCP Tools</strong></td>
<td align="center"><strong>5 MCP Resources</strong></td>
<td align="center"><strong>74 Device Models</strong></td>
<td align="center"><strong>151 Modules</strong></td>
<td align="center"><strong>15 Cable Types</strong></td>
</tr>
</table>

**🌐 Website:** https://www.mcpnetwork.top &nbsp;•&nbsp; **📚 Documentation:** https://mats2208.github.io/MCP-Packet-Tracer/

</div>

---

## Showcase

<p align="center">
  <img src="https://raw.githubusercontent.com/Mats2208/MCP-Packet-Tracer/main/demo/topology-screenshot.png" alt="3-router OSPF topology deployed to Packet Tracer" width="720"/>
</p>
<p align="center"><sub>3-router linear topology with OSPF, DHCP, and 6 PCs — planned and deployed via MCP tools</sub></p>

<table>
<tr>
<td width="50%">
<p align="center"><img src="https://raw.githubusercontent.com/Mats2208/MCP-Packet-Tracer/main/demo/mcp-client.png" alt="MCP tools executing in VS Code" width="100%"/></p>
<p align="center"><sub>Full build + live deploy pipeline in VS Code</sub></p>
</td>
<td width="50%">
<p align="center"><img src="https://raw.githubusercontent.com/Mats2208/MCP-Packet-Tracer/main/demo/cli-config.png" alt="Generated IOS CLI configs" width="100%"/></p>
<p align="center"><sub>Auto-generated IOS CLI configs with OSPF & DHCP</sub></p>
</td>
</tr>
</table>

<p align="center">
  <img src="https://raw.githubusercontent.com/Mats2208/MCP-Packet-Tracer/main/demo/live-deploy.gif" alt="Live deploy demo — from prompt to Packet Tracer in real time" width="720"/>
</p>
<p align="center"><sub>Live deploy — from a natural-language prompt to a running topology in Packet Tracer</sub></p>

---

## What it does

A **Model Context Protocol (MCP) server** that gives any LLM (Claude, GitHub Copilot, Codex, …) full programmatic control over Cisco Packet Tracer.

| | Feature | Details |
|---|---------|---------|
| **Planning** | Natural language → topology | A single prompt becomes a complete `TopologyPlan` |
| **IP / DHCP** | Auto /24 LANs + /30 links, DHCP pools on routers; `pt_configure_dhcp_server` for a dedicated **Server-PT** per subnet | Sequential, gateway at `.1` |
| **Routing** | Static · OSPF · EIGRP · RIP | Full IOS generation |
| **Switching** | VLANs, trunks, **inter-VLAN routing** (router-on-a-stick), STP, port-security | `.1q` subinterfaces + per-VLAN DHCP |
| **Security** | Device hardening (SSH, local users, enable-secret, banner), ACL/NAT | On live devices via the bridge |
| **IPv6** | Dual-stack addressing | Routers via CLI, hosts via SLAAC |
| **Wireless** | WiFi laptops + auto-associated Access Points | NIC swap → `Wireless0`, default-SSID assoc |
| **Validation** | Typed errors + auto-fixer | Wrong cables, missing ports, model upgrades |
| **Verification** | Plan-vs-live diff, health check, **real ping** (`pt_verify_connectivity`) | Drift, down links, duplicate IPs — and actual reachability |
| **Security audit** | `pt_audit_security` grades the **live** config: missing `enable secret`, reversible (type 7) credentials, `service password-encryption` off, `config-register 0x2142` | Reads the device, not the plan. Credentials never leave it — only the algorithm label |
| **Live inspection** | `pt_inspect_ports`, `pt_read_vlans`, `pt_device_power` | Per-port protocol/duplex/NAT/ACL state, real VLAN database, power-cycle with read-back |
| **Packet tracing** | `pt_simulation_mode`, `pt_simulation_step`, `pt_read_packet_trace` | Step the simulation and read **why** each packet did what it did — PT's own per-OSI-layer decision log, not just pass/fail |
| **Telemetry** | `pt_apply_netflow` configures a NetFlow exporter directly and reads it back; `pt_read_qos` verifies class-maps and policy-maps | Collector address, UDP port, version, source interface |
| **Device panel** | `pt_cli`, `pt_host_command`, `pt_terminal`, `pt_host_ip_config`, `pt_web_browser`, `pt_email_client`, `pt_host_firewall`, `pt_server_dhcp` / `_dns` / `_http` / `_service` | Every tab of a device window — IOS CLI, the PC's Command Prompt and Desktop apps, Server-PT Services — driven through PT's API. No mouse, no keyboard, nothing taken over on screen |
| **UI mode** | `pt_ui_mode`, `pt_ui_open`, `pt_ui_capture` | Headless by default; switch to `ui` and every panel tool also opens the real device window on the right tab so you can watch, with optional PNG captures |
| **Backup** | `pt_backup_config`, `pt_project_metadata`, `pt_workspace_options` | Real startup-config + serial + config-register; project info; auto-cabling and real-network-access toggles |
| **Deploy** | Real-time bridge to PT (auto-reconciles) | No copy-paste — commands stream directly |
| **Two channels** | HTTP when the extension window is open, **file-bridge when it's closed** | PT keeps executing with the window minimized/closed |
| **Projects** | Save / open the real `.pkt` (`pt_save_project` / `pt_open_project`) | Persist the running topology, not just the plan JSON |
| **Export** | Plans, JS scripts, CLI configs | Reusable project files on disk |

👉 Full tool reference, device catalog, networking guides and architecture live in the **[documentation site](https://mats2208.github.io/MCP-Packet-Tracer/)**.

## Installation

**1. Install the server**

```bash
pip install packet-tracer-mcp
```

Or install it in an isolated environment with uv:

```bash
uv tool install packet-tracer-mcp
```

UI dependencies install automatically for your OS; the `[ui]` extra remains a
compatible alias. UI mode opens and captures device windows on macOS and Windows.
Linux supports headless tools; UI mode is not available yet.

The cross-platform UI and `pt-mcp doctor` changes on this branch are unreleased.
Until a release includes them, install this checkout from source (the PyPI commands
above install the published version):

```bash
git clone --branch feat/cross-platform https://github.com/Mats2208/MCP-Packet-Tracer
cd MCP-Packet-Tracer
python -m venv .venv
# macOS / Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows cmd.exe: .venv\Scripts\activate.bat
python -m pip install -e .
```

**2. Connect your MCP client** (Claude Code shown)

Generate a command using the absolute Python interpreter from your installation:

```bash
pt-mcp doctor --print-config claude-code
```

Paste the printed command into your shell. For Claude Desktop, use
`pt-mcp doctor --print-config claude-desktop` and merge the printed JSON into its
MCP configuration. Configuration output does not run diagnostics. For other
clients, use that JSON's `command` and `args` in their stdio server settings.

_Linux · macOS · Git Bash · Windows `cmd.exe`_ — the equivalent command when
`python` is the interpreter where you installed the package:

```bash
claude mcp add --scope user --transport stdio packet-tracer -- python -m packet_tracer_mcp --stdio
```

_Windows PowerShell_ — quote the `--` separator, or PowerShell swallows it and Claude aborts with `error: unknown option '-m'`:

```powershell
claude mcp add --scope user --transport stdio packet-tracer "--" python -m packet_tracer_mcp --stdio
```

Verify with `claude mcp list` (look for `packet-tracer … ✓ Connected`).

**3. Install the live-deploy extension** — _only if you want real-time deploy into a running Packet Tracer_

Download **`V5.2.pts`** from [**Releases**](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest), then in Packet Tracer go to **Extensions → Scripting → Configure PT Script Modules → Add…** and select it. Full walkthrough in [Live deploy](#live-deploy) below.

> **v0.6.0+ requires V5.** The bridge now authenticates with a per-machine token that the V5 extension reads automatically; builds before V5 can't authenticate.

**4. Install the Claude Code Skill** — _recommended; makes the AI use the MCP correctly instead of guessing_

The repo ships a companion **[Agent Skill](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/skill/SKILL.md)** that teaches the model the exact tool
catalog, the discover→plan→validate→deploy workflow, and the precise Script-Engine API (so it never
invents method/model/port names). Install it **globally** from the repo root:

_Linux · macOS · Git Bash:_

```bash
mkdir -p ~/.claude/skills/packet-tracer && cp -r skill/. ~/.claude/skills/packet-tracer/
```

_Windows PowerShell:_

```powershell
New-Item -ItemType Directory -Force "$HOME\.claude\skills\packet-tracer" | Out-Null; Copy-Item -Recurse -Force skill\* "$HOME\.claude\skills\packet-tracer\"
```

Then run `/reload-skills` in Claude Code (or restart it) and confirm with `/skills`. Details →
**[Skill docs](https://mats2208.github.io/MCP-Packet-Tracer/skill/)**.

> Requires **Python 3.11+** (deps `mcp[cli]>=1.13`, `pydantic>=2.11` install automatically).
> Full setup for every client → **[Installation docs](https://mats2208.github.io/MCP-Packet-Tracer/installation/)**.

## macOS setup

1. Install Python 3.11+ and the server using the source instructions above for
   this unreleased branch. Activate that environment, then generate your client configuration with
   `pt-mcp doctor --print-config claude-code` (or `claude-desktop`), paste it into
   the client, and reconnect the server.
2. Install Cisco Packet Tracer (**9.0.1 verified on macOS**; older macOS builds
   are unverified) and manually register **V5.2.pts** from
   [Releases](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest) through
   **Extensions → Scripting → Configure PT Script Modules → Add…**. Open
   **Extensions → MCP BUILDER**. Package installation cannot register a `.pts`.
3. For UI mode, ask the connected client to call `pt_ui_mode("ui")`. Its reply
   names the app or executable macOS holds responsible for that server. In
   **System Settings → Privacy & Security**, enable both **Accessibility** and
   **Screen & System Audio Recording** (called **Screen Recording** on older
   macOS versions) for that named app. If it is absent, add it using **+** and
   **Cmd+Shift+G** to paste the path from the reply. A server launched by Terminal
   and a server launched by your MCP client can require different grants. Use
   the client's remedy, rather than granting Python or Packet Tracer by guess.
4. Ask for `pt_bridge_status`, then open or capture a device with `pt_ui_open` or
   `pt_ui_capture`. Run `pt-mcp doctor --ui` for diagnostics in the terminal's
   environment; `--json` gives structured output. Only an explicit
   `--request-permissions` asks macOS for grants. Terminal diagnostics cannot
   prove the client's permission state; its tool reply is the check for that
   process.

The `.pts` installation and both privacy grants need your interaction. Headless
planning and live tools do not need those grants. State, compatibility mailboxes
and output locations are listed in the [per-OS path table](docs/live-deploy.md#per-os-paths).

## Quick start

Just talk to your AI:

> *"Build a network with 2 routers, 2 switches, 4 PCs, DHCP and static routing."*

The LLM calls `pt_full_build`, which plans → validates → generates → deploys.
See the **[Quick Start guide](https://mats2208.github.io/MCP-Packet-Tracer/quickstart/)**.

## Live deploy

Stream topologies into a **running** Packet Tracer in real time. Install this repo's
own **MCP Control Center** extension once — the `.pts` from
[**Releases**](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest) — via
**Extensions → Scripting → Configure PT Script Modules → Add…**, then open
**Extensions → MCP BUILDER**. It auto-connects to the bridge — no snippet to paste.

<p align="center"><img src="https://raw.githubusercontent.com/Mats2208/MCP-Packet-Tracer/main/demo/install-demo.gif" alt="Installing the MCP Control Center extension in Packet Tracer" width="760"/></p>
<p align="center"><sub>Installing the MCP Control Center extension (V5) in Packet Tracer</sub></p>

📖 Full steps → **[Live Deploy Setup](https://mats2208.github.io/MCP-Packet-Tracer/live-deploy/)**.

## Device panel and UI mode

Once a topology is live, the agent can work inside each device the way a student would —
type in a router's **CLI** tab (`pt_cli`), run `ping`/`ipconfig`/`nslookup` from a PC's
**Command Prompt** (`pt_host_command`), set **IP Configuration**, browse with the **Web
Browser**, configure a server's **DHCP/DNS/HTTP/FTP/EMAIL** services — all through Packet
Tracer's own API. What it types appears in the real CLI tab, so you can watch or take over.

It is **headless by default**: nothing opens on screen. Say *"show it in Packet Tracer"* (or
call `pt_ui_mode("ui")`) and every panel tool also opens the device's window on the matching
tab or app; `capture=True` saves a PNG of it. The backend depends on the OS:

| OS | UI behavior |
|---|---|
| Windows | UI Automation navigates the panels; canvas clicks are posted without moving the real cursor, and `PrintWindow` captures the windows. |
| macOS | Accessibility navigates the panels; PT comes to the front, and a canvas click can briefly move the cursor before restoring it. Captures require Screen Recording permission. |
| Linux | UI mode is not available yet; device-panel tools work headless through PT's API. |

Dependencies install with the server. On macOS, follow the [two-grant setup](#macos-setup).
Claude Code users also get the prompts `/mcp__packet-tracer__ui_on` and `ui_off`.

📖 Tool list → **[Device panel](https://mats2208.github.io/MCP-Packet-Tracer/tools/#device-panel-cli-desktop-and-services)**.

## Clients

Any MCP client drives this server — Claude Code, Cursor, Claude Desktop, VS Code with
Copilot, Codex. Nothing in it is client-specific.

There is also one built **on** it: **[PacketSmith](https://github.com/Mats2208/packetsmith)**,
a terminal app that runs these tools with the network drawn beside the conversation — a
fabric tree and a canvas plan derived from the `pt_*` results themselves, so a device the
model *says* it created but did not never shows up.

| | This server alone | This server + PacketSmith |
|---|---|---|
| Where you talk | the MCP client you already use | a terminal app built for this one job |
| What you see | a chat log, plus PT in another window | split screen: reply left, live topology right |
| Topology | read out of the tool output | fabric tree and canvas plan, drawn for you |
| Tools loaded | every MCP server you have configured | this one only — measurably faster to start |
| Engine | whatever your client speaks | Claude, or ~150 providers |

**You need this server either way** — PacketSmith runs it underneath, and its setup installs
it for you. If you already live in Claude Code, you are done here; the client is for when you
want the topology in front of you instead of buried in a scrollback.

```bash
npm i -g packetsmith    # beta · MIT
```

## Credits & Acknowledgements

Live deploy runs through **our own Packet Tracer extension** — the **MCP Control
Center** (the `.pts` in [Releases](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest)).
Its Script-Engine helper layer was **inspired by**
**[PTBuilder](https://github.com/kimmknight/PTBuilder)** by
**Kim Knight ([@kimmknight](https://github.com/kimmknight))**, who pioneered driving
Packet Tracer's Script Engine from JavaScript — thanks for the groundwork. 🙏

> PTBuilder and Packet Tracer MCP are **separate, independent projects**. You install
> *our* extension, not PTBuilder. Full
> **[Credits & Attribution](https://mats2208.github.io/MCP-Packet-Tracer/credits/)**.

## Security

Driving Packet Tracer from outside means running a local HTTP bridge whose whole
job is to hand JavaScript to PT's Script Engine — code that executes with PT's
own privileges, including disk access. That makes the bridge a genuine attack
surface, not an implementation detail, and it is hardened accordingly.

**The attack this design exists to stop.** Binding to `127.0.0.1` is *not* a
security control. A `POST` with `Content-Type: text/plain` is a CORS *simple
request*: any web page open in your browser can send it to a loopback port
without a preflight and without needing to read the response. An unauthenticated
bridge therefore lets any website you visit — while Packet Tracer happens to be
open — queue arbitrary code inside it. Injection never needed to read anything
back, so same-origin policy alone never closed this.

What actually closes it is a secret the attacking page cannot guess:

| Control | Implementation |
|---|---|
| **Token on every endpoint** | Every route except `/ping` requires a shared token (`?t=` or `X-PT-Token`). Compared with `hmac.compare_digest` — constant time, no early-exit oracle. |
| **`/ping` leaks nothing** | Deliberately unauthenticated so the server can tell *who owns the port* before trusting it — but it returns only a SHA-256 **fingerprint** of the token, never the token. |
| **Foreign-bridge detection** | Before sending any payload, the server checks that `/ping` identity matches its own token fingerprint. If a stranger holds the port, it refuses to hand code to it instead of blindly trusting a `200`. |
| **DNS-rebinding defense** | The `Host` header is validated against `127.0.0.1` / `localhost` / `[::1]` + the real port. A rebound request arrives as `Host: evil.com:<port>` and is rejected. |
| **Loopback bind** | `ThreadingHTTPServer(("127.0.0.1", port))` — never `0.0.0.0`, so the bridge is not reachable from the LAN. |
| **Token at rest** | `secrets.token_urlsafe(32)`, created with `O_EXCL` (race-safe when two servers start at once) at mode `0o600` in the per-user state directory. Platform locations and compatibility fallbacks are in the [per-OS path table](docs/live-deploy.md#per-os-paths). |
| **Body size cap** | Oversized bodies are rejected with `413` and are **not** read into memory. |
| **Silent failures** | Error responses carry no CORS headers, so a hostile page cannot even distinguish *why* it failed. |
| **Tamper visibility** | Unauthorized attempts are counted and surfaced by `pt_bridge_status`, so a stale or rogue client is diagnosable instead of silent. |

Regression coverage lives in [`tests/test_bridge_security.py`](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/tests/test_bridge_security.py)
and [`tests/test_injection_regressions.py`](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/tests/test_injection_regressions.py);
the full suite runs offline with `python -m pytest` — no Packet Tracer required.

> **v0.6.0+ requires the V5 extension.** Versions before v0.6.0 shipped an
> unauthenticated bridge and are vulnerable to exactly the attack above.
> **Upgrade — there is no safe configuration of the old bridge.**

**Deliberate, documented behaviour:** `pt_send_raw` executes arbitrary JavaScript
inside Packet Tracer by design — it is the escape hatch for exploring the IPC
API. It is reachable only by an MCP client you have already authorised, over the
authenticated bridge. That is a capability, not a vulnerability.

Found a vulnerability? Report it privately via
[GitHub Security Advisories](https://github.com/Mats2208/MCP-Packet-Tracer/security/advisories/new),
not a public issue. [SECURITY.md](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/SECURITY.md) documents the full threat model.

## What's new

**v0.9.0** — the first release you can `pip install`, and the one that went hunting
for **silent false OKs**: a topology split into islands that validation approved
with `error_count: 0`, a bridge handing back the previous operation's result, a
`"CONECTIVIDAD OK"` reported with 75% packet loss. None of them crashed; all of
them lied. The server also reports its own version during the MCP handshake now —
it used to announce the version of the `mcp` SDK. v0.8.0 let the agent **show** the
network instead of only describing it: canvas screenshots plus notes and drawings,
for topologies that document themselves. v0.7.0 made the server read a live
topology, not just build one: security auditing, per-port inspection, packet
tracing with Packet Tracer's own per-layer decision log, NetFlow, and config
backup. Full list in the **[Changelog](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/CHANGELOG.md)**.

## Contributing

See [CONTRIBUTING.md](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/CONTRIBUTING.md). Tests run offline with
`python -m pytest`; no Packet Tracer needed.

## License

Released under the **[MIT License](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/LICENSE)** — © 2026 Mateo ([@Mats2208](https://github.com/Mats2208)).

<div align="center">

**Built with [MCP](https://modelcontextprotocol.io) · Powered by [Pydantic](https://docs.pydantic.dev) · Deploys to [Cisco Packet Tracer](https://www.netacad.com/) · Script-engine logic inspired by [PTBuilder](https://github.com/kimmknight/PTBuilder)**

**Terminal client built on this server → [PacketSmith](https://github.com/Mats2208/packetsmith)**

If this project is useful to you, star it ⭐ and share it with the community.

</div>
