# PHASE-07 — Docs, skill and end-to-end acceptance

## Objective

Every user-facing text describes each OS correctly. The README has a macOS
section that a new user can follow alone. Tool descriptions, the `pt://guide`
resource, the skill and `CODEMAP.md` match the code. The out-of-the-box run in
`EVALUATION.md` §6 passes on the Mac.

## Why it exists

Requirement (e) in `RESEARCH/SYNTHESIS.md` §1. The code can be cross-platform
and still fail its users if the README says "UI mode on Windows" and the docs
say "`%LOCALAPPDATA%`" (ISSUES F1 lists the places). The end-to-end run is the
only evidence for the user's actual requirement ("just connect mcp and it
works"). Every earlier phase tests a part. This one tests the whole, the way a
user meets it.

## Dependencies

- PHASE-01 to PHASE-06: everything the docs describe must exist.

## Files to modify

- `README.md`: install per OS (uv / pip; the client config through `pt-mcp
  doctor --print-config`); the `.pts` install; a macOS section with the two
  grants and the app to grant; the UI-mode paragraph (`README.md:99`, `:191`);
  the security table's token row (`:260`) per OS.
- `docs/installation.md`, `docs/live-deploy.md`, `docs/architecture.md`,
  `docs/tools.md`: replace every Windows-only statement and mailbox path (ISSUES F1).
- `skill/reference/tools.md:79`, `skill/reference/rough-edges.md:129`: UI mode
  per OS. **Sync the installed copy as before** (`~/.claude/skills/packet-tracer/`
  on the Mac).
- Tool descriptions that say Windows (`device_panel_tools.py:188` "Requires
  Windows and the [ui] extra" and any found by `grep -rn "Windows" src/packet_tracer_mcp/adapters`):
  make them OS-neutral. Regenerate `tests/fixtures/tool_api.json` with
  `UPDATE_TOOL_API=1` **in this phase only** (C9), and check each diff line is a
  description change.
- `settings.py` `GUIDE`: the per-OS setup section from PHASE-06, final wording.
- `pyproject.toml` classifiers; `CHANGELOG.md` (Unreleased: cross-platform
  support); `CODEMAP.md` regenerated.
- `CONTRIBUTING.md`: the live test lists (`tests/live/`) and the macOS fixture
  recorder.

## Implementation details

### Writing rules

- English only (AGENTS "Language").
- One home per fact. The per-OS path table lives in `docs/live-deploy.md`, and
  every other page links to it.
- Say plainly what still needs the user: the `.pts` install, the two macOS
  grants, and on Linux "UI mode not yet" (`EVALUATION.md` §9).
- The Windows instructions keep working word for word wherever nothing changed.
  The PowerShell `--` quoting note in the README stays.

### End-to-end run (`EVALUATION.md` §6)

1. On the Mac, remove the server's state: `~/.local/state/packet-tracer-mcp`,
   the venv or uv cache entry, and the MCP entry in the client.
2. Keep PT and V5.2 installed. The `.pts` step is then counted but not performed.
3. Follow only the README's macOS section. Count every user action and note any
   point where the README was not enough. Each such point is a docs bug: fix it
   and restart the run.
4. Revoke both grants (`tccutil reset Accessibility <bundle id>` and
   `tccutil reset ScreenCapture <bundle id>`, with the client's bundle id),
   then run the UI request from the client.
5. Record the action count, the doctor output and the PNG path in PREVIOUS_WORK
   Part 1.

### The open question this phase must answer

Is ≤ 4 user actions achievable on a real Mac with the user's client? If not,
record the real count and what forces each extra step. Do not hide a step in
"prerequisites" to make the number fit (`EVALUATION.md` §9).

## Inputs / outputs

- In: the finished code.
- Out: the docs, the skill, the tool API snapshot, the CHANGELOG, and the
  end-to-end record.

## Relevant interfaces

`INTERFACES.md` §5 (the path table the docs publish), §6 (doctor flags the
README uses).

## Relevant research

`RESEARCH/topics/macos-ui-automation.md` §1 (which app to grant, in the user's words).

## Tests

- Existing guards: tool description cap (1,500), `SERVER_INSTRUCTIONS` cap
  (2,000), the tool API snapshot, CODEMAP freshness, pyflakes.
- `grep -rn "LOCALAPPDATA" README.md docs skill src/packet_tracer_mcp/adapters`
  finds only per-OS tables (recorded output).
- `mkdocs build --strict` (requirements in `docs/requirements.txt`) succeeds.

## Acceptance criteria

- [x] Full offline suite passes on the Mac — 1233 passed in 34.72 s, 2026-10-10

- [x] CODEMAP indexes doctor and current OS backends; generated output passes guards — 8 registry/CODEMAP tests passed, 2026-10-10
- [x] Tool API snapshot is refreshed with description changes only — JSON comparison: only pt_deploy and pt_ui_open descriptions; schemas identical, 2026-10-10

- [ ] The suite passes on the Mac and CI; `tool_api.json` diff = description changes only (recorded)
- [x] `mkdocs build --strict` passes — temporary docs venv /private/tmp/pt-mcp-docs-venv; strict build exit 0, 2026-10-10
- [x] No Windows-only statement remains outside per-OS tables (grep recorded) — LOCALAPPDATA only docs/live-deploy.md per-OS table; PREVIOUS_WORK 2.11, 2026-10-10
- [x] The installed skill copy on the Mac is synced (diff empty) — diff -qr skill ~/.claude/skills/packet-tracer: empty, 2026-10-10
- [ ] `EVALUATION.md` §6 passed on the Mac: action count, doctor output and PNG recorded in PREVIOUS_WORK — **BLOCKED: fresh-client setup and real permission-reset approval pending; no action count or PNG claimed**
- [x] `CHANGELOG.md` Unreleased lists the platform layer, mailbox discovery, the XDG change, macOS UI mode, automatic UI dependencies and `pt-mcp doctor` — Unreleased section reviewed, 2026-10-10

Added 2026-10-24 (upstream merge, Mac lab runs, OS-aware shortcuts):

- [x] Upstream `main` @ `d9bb732` merged into the branch with no conflicts; suite passes on the Mac — merge `f7cb31e`, 1348 passed in 38.55 s, 2026-10-24
- [x] Control Center editor shortcuts and hints follow the OS (⌘ on macOS, Ctrl elsewhere) — `tests/test_webview_shortcuts.py` 8 passed, 8 failed before the fix; Mac Chromium render check, 2026-10-24
- [x] The OS-aware shortcuts show and work in PT's own Control Center on the Mac (needs a rebuilt `.pts`) — `MCP-BUILDER-os-shortcuts.pts` built and installed with the user's OK; AX read of the webview: "Run (⌘↩)", "Clear editor (⌘K)", "Clear log (⌘L)", ⌘↩/⌘K hints; ⌘K cleared the editor, Control+K left `line1⏎line2`; ⌘L cleared the log, Control+L did not; ⌘↩ ran once, Control+↩ did not, 2026-10-24
- [x] Lab task list for the two live labs written (`tests/live/labs/`) — README + 7 call lists, results recorded, 2026-10-24
- [x] CCE2 IPS lab (PDF pp. 6–10): topology, addressing and routing built through the MCP on the Mac — `ips-1-build.json` all calls ok, 9 devices/8 links, PC-1 4/4 to .100 and .50, 2026-10-24
- [x] CCE2 IPS lab: securityk9 licence, IOS IPS, ACL 110 and SPAN configured on the Mac — `show version` securityk9 Evaluation; `show ip ips all` IOSIPS inbound Gi0/0, 1 active sig; `show monitor` Gi0/1→Fa0/24, 2026-10-24
- [x] CCE2 IPS lab: all six rows of the PDF's Table 7 observed on the Mac — attacker ping reply → dropped with `%IPS-4-SIGNATURE Sig:2004`; syslog 5→7 per 2 attack pings, unchanged by internal; HTTP page served; PC-1 4/4, 2026-10-24
- [x] Static-routing lab: subnetted topology built and configured through the MCP on the Mac — `static-1-build.json`: 12 devices/11 links, R1 18/18, R2 22/22, R3 18/18 commands ok, /26 and /30 masks in `pt_query_topology`, 2026-10-24
- [x] Static-routing lab: every LAN reaches every other LAN; `show ip route` lists the static routes — R1 3, R2 2, R3 3 `S` routes; warm matrix 9/9 pings 4/4 (A↔B, A↔C, B↔C both ways); tracert .1→.194→.198→.139, 2026-10-24
- [x] OSPF lab (single area 0, three routers in a triangle) built, converged and failed over through the MCP on the Mac — `ospf-1..6`: 3×2 neighbours FULL, `O` routes cost 2; R1–R3 shut → LAN3 `[110/3] via 10.0.12.2`, tracert via R2, 4/4 ping; restored → `[110/2] via 10.0.13.2`, 50/50 pings, 2026-10-25
- [x] macOS UI activation (ISSUES X18): `_wait_front` falls back to LaunchServices and reads PT's `AXFrontmost` live instead of the cached `NSWorkspace` answer — `tests/test_macos_click_route.py` 29 passed (new tests failed before), 2026-10-25
- [x] UI mode end to end on the Mac after the Screen Recording grant: real window captures of a CLI and a Command Prompt — DHCP lab through `live_smoke` with PT in front at 100 % zoom: R1, DHCP-Server, PC1, PC3 opened by click; 12 non-blank window captures incl. R1 CLI (1400×1416) and PC1/PC3 Command Prompt; `projects/dhcp-lab/screens/`, 2026-10-25
- [x] UI activation fix (ISSUES X18) live: with Claude in front, `pt_ui_open` brings PT forward and opens the dialog — after the X13 fix: Claude frontmost, PT's AX list empty → PC4, PC2, SW2, then R1, DHCP-Server, PC2 (reopened lab) all opened by click and captured; `projects/dhcp-lab/live-proof/`, 2026-10-25
- [x] X13: an empty PT window list activates PT (`open -a`) and is read again; a dialog not yet open never activates PT — 4 tests (3 failed before); live as above, 2026-10-25
- [x] Full screen: the window lookup takes PT's main window out of full screen first — 4 tests (2 failed before); live: PT full screen + Claude in front → R1, DHCP-Server, PC2 opened and captured, 2026-10-25
- [x] X19: at zoom ≠ 100 % the presenter presses Zoom Reset before the canvas click — 3 tests (2 failed before), Windows-flow tests unchanged; live at zoom −2: step "zoom reset to 100%", PC4 and R1 opened, 2026-10-25
- [x] X20: the macOS click route re-checks the Select tool with PT in front right before the click — 5 tests (4 failed before); live: 7 clicks after it, no stray note or PDU, 2026-10-25
- [x] No Windows-only key shortcut is left in a user-facing tool description or reply on macOS — paste steps use `Platform.shortcut()` (test fails without it); `pt_save_project` description made OS-neutral, `tool_api.json` diff = that description only; grep of src/docs/skill/webview clean, 2026-10-24

## Known failure conditions

- `tool_api.json` shows a schema change → a parameter changed by accident.
  Revert it (C9).
- `mkdocs --strict` fails on a link → a page moved. Fix the link; do not remove
  `--strict`.
- The fresh-install run needs an undocumented step → a docs bug. Fix the README
  and run again from step 1.
- `tccutil reset` fails → wrong bundle id. Read it with
  `osascript -e 'id of app "Claude"'`.
