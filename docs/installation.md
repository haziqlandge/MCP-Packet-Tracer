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

## Install the server

```bash
pip install packet-tracer-mcp
```

Or use an isolated uv tool environment:

```bash
uv tool install packet-tracer-mcp
```

| OS | Installed UI dependencies | Support |
|---|---|---|
| Windows | `comtypes` | Headless and UI mode |
| macOS | pyobjc frameworks | Headless and UI mode; two privacy grants required |
| Linux | No UI dependencies | Headless tools; UI mode not yet available |

The `[ui]` extra is a compatible alias; no separate UI installation is needed.
See the [per-OS path table](live-deploy.md#per-os-paths) for state and output locations.

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

Either way the `packet_tracer_mcp` module becomes importable from any directory,
so `python -m packet_tracer_mcp --stdio` works from anywhere — no need to `cd`
into the repo or keep a server running.

!!! note "The extension is not part of the package"
    `pip install` gives you the server, and nothing else. The `.pts` extension is
    a module compiled by Packet Tracer itself, so it ships as a
    [release asset](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest)
    rather than inside the wheel — and Packet Tracer only accepts it through its
    own Extensions menu anyway. You need it **only for live deploy**; planning,
    validation and config generation work without it.

## Connect your MCP client

Generate configuration from the environment where you installed the server:

```bash
pt-mcp doctor --print-config claude-code
pt-mcp doctor --print-config claude-desktop
```

The first command prints a shell command to paste; the second prints JSON to
merge into Claude Desktop's configuration. Both use the absolute interpreter
path so a GUI client does not depend on your shell's `PATH`. Configuration output
does not run diagnostic checks. The examples below also work when `python`
resolves to the interpreter containing the package.

=== "Claude Code"

    **Linux · macOS · Git Bash · Windows `cmd.exe`:**

    ```bash
    claude mcp add --scope user --transport stdio packet-tracer -- python -m packet_tracer_mcp --stdio
    ```

    **Windows PowerShell** — quote the `--` separator:

    ```powershell
    claude mcp add --scope user --transport stdio packet-tracer "--" python -m packet_tracer_mcp --stdio
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
    # packet-tracer: python -m packet_tracer_mcp --stdio - ✓ Connected
    ```

    Remove later with `claude mcp remove packet-tracer --scope user`.

=== "VS Code / Copilot"

    Add to your MCP config (`.vscode/mcp.json` or user settings):

    ```json
    {
      "servers": {
        "packet-tracer": {
          "type": "stdio",
          "command": "python",
          "args": ["-m", "packet_tracer_mcp", "--stdio"]
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
          "command": "python",
          "args": ["-m", "packet_tracer_mcp", "--stdio"]
        }
      }
    }
    ```

## Live deploy extension (optional)

To stream topologies into a **running** Packet Tracer, also install this project's own
**MCP Control Center** extension:

1. Download **`V5.2.pts`** from
   **[Releases (latest)](https://github.com/Mats2208/MCP-Packet-Tracer/releases/latest)**.
2. In Packet Tracer: **Extensions → Scripting → Configure PT Script Modules → Add…**,
   select `V5.2.pts`, and confirm.
3. Open **Extensions → MCP BUILDER** — it auto-connects to the bridge.

Full walkthrough → **[Live Deploy Setup](live-deploy.md)**.

## macOS privacy grants for UI mode

From your connected MCP client, call `pt_ui_mode("ui")`. Its reply names the
responsible app or executable and the path to add. In **System Settings → Privacy
& Security**, enable **Accessibility** and **Screen & System Audio Recording**
(**Screen Recording** on older macOS). If the app is absent, use **+**, then
**Cmd+Shift+G** to paste the reported path. macOS attributes a server to its
launcher, so a Terminal grant does not establish a grant for your MCP client.

`pt-mcp doctor --ui` checks the terminal process's environment; it does not prompt.
Use `pt-mcp doctor --ui --request-permissions` only when you want to request
permissions from that process. `pt_bridge_status` and UI tool replies show the
connected server's permission state. All headless tools work without the grants.

## Diagnostics

```bash
pt-mcp doctor
pt-mcp doctor --ui
pt-mcp doctor --json
```

The doctor checks installation, writable state and output paths, Packet Tracer,
extension activity, the bridge port, clipboard and UI availability. Each failed
check includes a fix. UI checks become required with `--ui`; clipboard availability
is optional. It exits with status 1 when a required check fails. If the MCP server
is stopped, extension detection can only use a file heartbeat; start the client
and open **Extensions → MCP BUILDER** if the extension is not seen.

## Claude Code Skill (recommended)

The repo ships a companion **Agent Skill** (`skill/SKILL.md`) that teaches the model the exact tool
catalog, the discover→plan→validate→deploy workflow, and the precise Script-Engine API — so the AI
drives the MCP from verified facts instead of guessing. Install it **globally** from the repo root:

=== "Linux / macOS / Git Bash"

    ```bash
    mkdir -p ~/.claude/skills/packet-tracer
    cp -r skill/. ~/.claude/skills/packet-tracer/
    ```

=== "Windows PowerShell"

    ```powershell
    New-Item -ItemType Directory -Force "$HOME\.claude\skills\packet-tracer" | Out-Null
    Copy-Item -Recurse -Force skill\* "$HOME\.claude\skills\packet-tracer\"
    ```

Then run `/reload-skills` (or restart Claude Code) and confirm with `/skills`. Full details, including
what it covers and a project-local alternative → **[Claude Code Skill](skill.md)**.

## Transport modes

- **stdio** (recommended for desktop clients): the client spawns the server as a
  child process. The internal HTTP bridge to Packet Tracer (`:54321`) still starts
  automatically inside that process — live deploy works the same.
- **streamable-http** (`http://127.0.0.1:39000/mcp`): start the server yourself with
  `python -m packet_tracer_mcp` and let multiple clients share one instance.

!!! note "GUI clients may not inherit your shell PATH"
    Use `pt-mcp doctor --print-config claude-desktop` for an absolute interpreter
    path, or put that interpreter in your client's `command` field. This applies
    on every OS.

Next: run the **[Quick Start](quickstart.md)** example.
