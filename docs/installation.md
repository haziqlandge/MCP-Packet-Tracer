# Installation

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | |
| `mcp[cli]` | ≥ 1.13, < 2 | Installed automatically |
| `pydantic` | ≥ 2.11, < 3 | Installed automatically |
| Cisco Packet Tracer | 8.2+ generally; macOS verified on 9.0.1 | Only for **live deploy**; older macOS builds are unverified |
| MCP Control Center extension | latest | This project's **own** PT extension (`.pts` in [Releases](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest)), only for live deploy — see [Live Deploy Setup](live-deploy.md) |

!!! warning "pydantic ≥ 2.11 is required"
    Modern `mcp` builds tool output schemas from return annotations and needs
    `pydantic ≥ 2.11`. An older pydantic makes the server crash on startup. The
    pinned dependencies handle this for you; just don't force an older pydantic.

## Let your AI agent install it

Paste this into Claude Code, OpenCode, Codex or any coding agent:

```text
Install the Packet Tracer MCP from https://github.com/Mats2208/MCP-Packet-Tracer and set everything up for me.
```

The agent follows [`llms-install.md`](https://github.com/Mats2208/MCP-Packet-Tracer/blob/main/llms-install.md),
does every step below, and leaves you one click: **Yes** when Packet Tracer asks to enable the extension.

## Install the server

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/), which brings its own Python:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh                          # macOS · Linux
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

There is nothing else to install: the client runs the server with `uvx packet-tracer-mcp --stdio`, which
downloads and caches it on first use.

!!! note "pip"
    `pip install packet-tracer-mcp` also works (then the command is `python -m packet_tracer_mcp --stdio`),
    but on macOS/Homebrew and recent Linux distros a plain `pip install` is refused with
    `externally-managed-environment` (PEP 668). Use `uv` or a virtualenv there.

Or from source, if you want to modify it:

```bash
git clone https://github.com/Mats2208/MCP-Packet-Tracer
cd MCP-Packet-Tracer
pip install -e .
```

| OS | Installed UI dependencies | Support |
|---|---|---|
| Windows | `comtypes` | Headless and UI mode |
| macOS | pyobjc frameworks | Headless and UI mode; two privacy grants required |
| Linux | No UI dependencies | Headless tools; UI mode not yet available |

UI dependencies install with the server; the `[ui]` extra is a compatible alias.
See the [per-OS path table](live-deploy.md#per-os-paths) for state and output locations.

!!! note "The extension is not part of the package"
    The server and the skill come from the package; the `.pts` extension is a module compiled by Packet
    Tracer itself, so it ships as a
    [release asset](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest) and Packet Tracer only
    accepts it through its own Extensions menu.

## Connect your MCP client

The examples below run the server with `uvx`. Installed with pip or from source instead? Let the
server print the configuration for the environment it is installed in:

```bash
pt-mcp doctor --print-config claude-code
pt-mcp doctor --print-config claude-desktop
```

The first prints a shell command to paste; the second prints JSON to merge into Claude Desktop's
configuration. Both use the absolute interpreter path, so a GUI client does not depend on your
shell's `PATH`. Printing a configuration runs no diagnostic checks.

=== "Claude Code"

    **Linux · macOS · Git Bash · Windows `cmd.exe`:**

    ```bash
    claude mcp add --scope user --transport stdio packet-tracer -- uvx packet-tracer-mcp --stdio
    ```

    **Windows PowerShell** — quote the `--` separator:

    ```powershell
    claude mcp add --scope user --transport stdio packet-tracer "--" uvx packet-tracer-mcp --stdio
    ```

    !!! warning "PowerShell eats a bare `--`"
        In Windows PowerShell the bare `--` separator is consumed before it reaches the
        `claude` CLI, so Claude treats the following `-m` as one of its own options and
        aborts with `error: unknown option '-m'`. Quoting it (`"--"`) passes it through
        literally. Alternatively use the `cmd.exe`/Git Bash form above, or wrap the whole
        command in `cmd /c "…"`.

    Verify (any shell):

    ```bash
    claude mcp list
    # packet-tracer: uvx packet-tracer-mcp --stdio - ✓ Connected
    ```

    Remove later with `claude mcp remove packet-tracer --scope user`.

=== "VS Code / Copilot"

    Add to your MCP config (`.vscode/mcp.json` or user settings):

    ```json
    {
      "servers": {
        "packet-tracer": {
          "type": "stdio",
          "command": "uvx",
          "args": ["packet-tracer-mcp", "--stdio"]
        }
      }
    }
    ```

=== "Generic (JSON)"

    Any MCP client that supports stdio servers:

    ```json
    {
      "mcpServers": {
        "packet-tracer": {
          "command": "uvx",
          "args": ["packet-tracer-mcp", "--stdio"]
        }
      }
    }
    ```

## Live deploy extension (optional)

To stream topologies into a **running** Packet Tracer, also install this project's own
**MCP Control Center** extension:

1. Download **`MCP-Control-Center.pts`** from
   **[Releases (latest)](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest)**.
2. Drop it in Packet Tracer's own `extensions` folder, in a subfolder
   (`…/extensions/MCPControlCenter/`): `Cisco Packet Tracer <version>.app/Contents/extensions/` on
   macOS, `C:\Program Files\Cisco Packet Tracer <version>\extensions\` on Windows (needs admin).
   PT asks *"detected a new script module… enable?"* at its next start — click **Yes**. Or add it
   by hand: **Extensions → Scripting → Configure PT Script Modules → Add…**.
3. Open **Extensions → MCP BUILDER** — it auto-connects to the bridge.

Full walkthrough → **[Live Deploy Setup](live-deploy.md)**.

## macOS privacy grants for UI mode

From your connected MCP client, call `pt_ui_mode("ui")`. Its reply names the
responsible app or executable and the path to add. In **System Settings → Privacy
& Security**, enable **Accessibility** and **Screen & System Audio Recording**
(**Screen Recording** on older macOS). If the app is absent, use **+**, then
**Cmd+Shift+G** to paste the reported path. macOS attributes a server to its
launcher, so a Terminal grant does not establish a grant for your MCP client.

`uvx packet-tracer-mcp doctor --ui` checks the terminal process's environment; it does not prompt.
Add `--request-permissions` only when you want to request
permissions from that process. `pt_bridge_status` and UI tool replies show the
connected server's permission state. All headless tools work without the grants.

## Diagnostics

```bash
uvx packet-tracer-mcp doctor
uvx packet-tracer-mcp doctor --ui
uvx packet-tracer-mcp doctor --json
```

(`pt-mcp doctor` with a pip or source install.)

The doctor checks installation, writable state and output paths, Packet Tracer,
extension activity, the bridge port, clipboard and UI availability. Each failed
check includes a fix. UI checks become required with `--ui`; clipboard availability
is optional. It exits with status 1 when a required check fails. If the MCP server
is stopped, extension detection can only use a file heartbeat; start the client
and open **Extensions → MCP BUILDER** if the extension is not seen.

## Agent Skill (required in practice)

The package ships a companion **Agent Skill** that teaches the model the exact tool catalog, the
discover→plan→validate→deploy workflow and the precise Script-Engine API — so the AI drives the MCP from
verified facts instead of guessing. Install it into your agent's skills folder:

```bash
uvx packet-tracer-mcp install-skill                          # Claude Code, OpenCode → ~/.claude/skills
uvx packet-tracer-mcp install-skill --dest ~/.agents/skills  # Codex
```

Then run `/reload-skills` (or restart your agent) and confirm with `/skills`. Full details →
**[Claude Code Skill](skill.md)**.

## Transport modes

- **stdio** (recommended for desktop clients): the client spawns the server as a
  child process. The internal HTTP bridge to Packet Tracer (`:54321`) still starts
  automatically inside that process — live deploy works the same.
- **streamable-http** (`http://127.0.0.1:39400/mcp`): start the server yourself with
  `python -m packet_tracer_mcp` and let multiple clients share one instance.

!!! note "If the client can't find `uvx`"
    A shell or app opened before installing uv doesn't see it yet: restart it, or put the full path in
    `command` (`~/.local/bin/uvx` on macOS/Linux, `%USERPROFILE%\.local\bin\uvx.exe` on Windows).

!!! note "Or an absolute interpreter"
    `uvx packet-tracer-mcp doctor --print-config claude-desktop` prints a client
    configuration with an absolute interpreter path, for GUI clients that do not
    inherit your shell's PATH.

Next: run the **[Quick Start](quickstart.md)** example.
