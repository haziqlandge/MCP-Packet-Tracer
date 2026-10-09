# SYNTHESIS

The consolidated understanding behind `PLAN/`. Numbered so that phases can cite
§n. Measurements made later go at the end as dated "Local empirical update"
sections. Do not rewrite the sections above them.

## 1. The problem, restated technically

The server is already mostly OS-neutral: planning, validation, generators and
the HTTP bridge are pure Python plus JavaScript that PT runs. What ties it to
Windows is a thin layer:

(a) the per-user state directory, where the token and mailbox live;
(b) the clipboard used by `pt_deploy`;
(c) the whole UI mode (Win32 + UI Automation, about 800 lines under
`infrastructure/ui/`);
(d) the extension's guess at that state directory from inside PT;
(e) installation steps and docs that assume Windows.

"Works out of the box on any OS" means that a user installs one package,
installs the `.pts` once, adds the MCP to their client, and both channels and UI
mode work with nothing else to configure. On macOS the only extra step is
granting two permissions the first time UI mode is used.

## 2. What the sources agree on

- PT keeps its user folder directly under home on all three OSes
  (`topics/pt-on-macos.md` §1), so a home directory derived from it is a sound
  anchor for both sides of the pairing.
- macOS has a full UIA equivalent: the AXUIElement tree with AXPress and settable
  AXValue (`topics/macos-ui-automation.md` §6). The Windows presenter's method
  (read the widget tree, act through accessibility actions, avoid the real mouse
  and keyboard) carries over.
- Every macOS GUI capability needs a TCC grant that belongs to the client app,
  not to Python (`topics/macos-ui-automation.md` §1). Onboarding must name that
  app.

## 3. Approaches and our selections

| Concern | Selected | Rejected, and why |
|---|---|---|
| Modularity | One package. Protocols per concern, backends chosen by `sys.platform` at runtime | Entry-point plugins per OS: more packaging and no benefit to the user, who asked for "connect and it works" |
| macOS bindings | pyobjc (Quartz, ApplicationServices, Cocoa, ScreenCaptureKit) | ctypes into the frameworks: SCK needs Objective-C blocks for completion handlers, and CF memory rules are easy to get wrong |
| Widget lookup | `AXIdentifier` when present, a role + text fallback otherwise (`PLAN/INTERFACES.md` §3) | Identifier only: fails outright if PT bundles an older Qt (`topics/pt-on-macos.md` §4) |
| Window handle | CGWindowID found by joining AX windows to CG windows by bounds | Private `_AXUIElementGetWindow`: undocumented. CG titles alone: empty without Screen Recording |
| Capture | SCK (14+), then CGWindowListCreateImage, then `screencapture -l` | `screencapture` alone: a process spawn per frame, and no fine control |
| Canvas click | `CGEventPostToPid`, with a cursor-restoring fallback | Real cursor only: steals the user's mouse every time |
| Mailbox pairing | Python follows the extension's heartbeat (several candidate dirs) **and** a fixed `main.js` | Fixing `main.js` alone: useless until a new `.pts` ships, and nobody knows how to build one on a Mac |
| Install | Platform dependencies as environment markers in core `dependencies` | A `[ui]` extra the user must remember. Kept only as an empty alias |

## 4. The gap, and our thesis

Upstream treats macOS and Linux as "the tests pass on Ubuntu" (`.github/workflows/tests.yml`).
No PT automation tool found drives PT's device windows on macOS. The thesis is
that UI mode is a backend detail. If the presenter only speaks a small
`WindowBackend` protocol, and widget lookup is data (locators) rather than code,
then a macOS backend reaches feature parity without a second presenter, and
Linux later becomes one more backend.

## 5. Contradictions and tensions

- **Identifier versus text.** Windows matches objectName paths. On macOS they may
  not exist. Text matching works on any Qt, but breaks if PT is localised.
  Resolution: identifiers first, text as the fallback, and locators recorded
  against real fixtures.
- **No cursor movement versus reliability.** `CGEventPostToPid` may not reach a
  Qt canvas in the background. The cursor-restoring fallback is reliable but
  visible. PHASE-05 measures both.
- **Old extension versus correct extension.** Supporting the released V5.2 forces
  Python to watch a legacy `~/AppData/Local/...` directory on a Mac. The fixed
  `main.js` makes that unnecessary, but only for new builds. Both are kept until
  a fixed `.pts` is the one in Releases.
- **Windows safety versus executing on a Mac.** The Windows backend is
  refactored on a machine that cannot run it live (`PLAN/CONSTRAINTS.md` C4).

## 6. Failure modes to design against

- Window titles read as empty without Screen Recording, so a lookup through CG
  finds nothing.
- A permission granted to the wrong app, or not yet effective until a restart.
- Padded CGImage rows or a different pixel order give a sheared or colour-swapped PNG.
- Points versus pixels give clicks at half or double the position.
- A GUI client starts the MCP with cwd `/`, or with a PATH that resolves the
  system Python 3.9.
- `pbcopy` run without a UTF-8 locale mangles non-ASCII text.
- Importing pyobjc at module load breaks Windows and Linux.

## 7. Non-negotiable design commitments

They become `PLAN/CONSTRAINTS.md` C1–C11: one home for OS checks, imports safe
everywhere, no permission prompts on headless paths, Windows backend moved and
not rewritten, both pairing sides compute the same paths, no guessed APIs,
degraded results carry a remedy, no claim without live evidence, a stable tool
API, units never mixed, and outputs never written to an unwritable cwd.

## 8. Validation strategy

Offline: the whole suite on Windows, macOS and Ubuntu CI. The macOS backend's
pure logic is tested against **AX trees recorded from the real PT** (PHASE-00
fixtures), so locator and conversion code meets reality without a live PT. Live,
on the Mac: a committed smoke harness runs the headless list and the UI list.
Out of the box: one run of the fresh-install path. The details are in
`PLAN/EVALUATION.md`.

## 9. Unresolved questions (PHASE-00 answers these)

1. Exact macOS version, Mac CPU, PT version and install path. Is the PT binary
   x86-64?
2. PT's bundled Qt version. Is `AXIdentifier` populated? Does it hold the same
   objectName path as Windows' AutomationId?
3. What `getUserFolder()` returns on the Mac.
4. Which mailbox directory the released V5.2 extension uses (Control Center
   status), and whether it can create missing parent directories.
5. Does HTTP pairing work with V5.2 as-is?
6. AX roles and actions of tabs, the Select tool, scroll bars, Desktop app
   buttons and the logical canvas.
7. Does `CGEventPostToPid` open a device dialog with PT in the background? With
   the window-number fields set?
8. Which capture route works on this macOS version, and is a covered window
   captured correctly?
9. Which app does TCC treat as responsible for the user's MCP client? Does a
   grant take effect without a restart?
10. The cwd and PATH the user's client gives the MCP server.
11. Does binding `127.0.0.1:54321` raise a firewall prompt?
12. How to build or patch a `.pts` on the Mac, if at all.
