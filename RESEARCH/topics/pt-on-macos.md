# Packet Tracer on macOS

What is known about running PT, and this project's extension, on a Mac.
Sources are graded in `RESEARCH/INDEX.md`.

## 1. Install location and user folder

- The app bundle lives under `/Applications/Cisco Packet Tracer <ver>/` (S1, item
  39, shows the unversioned `/Applications/Cisco Packet Tracer/Cisco Packet
  Tracer.app`). The folder name follows whatever the installer used. PHASE-00
  records the real path.
- The PT user folder is `~/Cisco Packet Tracer <ver>` on macOS, `~/pt` on Linux
  and `C:\Users\<u>\Cisco Packet Tracer <ver>` on Windows (S1, item 150, written
  for 8.2.0). `ipc.appWindow().getUserFolder()` returns it with forward slashes
  (the comment at `main.js:47`, seen on Windows).
- **Consequence.** `main.js` derives the home directory as
  `uf.substring(0, uf.lastIndexOf("/"))`. That gives `/Users/<u>` on macOS and
  `/home/<u>` on Linux, but only while the user folder sits directly under home.
  A user folder moved deeper, for example under `~/Documents`, breaks the
  derivation on every OS.

## 2. CPU architecture

PT 9.0 for macOS is reported to be an x86-64 build that runs under Rosetta 2 on
Apple Silicon (S2, S3, both Low). Rosetta does not matter to this project: the
MCP server can stay a native arm64 Python, and Accessibility, Core Graphics
events and ScreenCaptureKit are system services that work across processes of
either architecture. pyobjc ships universal2 wheels. PHASE-00 runs `file` on the
PT binary to confirm the architecture.

## 3. The two channels on macOS (repo analysis, S11)

- **HTTP (webview).** The token candidates (`main.js:44-56`) include
  `<home>/.local/state/packet-tracer-mcp/bridge_token`. That is exactly where
  Python puts the token on macOS when `XDG_STATE_HOME` is unset
  (`bridge_token.py:47-53`). HTTP pairing should therefore already work on macOS.
  It is unverified.
- **File mailbox (script engine).** `mcpBridgeDir()` (`main.js:121-129`) returns
  the directory of the **first** candidate,
  `<home>/AppData/Local/packet-tracer-mcp/bridge`, without checking that a token
  exists there. On macOS and Linux the extension therefore polls a different
  directory from the one Python writes to (`~/.local/state/packet-tracer-mcp/bridge`).
  It is unknown whether `fm.makeDirectory` creates missing parent directories.
  If it does not, the loop never gets past its first tick. Either way, the file
  channel cannot work on macOS or Linux today. The Control Center shows the
  directory it uses (`fileBridgeStatus().dir`, `main.js:113-118`). That is how
  PHASE-00 confirms it without reading the `.pts`.
- **The released `.pts`** (V5.2, in upstream's Releases) was built upstream. This
  fork has never rebuilt it: `git log -- EXTENSION/script-engine/main.js` shows only
  a refactor and a comment translation. It is unknown whether its `main.js`
  matches the tracked one, and unknown how to build a `.pts` on a Mac
  (`EXTENSION/script-engine/README.md` only says "package with the webview UI").
- **`XDG_STATE_HOME`.** Python honours it on POSIX. The extension cannot read
  environment variables through any API this repo uses, so a set
  `XDG_STATE_HOME` silently breaks pairing on Linux and macOS.

## 4. Qt version and Accessibility

- Windows UI mode finds widgets by UIA `AutomationId`, which Qt fills with the
  widget's objectName path, for example `...m_titleBar.m_titleLabel`
  (`uia.py` docstring, `presenter.py` `APPLET_TITLES`). The macOS equivalent is
  `AXIdentifier`.
- In qtbase `dev`, `accessibilityIdentifier` returns
  `QAccessibleBridgeUtils::accessibleId(iface)` (S4), which is the same
  objectName-path scheme. In 5.15 and 6.2 the method is absent (S5). The Qt
  version bundled with PT 9.0 for macOS is unknown. **If it predates the
  change, every `AXIdentifier` is empty** and the macOS backend must find widgets
  by role, visible text and position in the tree instead (`PLAN/INTERFACES.md` §3).
- `accessibilityPerformAction` maps AX actions such as `AXPress` to Qt actions in
  both old and new Qt (S4, S5). Pressing tabs and buttons does not depend on the
  Qt version.
- PHASE-00 reads the bundled version from
  `Contents/Frameworks/QtCore.framework/Resources/Info.plist` and dumps a real
  AX tree.

## 5. What is still unknown

The list lives in `SYNTHESIS.md` §9, so that it has one home.
