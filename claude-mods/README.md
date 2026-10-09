# claude-mods

The three Claude Code mods that were loaded on the Windows machine while this
branch was planned. They are copied here so the Mac session runs with the same
setup. They are branch-local tooling, not part of the MCP server: delete this
folder, together with the plan docs, before any upstream PR.

| Mod | What it shows |
|---|---|
| `progress-tracker` | Plan and task bars above the prompt. It reads `PLAN/INDEX.md` and the `## Acceptance criteria` boxes of each `PLAN/phases/PHASE-NN.md`, so ticking a box moves the bar |
| `cache-timer` | How long the prompt cache stays warm |
| `cost-ticker` | Session and month cost, token totals and cache hit rate. It owns the band's open/close toggle that the other two read |

The `.claude-plugin/types/` folders are left out on purpose. The engine writes
them again every time it loads a mod.

## Load them on macOS

Add the three folders to the `env` block of `~/.claude/settings.json` (the
user's settings; a project's settings are not read for this). Separate them
with `:`, the macOS path-list separator (Windows uses `;`). `~` is allowed.
Replace `<clone>` with where this repository is checked out:

```json
{
  "env": {
    "CLAUDE_CODE_PLUGIN_DIRS": "~/<clone>/claude-mods/progress-tracker:~/<clone>/claude-mods/cache-timer:~/<clone>/claude-mods/cost-ticker"
  }
}
```

Merge it into the existing file rather than replacing the file. Then restart
Claude. In a terminal session you can instead pass
`claude --plugin-dir <folder>` once per mod.

## Check them

```bash
node claude-mods/progress-tracker/tests/check.mjs .
```

prints every phase with its ticked and total acceptance boxes. With a second
argument (`preview.html`) it also writes the bars to an HTML page.
`claude plugin validate claude-mods/<mod>` and `claude plugin test claude-mods/<mod>`
validate and test a mod.
