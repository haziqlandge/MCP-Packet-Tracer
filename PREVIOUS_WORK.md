# PREVIOUS WORK

What has been done and proved on `feat/cross-platform`. Open items are in
`ISSUES.md`; next steps are in `FUTURE_WORK.md`. Work before this branch
(device-panel control, context-cost optimisation, English conversion) is in
`CHANGELOG.md` and git history.

Part 1 is the story. Part 2 is the set of things that were expensive to learn and
would be expensive to learn twice. **Grep this file before re-deriving
anything. Do not read it whole.**

---

# Part 1 — Timeline

**2026-10-10 — Cross-platform plan written (Windows machine).** The user asked
for the MCP to work on macOS on a separate branch, with "cross modularity", and
set the bar: connect the MCP and it works out of the box on any OS. User
decisions: full UI-mode parity on macOS now; the plan docs committed on the
branch; every phase executed on the user's Mac, which has PT. Branch
`feat/cross-platform` was created from `main` @ `bcb2ef3`. `PLAN/`, `RESEARCH/`
and the state docs were written. The user's three loaded Claude Code mods were
copied into `claude-mods/` (generated types left out) so the Mac runs the same
setup. `progress-tracker/tests/check.mjs` parses all nine phases. No server code
changed. Tests (Windows, before branching): baseline in `CLAUDE.md` §5.

**2026-10-10 — PHASE-00 started on the Mac.** Branch cloned (`cross-platform` on the
fork), venv on Homebrew Python 3.12.15 with pyobjc 12.2.2, offline suite 825 passed.
The mods were placed in the session's hot-reload folder. `devtools/live_smoke.py`,
`tests/live/` and `devtools/macos_probe.py` written. Pairing facts measured (2.4):
HTTP pairs with V5.2; V5.2's mailbox is the legacy `~/AppData/Local/...` directory,
which it creates itself. Canvas saved to a backup `.pkt` before the fixture build;
clearing the canvas and the AX/click/capture steps wait on the user (FUTURE_WORK §0).

**2026-10-10 — PHASE-01 and PHASE-02 completed on the Mac.** Platform layer (2.5), then
pairing on every OS (2.6): the server follows the extension's heartbeat across mailbox
candidates, `main.js` fixed, and a `.pts` built on the Mac with PT's module editor and
installed in place of V5.2 with the user's OK. Nothing committed (the user asked for no
commits).

**2026-10-10 — PHASE-03 completed (new session).** The mods were copied into this session's
hot-reload folder. The presenter now speaks only `WindowBackend` and finds widgets through
`locators`; Windows' `win32.py`/`uia.py` moved under `ui/backends/windows/` byte-identical;
other OSes get a `NullBackend` with the reason. Suite 1028 passed. Details in 2.7.

**2026-10-10 — PHASE-04 built by a parallel session, PHASE-05 built and run live (this
session).** A second Claude session on this Mac wrote `backends/macos/` (permissions,
windows, capture, `MacBackend`), the dependency markers and five test files, and ticked two
PHASE-04 boxes; the user then gave PHASE-04 to this session, which re-verified its capture box
and continued. PHASE-05: AX walk shared with the probe, locator fallback, HID click and
keyboard section switch, three live bugs found and fixed, `tests/live/ui.json` 8/8. Details
in 2.8 and 2.9.

**2026-10-10 — First commit and push of the branch's work.** With the user's OK, everything
since `0bc0976` was committed as `f86cfe9` (author Haziq, no AI attribution; the user's home
path redacted to `~` in two plan docs first) and pushed to `haziqlandge/MCP-Packet-Tracer`
`cross-platform`. CI run 38059124205: all 6 jobs green; the install logs show comtypes only
on Windows and pyobjc only on macOS, so the environment markers work. That closed the CI
boxes of PHASE-01, 03, 04 and 05; PHASE-05 complete.

---

# Part 2 — Findings that must not be re-derived

## 2.1 The file mailbox is mis-addressed on macOS and Linux (code reading, not yet measured)

`mcpBridgeDir()` in `EXTENSION/script-engine/main.js:121-129` takes the
directory of the first token candidate, `<home>/AppData/Local/...`, without
checking that a token exists there. Python writes to
`~/.local/state/packet-tracer-mcp/bridge` on POSIX. HTTP pairing is unaffected,
because `getMcpToken()` does check `fileExists` on each candidate. Read on
2026-10-10 at `bcb2ef3`. PHASE-00 confirms it live. The design that follows is
`PLAN/INTERFACES.md` §5.

## 2.2 This fork has never rebuilt the `.pts`

`git log -- EXTENSION/script-engine/main.js` shows only `ad59a02` (reorganise
into `EXTENSION/`) and `442adef` (English comments). Whatever runs in users'
PT is upstream's V5.2 build. That is why the plan makes the server adapt to the
extension (C5) instead of depending on a new build.

## 2.3 Qt's macOS bridge exposes objectName paths only in recent Qt

qtbase `dev` implements `accessibilityIdentifier` as
`QAccessibleBridgeUtils::accessibleId(iface)`. The 5.15 and 6.2 branches do not
implement it (RESEARCH S4, S5). Whether PT's bundled Qt has it is PHASE-00's
open question.

## 2.4 PHASE-00 measurements on the Mac (2026-10-10)

Answers to `RESEARCH/SYNTHESIS.md` §9, measured on the executor Mac. "Pending"
means not measured yet; the reason is given.

| # | Answer | Evidence |
|---|---|---|
| 1 | macOS 26.5.1 (25F80), arm64, Mac17,9. PT 9.0.1 at `/Applications/Cisco Packet Tracer 9.0.1/Cisco Packet Tracer 9.0.1.app`, bundle id `com.netacad.PacketTracer9.0.1`. **The PT binary is universal (x86_64 + arm64)**, not x86-64 only: Rosetta is not required | `sw_vers`, `uname -m`, `sysctl hw.model`; `file .../Contents/MacOS/PacketTracer` |
| 2 | Qt **6.8.7**. **`AXIdentifier` is populated with the same dotted objectName paths as Windows' AutomationId** (104 of 111 main-window nodes; e.g. `PtApp.CAppWindowBase.m_pPlToolBar.QToolButton`, `...m_PLFrame.m_logicalSwitch`). The macOS tree is **flat** (max depth 3): Qt's bridge skips plain container widgets. The logical canvas appears only as the `AXGroup` `...m_pViewArea_Window.m_workspaceWS` (frame 0,180 1512×526 pt) with one child "Workspace Description"; there is **no `CLogicalWorkspace.QWidget` element and no canvas scroll bars**, so the `logical_canvas` and `canvas_hbar`/`vbar` locators need a macOS `by_shape` (PHASE-05). The whole walk takes ~25 ms | `QtCore.framework/Resources/Info.plist`; `tests/fixtures/macos/main-window.json` (`macos_probe ax`) |
| 3 | `getUserFolder()` = `~/Cisco Packet Tracer 9.0.1` (forward slashes, directly under home, so `main.js`'s home derivation gives `~`). `getDefaultFileSaveLocation()` = `<user folder>/saves` | `pt_send_raw` through `live_smoke` |
| 4 | Released V5.2 polls **`~/AppData/Local/packet-tracer-mcp/bridge`** (`fileBridgeStatus().dir`), while it finds the token in its 2nd candidate `~/.local/state/packet-tracer-mcp/bridge_token`. V5.2's search list is `AppData/Local`, `.local/state`, `.packet-tracer-mcp` (no Application Support). **`fm.makeDirectory` creates missing parents**: `~/AppData` renamed away at 14:50:47, the whole chain plus `alive.txt` was back by 14:50:52, mode **0755**. The server therefore does not need to pre-create the legacy directory (`INTERFACES.md` §5 condition not met) | `pt_send_raw` `fileBridgeStatus()`, `getMcpTokenInfo()`; `stat` before/after the rename (old tree left at `~/AppData.phase00-renamed`) |
| 5 | **HTTP pairing works with V5.2 as-is**: `pt_bridge_status` "CONNECTED over HTTP", `pt_query_topology` returned 10 devices / 7 links | `live_smoke` from this checkout |
| 6 | **Tabs**: `AXRadioButton` (title Physical/Config/CLI/Desktop/Services/Attributes) inside an `AXTabGroup`, action `AXPress` works. **Select tool**: `AXCheckBox` titled `Select (Esc)`, value `1` when active, `AXPress`. **Desktop app buttons**: `AXButton`, ident `...m_desktopFrame.<App>Btn` (e.g. `CommandPromptBtn`, `WebBrowserBtn`, `EmailBtn`), `AXPress` opens the app. **Config/Services sections** (Settings, FastEthernet0, DHCP, HTTP…): **checkable** `AXCheckBox`; `AXPress` maps to Qt's `toggle()` and flips the check **without** switching the panel (PT listens to `clicked()`). Focusing the element (`AXFocused` = True) and posting Space to the pid switches it, **but only while PT is frontmost** (with Claude frontmost the panel did not change). **Applets**: identical idents to Windows (`CDesktopApplet...m_titleBar.m_titleLabel`/`m_closeButton`; Email: `m_titleFrame.m_titleLable`/`m_closeBtn`); a closed applet leaves the AX tree; nested applets close **innermost (last) first**: Email showed 2 closers → 1 → 0, while pressing the first closer did nothing. **Consoles**: `AXTextArea` ending `CCommandLine`, no scroll-bar element. **Web Browser**: `AXTextField` `...m_urlEdit`, `AXButton` `...m_goButton`. **Logical canvas**: `AXGroup` `m_workspaceWS`, no actions, no scroll bars (#2) | 8 fixtures in `tests/fixtures/macos/`; `macos_probe press`; captures |
| 7 | **`CGEventPostToPid` mouse clicks never open a device dialog**: 5 variants failed (plain; with `kCGMouseEventWindowUnderMousePointer[ThatCanHandleThisEvent]` = main CGWindowID; with `kCGMouseEventClickState` = 1 and a preceding mouse-move; PT in the background and frontmost). The **HID route works**: activate PT, `AXRaise` its main window, `CGEventPost(kCGHIDEventTap)` down/up, `CGWarpMouseCursorPosition` back (~0.52 s; R1, PC1, SRV1 all opened; a hidden dialog re-shows). Scene coordinates map 1:1 to points from the canvas origin at zoom 0 (R1 scene 299,150 → screen 299,330 with the canvas at 0,180); `centerOnComponentByName` does not scroll when the scene fits. **Device dialogs all open at the same frame** (406,103 700×708) | `macos_probe click --route pid|pid-fields|post`; AX window list before/after |
| 8 | Without Screen Recording every route fails cleanly (None; `screencapture` rc=1; SCK -3801). **With the grant all three routes capture a covered window correctly**: R1's dialog under PC1 and SRV1 gave identical pixels from SCK, `CGWindowListCreateImage` and `screencapture -l` (100 % of sampled pixels equal), 1400×1416 px for 700×708 pt. Timings: SCK ~235 ms, CGImage ~165 ms, screencapture ~175 ms. CGImage rows are **padded** (5632 bytes per row for 1400 px) with bitmap info 8194 (BGRA, little-endian, premultiplied first); ImageIO read-back of `screencapture` is RGBA (info 3). **SCK traps**: a CLI process must call `NSApplication.sharedApplication()` first, or SCK aborts the process (`CGS_REQUIRE_INIT` assertion); the screenshot handler gets the CGImage as a raw pointer (no block metadata) that must be wrapped with `objc.objc_object(c_void_p=ptr.pointerAsInteger)` **inside** the callback; any exception inside a completion block terminates the process | `macos_probe capture`; pixel comparison of the three PNGs |
| 9 | Processes started from the Claude desktop app's Code tab are attributed by TCC to the **bundled Claude Code CLI**, `~/Library/Application Support/Claude/claude-code/2.1.293/<hash>/claude.app/Contents/MacOS/claude`, not to `Claude.app`: the chain is Python → zsh → claude → `Claude.app/Contents/Helpers/disclaimer` → Claude, and the disclaimer helper hands responsibility down. The path is **versioned**, so a grant may not survive a Claude Code update (to measure). The plan's ppid heuristic reported `Python` (Homebrew's `Python.framework/.../Python.app`) until it skipped that bundle. **Grants take effect without a restart**: after the user granted Accessibility and Screen Recording, the same CLI process (pid unchanged) passed all three preflights and AX/capture worked | `macos_probe perms` (`chain`, `tcc_responsible` from libSystem `responsibility_get_pid_responsible_for_pid`) |
| 10 | cwd of the client-launched MCP server (Claude desktop, Code tab) = the session folder (`~/packet tracer`), not `/`: `pt_screenshot` wrote `~/packet tracer/projects/...`. PATH: not measured (process-environment inspection was refused by the session's safety classifier); the MCP config uses an absolute venv interpreter, so PATH does not affect the launch here | `pt_screenshot` through the session's own `packet-tracer` server |
| 11 | The application firewall is **off** on this Mac (`socketfilterfw --getglobalstate`: State = 0), so no prompt can appear here; the bridge binds `127.0.0.1:54321` only. Measuring with the firewall on would mean changing a security setting: not done | `socketfilterfw`, `lsof -iTCP:54321` |
| 12 | Pending: no `.pts` built in this session. An earlier local audit (2026-10-09, outside this repo) proposed Cisco's module-editor route (replace `main.js` with `#include "<abs path>/main.js"`, save a new `.pts`, expand includes) and reported PT crashing in `libqcocoa`/`NSAccessibility` when the editor was driven by accessibility automation. Unverified here | — |

**Live smoke on the Mac (2026-10-10, HTTP channel, released V5.2, this checkout's
code through `devtools/live_smoke.py`).** The user approved clearing the canvas
(backup `~/packet tracer/backups/pre-phase00-canvas-2026-10-10.pkt`); the fixture
topology is saved as `~/packet tracer/projects/phase00-fixture.pkt`.

- `tests/live/setup.json`: **11/11 ok**. R1, SW1, PC1, SRV1 created (PT adds a
  Power Distribution Device), 3 links, R1 Gi0/0 192.168.10.1/24 up through `pt_cli`,
  PC1 .11 and SRV1 .10 static; `pt_query_topology` read back 5 devices / 3 links.
- `tests/live/headless.json`: **18/18 pass**, no `Traceback`/`NameError`/`PT_ERROR`/
  `EXCEPTION`: estimate, bridge status, export (5 devices, 3 links), modules for
  2911 (127), ACL/NAT/VLAN dry runs valid, `pt_read_vlans` SW1 (5 factory VLANs),
  audit R1 (not secure: 1 high, 1 medium, 2 low), inspect R1 Gi0/0 up, health
  clean, packet trace (realtime, 0 events), screenshot PNG 13,705 bytes, metadata
  (PT 9.0.1.0858), DHCP pool on SRV1 (50 addresses, service on), QoS read, PC1 panel,
  `show ip interface brief` on R1. The Windows reference list passes the same way.
- `pt_bridge_status` also reports "the file-bridge has not reported a heartbeat
  yet": the Python side of X1 (it watches `~/.local/state/.../bridge`).

Other facts measured on the way:

- **PT listens on `*:39000`** (IPv6, all interfaces). That is the MCP server's default
  streamable-HTTP port (`server.py` `TRANSPORT_PORT`): `python -m packet_tracer_mcp`
  without `--stdio` cannot bind while PT runs. stdio clients are unaffected
  (`lsof -iTCP:39000`; ISSUES X8).
- The client's `packet-tracer` server on this Mac runs from a separate checkout
  (`~/MCP-Packet-Tracer`, local branch `macos-support`), and a server from that checkout
  started with `--port 39002` owns the bridge port 54321. `live_smoke` from this checkout
  pairs through it (same token file).
- The offline suite on the Mac: 825 passed (baseline in `CLAUDE.md` §5).

pyobjc names exercised by `devtools/macos_probe.py` on this Mac (C6), all
resolved at runtime on macOS 26.5.1 with pyobjc 12.2.2:

- ApplicationServices: `AXIsProcessTrustedWithOptions`, `kAXTrustedCheckOptionPrompt`,
  `AXUIElementCreateApplication`, `AXUIElementSetMessagingTimeout`,
  `AXUIElementCopyAttributeValue` (returns `(err, value)`).
- Quartz: `CGPreflightScreenCaptureAccess`, `CGPreflightPostEventAccess`,
  `CGWindowListCopyWindowInfo`, `kCGWindowListOptionAll`, `kCGNullWindowID`,
  `kCGWindowOwnerPID`, `kCGWindowNumber`, `kCGWindowName`, `kCGWindowLayer`,
  `kCGWindowIsOnscreen`, `kCGWindowBounds` (a dict with `X`, `Y`, `Width`, `Height`),
  `CGWindowListCreateImage`, `CGRectNull`, `kCGWindowListOptionIncludingWindow`,
  `kCGWindowImageBoundsIgnoreFraming`, `kCGWindowImageBestResolution`
  (still callable on 26.5.1; it returns None without Screen Recording).
- ScreenCaptureKit: `SCShareableContent.getShareableContentWithCompletionHandler_`
  (the handler runs on a background thread; a `threading.Event` wait works).

Exercised after the grants (same date, all resolved and behaved as recorded above):

- ApplicationServices: `AXValueGetValue` with `kAXValueCGPointType` /
  `kAXValueCGSizeType` (returns `(ok, value)`), `AXUIElementCopyActionNames`
  (returns `(err, names)`; checkable buttons list `AXPress` twice),
  `AXUIElementPerformAction`, `AXUIElementSetAttributeValue` (`AXFocused`),
  `AXUIElementCreateSystemWide`, `AXUIElementCopyElementAtPosition`; attributes
  `AXWindows`, `AXChildren`, `AXRole`, `AXSubrole`, `AXTitle`, `AXDescription`,
  `AXIdentifier`, `AXValue`, `AXPosition`, `AXSize`, `AXFocused`, `AXParent`.
- Quartz events: `CGEventCreateMouseEvent`, `kCGEventLeftMouseDown`/`Up`,
  `kCGEventMouseMoved`, `kCGMouseButtonLeft`, `CGEventPostToPid`, `CGEventPost`,
  `kCGHIDEventTap`, `CGEventCreate`, `CGEventGetLocation`, `CGWarpMouseCursorPosition`,
  `CGEventSetIntegerValueField`, `kCGMouseEventWindowUnderMousePointer`,
  `kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent`,
  `kCGMouseEventClickState`, `CGEventCreateKeyboardEvent` (keycode 49 = Space).
- Quartz images: `CGImageGetWidth`/`Height`/`BytesPerRow`/`BitmapInfo`,
  `CGImageGetDataProvider`, `CGDataProviderCopyData`, `kCGBitmapAlphaInfoMask`,
  `kCGBitmapByteOrderMask`, `kCGBitmapByteOrder32Little`,
  `kCGImageAlphaPremultipliedFirst`/`First`/`NoneSkipFirst`,
  `CGImageSourceCreateWithURL`, `CGImageSourceCreateImageAtIndex`; Foundation
  `NSURL.fileURLWithPath_`.
- ScreenCaptureKit: `SCShareableContent.windows()`, `SCWindow.windowID()`/`frame()`,
  `SCContentFilter.alloc().initWithDesktopIndependentWindow_`,
  `SCStreamConfiguration.alloc().init()`, `setWidth_`, `setHeight_`,
  `setShowsCursor_`, `SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_`;
  `objc.objc_object(c_void_p=...)` for the raw CGImage pointer.
- AppKit: `NSApplication.sharedApplication`, `NSScreen.mainScreen().backingScaleFactor()`
  (2.0 here), `NSRunningApplication.runningApplicationWithProcessIdentifier_`
  (`bundleURL`, `activateWithOptions_`), `NSWorkspace.sharedWorkspace()`
  (`frontmostApplication`, `runningApplications`).

- Permission requests: `CGRequestScreenCaptureAccess`, `CGRequestPostEventAccess` and
  `AXIsProcessTrustedWithOptions` with the prompt option True all returned True with
  the grants already in place, and showed no dialog (`macos_probe perms --request`).

## 2.5 PHASE-01: the platform layer (2026-10-10, closed ISSUES X2, X6, X7)

- `infrastructure/platform/` (base, paths, clipboard, output, host, `current()`) is the
  one home of OS facts. A grep test (`test_os_checks_confined.py`) enforces C1; its only
  allow-list entry is `infrastructure/ui/win32.py` until PHASE-03.
- **X6 closed:** `XDG_STATE_HOME` is no longer honoured (`paths.state_dir`); the token
  stays in `~/.local/state/packet-tracer-mcp` on macOS/Linux. Windows is byte-identical to
  the old `token_dir()` for every env combination (test). The XDG test failed before
  (token under `$XDG_STATE_HOME`).
- **X2 closed:** `pt_deploy` copies through `platform.current().clipboard`. Measured live:
  bare `pbcopy` started without a locale mangles UTF-8 into Mac Roman (`h√©llo`), while
  ours (`LC_CTYPE=UTF-8` always set) round-trips `héllo PC-Ñandú-é` even under `env -i`.
  The PTBuilder script itself is ASCII (`json.dumps` escapes), so the deploy path never
  carries raw non-ASCII; the fix matters for any other text.
- **X7 closed:** relative output folders resolve under `output_root()`; the executors and
  `ProjectRepository` do it themselves (`output_root() / Path(dir)`), so absolute paths and
  the tool call sites stay as they were (and `test_full_build`'s source assertion holds).
  Live from the client's cwd, export and screenshot report absolute paths there.
- Deviations recorded in INTERFACES §1 (amendment "as built"): `responsible_bundle()`,
  outermost-`.app` walk, `pgrep -x PacketTracer` on macOS.
- Suite: 906 passed on the Mac (baseline 825). Remote CI not run (nothing pushed).

## 2.6 PHASE-02: pairing on the Mac (2026-10-10)

- **Server side follows the heartbeat.** `FileBridge` holds `mailbox_candidates()` and
  picks the freshest live `alive.txt` on every send (`active_dir()`); `mailbox_status()`
  feeds a `pt_bridge_status` line that flags the legacy directory. Tests:
  `test_file_bridge_discovery.py` (15), all failing first (no `candidates=` API).
- **Live, released V5.2, Control Center closed** (closed through its AX close button,
  reopened with the extension's own `startBridge()` sent over the file channel):
  `pt_bridge_status` → "CONNECTED over file-bridge … file mailbox:
  ~/AppData/Local/packet-tracer-mcp/bridge (legacy location polled by the released V5.2
  extension)"; `pt_query_topology` answered in ~2 s; `tests/live/headless.json` 18/18 over
  the file channel. ISSUES X1 is fixed server-side for users of the released `.pts`.
- **The 10-second gap (ISSUES X10).** Right after the window closes, the bridge still
  reports the webview as connected for 10 s, so a command sent then goes to HTTP and
  times out. Measured: ~3 s after closing → timeout; at 33 s → answered over the file
  channel.
- **`main.js` before the fix** (`tests/test_main_js_paths.py` under node 26.11.1, Homebrew):
  `5 failed, 1 passed`. macOS user folder with the token in `.local/state` → bridge dir
  `/Users/u/AppData/Local/packet-tracer-mcp/bridge` (expected `.local/state/...`);
  backslashed Windows user folder → `''`; Linux `/home/u/pt` → `/home/u/AppData/Local/...`;
  user folder under `~/Documents` → `/Users/u/Documents/AppData/Local/...`; no token →
  `/Users/u/AppData/Local/...` instead of the OS default. Only the Windows case passed.
- **Released V5.2's `main.js` is the tracked `main.js`.** Read out of PT's module editor:
  251 code lines, identical after stripping comments; only the comments differ (V5.2 has
  the Spanish originals). DATA.md's "not necessarily equal" is resolved.
- **A `.pts` can be built on the Mac (SYNTHESIS §9 #12).** Route, all driven through AX:
  Extensions → Scripting → Configure PT Script Modules (menu item `AXPress`) → select the
  `MCP-BUILDER` row (`com.matsoto.mcpbuilder`) → Edit → window "Scripting - MCP-BUILDER
  (Running)" → Script Engine tab → select `main.js` → set the editor's `AXValue`
  (`...ScriptEditor.textEditor`, settable; the module keeps the text when switching files)
  → Info tab → **Export** (not Save: Save writes the installed module's own file) → native
  save panel (`saveAsNameTextField`, default folder `~/Cisco Packet Tracer 9.0.1/extensions`)
  → "Script module saved." Closing the editor asks whether to drop unsaved changes to the
  persistent module; Yes keeps the installed `.pts` as it was. Built:
  `~/Cisco Packet Tracer 9.0.1/extensions/MCP-BUILDER-mailbox-fix.pts` (126,491 bytes; V5.2
  is 125,552). **Not yet installed or tested** (it would replace the user's V5.2).
- The editor's file list ignores `AXPress`, `AXSelectedRows` and arrow keys; only a real
  click (the cursor-restoring HID route) changes the file shown. PT did **not** crash under
  AX automation of the module editor on 9.0.1 / macOS 26.5.1, contrary to the earlier local
  audit's report.
- **The fixed `.pts` is installed on the Mac** (user's OK; Remove + Add + Launch in PT's module
  list). The extension then reports `fileBridgeStatus().dir` = `~/.local/state/packet-tracer-mcp/bridge`
  and searches `.local/state` first for the token; `pt_bridge_status` shows "file mailbox:
  ~/.local/state/packet-tracer-mcp/bridge" with no legacy note, and with the window closed
  `pt_open_project` + `pt_query_topology` answered over the canonical mailbox (PHASE-02 box).
  Still so at the start of the PHASE-03 session (`live_smoke`, same line). The fixed `.pts`
  is not in Releases: shipping it is the user's call (ISSUES X3).

## 2.7 PHASE-03: the UI backend seam (2026-10-10)

- **The two Windows files moved untouched.** `git diff -M bcb2ef3 --stat -- '**/win32.py' '**/uia.py'`:
  ```
  src/packet_tracer_mcp/infrastructure/ui/{ => backends/windows}/uia.py   | 0
  src/packet_tracer_mcp/infrastructure/ui/{ => backends/windows}/win32.py | 0
  2 files changed, 0 insertions(+), 0 deletions(-)
  ```
  Both renames at similarity index 100 %. Neither file has a relative import, so not even an
  import line changed. (The renames are staged by `git mv`; nothing is committed.)
- `presenter.py`: `grep -n "win32\|uia\|UIA_\|automation_id"` → nothing. The C1 allow-list is
  empty.
- **`WindowsBackend` builds a `Uia()` per call**, as the old presenter did per method: `Uia()`
  runs `CoInitializeEx` on the calling thread, and FastMCP runs sync tools on worker threads,
  so one cached `Uia` would hit an uninitialised COM thread. Roles come from `u.m`'s
  `UIA_*ControlTypeId` at runtime (no hard-coded ids); a role filter passes the same UIA type
  name the old `descendants(h, "TabItem")` calls did. `uia` exceptions pass through unchanged
  (not wrapped in `BackendError`) so the notes the tools print on Windows read as before.
- **`UiElement.rect` is a property over `bounds`** (a tuple or a reader). UIA reads every rect
  cross-process and the presenter needs only the canvas's; reading all of them eagerly would
  add a fifth COM call per element to every walk. INTERFACES §2 amended.
- `select_tool` is a name match, so its `by_shape` repeats the name predicate: with an empty
  ident (`locate()` skips `by_ident` then) the Select tool must still be found, or the Delete
  guard would refuse every click on an OS that exposes no ident for it.
- `Presenter(send, *, sleep, clock, backend)`: `clock` (default `time.monotonic`) lets the
  window waits run on a fake clock; `backend` defaults lazily to
  `platform.current().ui_backend()` (cached on the frozen `Platform` through a
  `compare=False` field). `scroll_consoles(hwnd)` lost its `u` argument. `pt_ui_mode("ui")` is
  the one caller of `available(request=True)` (C3); status and every tool use `request=False`.
- Deviation from "existing UI tests: import paths only": `test_device_panel.py`'s
  `TestOpenApp` fake now speaks `elements`/`press`/`ident` (its six assertions unchanged), and
  the two `FakePresenter`s gained `available()`, since `pt_ui_mode` asks the presenter's
  backend instead of a module-level Windows check.
- Tests: `test_locators.py` 23, `test_backend_selection.py` 27, `test_windows_backend.py` 13
  (fake `Uia`), `test_presenter_on_backend.py` 35, `test_imports_every_os.py` 3 (fresh
  interpreter per faked `sys.platform`, comtypes/pyobjc blocked; an `import objc` planted in
  `backends/null.py` failed all three). Suite 927 → 1028.
- Live (Mac, file channel): `pt_ui_mode("status")` → "PT GUI: NOT available (UI mode is not
  available on macOS yet: its backend is still being built; every tool works headless.)";
  `pt_cli(show=True)` ran and appended "GUI: could not show it (<that reason>). The work was
  still done through the API." Windows: unverified until `FUTURE_WORK.md` §2 (ISSUES X5).

## 2.8 PHASE-04: the macOS backend's windows, capture and permissions (2026-10-10)

Built by the parallel session (files dated 18:58–19:04); reviewed and re-verified here.

- `backends/macos/`: `permissions.py` (preflight-only `state()`, `request()` at most once
  per permission per process, `remedy()` naming the pane, the app and its full path, "no
  restart needed"), `windows.py` (AX ↔ CG join by frame ±1 pt, CG name = AX title first,
  then on-screen; dialogs match by exact title, the main window by prefix), `capture.py`
  (SCK → `CGWindowListCreateImage` → `screencapture -l`; `to_bgra` drops row padding and
  reorders by bitmap info), `backend.py` (`MacBackend`). `available()` needs pyobjc and
  Accessibility; a missing Screen Recording only blocks capture. pyobjc is imported inside
  functions (C2, held by `test_imports_every_os.py`).
- Dependencies: comtypes (win32) and five pyobjc packages ≥ 12.2 (darwin) are core
  dependencies with markers; `[ui]` is an empty alias; classifier `Operating System :: MacOS`.
- The presenter also turns `BackendError` into `PresenterError` (the Windows backend never
  raises it, so Windows notes are unchanged).
- Re-verified live by this session: `pt_ui_capture` main window 3024×1752 px and PC1
  1400×1416 px, not blank, right windows. Still open: permissions revoked (needs the user),
  and CI (needs a push).

## 2.9 PHASE-05: macOS navigation and open-by-click (2026-10-10)

- **One AX walk.** `backends/macos/ax.py` `walk()` produces fixture-format nodes; the probe's
  `dump_tree` is now `ax.walk(root, redact=_redact)` (live: PC1 49 nodes in 23 ms, passes the
  fixture-format check). `elements_from_tree` converts in UIA's order (parents first, the
  window excluded). Role map from the fixtures: AXRadioButton is a TAB only inside an
  AXTabGroup (SRV1's DHCP On/Off are not tabs); applet title labels carry their text in
  `AXDescription`.
- **Locator fallback.** On macOS the canvas exists under another objectName
  (`...m_pViewArea_Window.m_workspaceWS`), so PHASE-03's "by_shape only for empty idents"
  could never reach it. `locate_all` now gives `by_shape` a second pass over elements with
  an ident, **only when the first pass found nothing**: Windows matches exactly what it did
  (tested with the mac name listed first).
- **Click route: `cursor-restored`, always.** Evidence: PHASE-00's five posted variants all
  failed (2.4 #7); every live open by click here went through `events.click` (activate PT,
  `AXRaise` main, wait ≤ 1.5 s for PT frontmost, hit-test until PT's canvas is under the point
  ≤ 1 s, HID down/up, warp back). Step text: "click sent; the cursor moved there for a moment
  and was put back".
- **Three live bugs, each with a test that failed first.** (1) PT reports frontmost before its
  windows are raised over Claude's: the first hit test saw Claude's window and the click was
  (rightly) refused; the hit test is now polled. (2) A section's `AXValue` turns 1 about
  0.15 s after Space (measured 0 at 0.02 s, 1 from 0.17 s); now polled ≤ 1 s, and a section
  already checked is not pressed. Sections all read 0 right after a dialog opens: "checked"
  follows a click, not the panel shown by default. (3) A device outside the view: with no
  scroll bars to read (macOS exposes none, even when the scene does not fit), the recomputed
  point after `centerOnComponentByName` stayed stale and off-screen (the guard refused);
  the presenter now clicks the view's centre in that case. With bars (Windows) the
  recomputed point is used as before (tested).
- **Calibration holds in points on Retina (scale 2).** SRV1 moved to the four canvas corners
  (centres 40,40 / 1470,40 / 40,490 / 1470,490): each opened on the first click at
  canvas origin + scene centre (e.g. 1470,670). `moveToLocation(x, y)` puts the centre at
  (x + 28, y + 26) for a Server-PT. SRV1 restored to 398,450 after every test.
- **Section switch.** Checkable sections in a device dialog go through
  `events.press_by_keyboard` (activate, `AXFocused`, Space to the pid) and are verified checked;
  the main window's Select tool keeps `AXPress`. URL field: `AXValue` set directly worked.
  Console scroll bars: an `AXScrollBar` with `CCommandLine` in its ident appears live once
  the console overflows ("console scrolled to the end"), though none is in the recordings.
- **Timings** (PHASE-05 box): HTTP open-existing 0.34–0.49 s, by click 0.84–1.21 s, capture
  0.31–0.39 s, AX walks 18–32 ms. Over the file channel one JS round trip took 0.21–1.42 s,
  which pushed two open-existing runs to 1.68 s and 1.84 s (ISSUES X14).
- Probe: `hit --x --y` added (read-only) so `AXUIElementCreateSystemWide`,
  `AXUIElementCopyElementAtPosition` and the `AXParent` climb are exercised there (C6).
- `devtools/live_smoke.py` prints `----- <seconds> s` after each call.

## Where the detailed evidence lives

| Artifact | Contents |
|---|---|
| `RESEARCH/INDEX.md` | Sources S1–S11, graded |
| `RESEARCH/SYNTHESIS.md` §9 | The 12 questions PHASE-00 answers |
| `tests/fixtures/macos/` | AX recordings (from PHASE-00) |
