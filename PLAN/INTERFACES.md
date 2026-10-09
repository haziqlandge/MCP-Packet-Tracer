# INTERFACES

The authoritative definition of the new boundaries. Phase files cite it by
section. Existing interfaces (`BridgeContext`, `PanelSupport`, the tool API in
`tests/fixtures/tool_api.json`) keep their signatures (`CONSTRAINTS.md` C9).

## 1. Platform layer (`infrastructure/platform/`)

```python
OsName = Literal["windows", "macos", "linux", "other"]

def detect_os(sys_platform: str | None = None) -> OsName
    # "win32"/"cygwin" -> windows; "darwin" -> macos; startswith("linux") -> linux; else other

@dataclass(frozen=True)
class HostInfo:
    os: OsName
    os_version: str      # platform.mac_ver()[0] | platform.version() | platform.release()
    arch: str            # platform.machine(): "arm64", "x86_64", "AMD64"
    python: str          # platform.python_version()

class Clipboard(Protocol):
    name: str                          # "clip.exe" | "pbcopy" | "wl-copy" | "xclip" | "xsel" | "none"
    def copy(self, text: str) -> bool  # never raises; False when there is no tool or it failed

@dataclass(frozen=True)
class Platform:
    host: HostInfo
    state_dir: Path
    clipboard: Clipboard
    def ui_backend(self) -> "WindowBackend"    # lazy, cached; §2

def current() -> Platform          # process-wide cache
def reset_current() -> None        # tests only

# paths.py: pure, everything injected
def state_dir(os_name: OsName, env: Mapping[str, str], home: Path) -> Path      # §5
def mailbox_candidates(os_name: OsName, env: Mapping[str, str], home: Path) -> list[Path]  # §5

# clipboard.py
def clipboard_for(os_name: OsName, *, which=shutil.which, env=os.environ,
                  run=subprocess.run) -> Clipboard
    # windows: clip.exe, UTF-16-LE (as deploy_executor does today)
    # macos:   pbcopy, UTF-8, env with LC_CTYPE=UTF-8 added (SYNTHESIS §6)
    # linux:   wl-copy if WAYLAND_DISPLAY is set and it exists, else xclip -selection clipboard, else xsel -b
    # none found -> NoClipboard (copy() returns False)

# output.py
def output_root(*, cwd: Path | None = None, env=os.environ, home: Path | None = None,
                os_name: OsName | None = None) -> Path
    # PT_MCP_OUTPUT_DIR if set; else cwd if it is writable and not a filesystem root;
    # else home/"Documents"/"Packet Tracer MCP" (windows, macos) or home/"packet-tracer-mcp"
def output_dir(name: str, fallback: str) -> Path
    # output_root() / safe_name_component(name, fallback=fallback); replaces every
    # `Path(safe_name_component(output_dir, ...))` at the tool sites (C11)

# host.py
def host_info() -> HostInfo
def pt_processes() -> list[int]                        # PIDs of running PT; [] when unknown
def responsible_app(pid: int, *, ps=...) -> str | None
    # macOS: walk the ppid chain; the first ancestor whose executable path contains
    # "/<Name>.app/Contents/MacOS/" gives "<Name>"; None elsewhere or when unknown
```

**Error contract.** Platform functions never raise for a missing tool or an
unknown environment. They return `False`, `None` or `[]`. Creating directories
is the caller's job (`bridge_token`, `file_bridge`, the tools).

## 2. UI backend (`infrastructure/ui/backend.py`)

```python
class Role(str, Enum):
    TAB = "tab"; BUTTON = "button"; CHECKBOX = "checkbox"; LIST_ITEM = "list_item"
    EDIT = "edit"; SCROLLBAR = "scrollbar"; STATIC = "static"; WINDOW = "window"; OTHER = "other"

@dataclass
class UiElement:
    raw: object                        # backend handle; never leaves backend + presenter
    name: str                          # visible text
    ident: str                         # Qt objectName path; "" when the platform does not expose it
    role: Role
    offscreen: bool
    rect: tuple[int, int, int, int]    # left, top, right, bottom; screen coords, backend units

@dataclass(frozen=True)
class Capture:
    width: int                         # pixels
    height: int                        # pixels
    bgra: bytes                        # width*4 bytes per row, top-down, B,G,R,A (png.bgra_to_png input)

WindowHandle = int                     # Windows: HWND. macOS: CGWindowID. JSON-safe on purpose

class BackendUnavailable(RuntimeError): ...   # str() is the actionable remedy (C7)
class BackendError(RuntimeError): ...         # an operation failed (element gone, action refused)

class WindowBackend(Protocol):
    name: str                                            # "windows" | "macos" | "linux" | "null"
    def available(self, *, request: bool = False) -> tuple[bool, str]
        # request=True may show OS permission prompts; only UI-mode entry points pass it (C3)
    def find_window(self, pid: int, title: str) -> WindowHandle | None
    def main_window(self, pid: int) -> WindowHandle | None
    def raise_window(self, handle: WindowHandle) -> None
    def capture(self, handle: WindowHandle) -> Capture
    def click(self, handle: WindowHandle, x: int, y: int) -> str   # "posted" | "cursor-restored"
    def elements(self, handle: WindowHandle, role: Role | None = None) -> list[UiElement]
    def select(self, el: UiElement) -> None                       # a tab
    def press(self, el: UiElement) -> None                        # button, list item, checkbox, toggle
    def toggle_state(self, el: UiElement) -> int                  # 0 off, 1 on, 2 indeterminate
    def range_value(self, el: UiElement) -> float
    def set_value(self, el: UiElement, text: str) -> None
    def scroll_to_end(self, el: UiElement) -> None

# backends/__init__.py
def load_backend(os_name: OsName | None = None, env=os.environ) -> WindowBackend
    # PT_MCP_UI_BACKEND in {"null","windows","macos","linux"} overrides; an unknown value
    # or a backend whose import fails -> NullBackend carrying that reason
```

**Units (C10).** Windows: physical pixels (the process is per-monitor DPI aware,
`win32.py`). macOS: points for `rect` and `click`, pixels for `Capture`. The
presenter does its arithmetic in backend units and never mixes `rect` with
`Capture` dimensions.

**Role mapping.** Windows (UIA control type → Role): TabItem → TAB, Button →
BUTTON, CheckBox → CHECKBOX, ListItem → LIST_ITEM, Edit → EDIT, ScrollBar →
SCROLLBAR, Text → STATIC, Window → WINDOW. macOS (AXRole, **provisional until
the PHASE-00 fixtures**): AXRadioButton under AXTabGroup → TAB, AXButton →
BUTTON, AXCheckBox → CHECKBOX, AXRow / AXCell → LIST_ITEM, AXTextField /
AXTextArea → EDIT, AXScrollBar → SCROLLBAR, AXStaticText → STATIC, AXWindow →
WINDOW.

**Error contract.** `PanelSupport.present()` already turns a `PresenterError`
into the note "GUI: could not show it (…). The work was still done through the
API." That stays. The presenter turns `BackendUnavailable` into a
`PresenterError` that carries the remedy word for word. On macOS the remedy names
the permission, the app to grant (from `responsible_app`) and the System
Settings path.

## 3. Locators (`infrastructure/ui/locators.py`)

```python
@dataclass(frozen=True)
class Locator:
    key: str
    by_ident: Callable[[UiElement], bool]                          # used when el.ident != ""
    by_shape: Callable[[UiElement, list[UiElement]], bool] | None  # fallback when ident == ""

def locate(els: list[UiElement], loc: Locator) -> UiElement | None
def locate_all(els: list[UiElement], loc: Locator) -> list[UiElement]
```

The presenter uses these keys. Each `by_ident` is today's predicate, moved
verbatim from `presenter.py` at `bcb2ef3`. `by_shape` is written in PHASE-05
from the PHASE-00 fixtures.

| Key | `by_ident` today | Used by |
|---|---|---|
| `select_tool` | name starts with `"Select ("` (a name match, kept as it is) | `_open_by_click` |
| `logical_canvas` | ident ends with `CLogicalWorkspace.QWidget` | `_open_by_click` |
| `canvas_hbar` / `canvas_vbar` | ident contains `CLogicalWorkspace.qt_scrollarea_hcontainer` / `vcontainer` and ends with `QScrollBar` | `_open_by_click` |
| `applet_title` | `applet_parts(els, APPLET_TITLES)` | `_open_app` |
| `applet_close` | `applet_parts(els, APPLET_CLOSERS)` | `_open_app` |
| `desktop_app(obj)` | ident ends with `"." + obj` (from `names.desktop_app_object_name`) | `_open_app` |
| `console_scrollbar` | role SCROLLBAR and `CCommandLine` in ident | `scroll_consoles` |
| `ident_suffix(s)` | ident ends with `s` (`m_urlEdit`, `m_goButton`) | `fill_and_go` |

Tabs, sections and `invoke_button` already match by visible name and role. They
need no locator.

## 4. External interfaces

| Producer | Consumer | Protocol | Auth | Failure behaviour |
|---|---|---|---|---|
| MCP server | PT webview | HTTP poll on `127.0.0.1:54321` | Token (unchanged) | Status reports "disconnected" |
| MCP server | PT script engine | Mailbox files (§5) | User-only directory | Heartbeat stale → HTTP only |
| macOS backend | TCC / AX / CG / SCK | pyobjc calls | Grant to the responsible app | `BackendUnavailable` with the remedy |
| Platform clipboard | `clip.exe` / `pbcopy` / `wl-copy` / `xclip` / `xsel` | stdin pipe, 5 s timeout | none | `copy()` → False; deploy says "copy by hand" |
| `pt-mcp doctor` | user | stdout text or `--json` | none | Exit code 1 when a required check fails |

## 5. Pairing contract (both sides must agree, C5)

**State directory** (`paths.state_dir`):

- windows: `%LOCALAPPDATA%\packet-tracer-mcp`, falling back to `%APPDATA%`, then
  `~/.packet-tracer-mcp`. This is unchanged.
- macos, linux, other: `~/.local/state/packet-tracer-mcp`. **`XDG_STATE_HOME`
  is no longer honoured**, because the extension cannot read it
  (`RESEARCH/topics/pt-on-macos.md` §3). This amends `bridge_token.py:49-51`.

**Token:** `<state>/bridge_token`. This is unchanged.

**Mailbox** (`paths.mailbox_candidates`, in order):

1. `<state>/bridge`, the canonical directory.
2. macos and linux only: `<home>/AppData/Local/packet-tracer-mcp/bridge`, the
   legacy directory that released V5.2's `mcpBridgeDir()` polls.

`FileBridge` uses the candidate whose `alive.txt` is freshest within
`HEARTBEAT_FRESH_S`. When none is fresh, it falls back to candidate 1. If
PHASE-00 shows that V5.2 cannot create the legacy directory itself, the server
pre-creates it (mode 0700) at start, on macOS and Linux only.

**Extension (fixed `main.js`).**

- Home is the first match of `^[A-Za-z]:/Users/[^/]+`, `^/Users/[^/]+`,
  `^/home/[^/]+` or `^/root` on `getUserFolder()`. Otherwise it is the parent of
  the user folder.
- Candidate order: a Windows-shaped home puts `AppData/Local/...` first,
  otherwise `.local/state/...` comes first.
- Mailbox directory = the directory of the first candidate whose `bridge_token`
  exists, plus `/bridge`. With no token anywhere, it is the OS default.
- `_fileBridgeDir` is cached only once a token has been found.

## 6. Diagnostics

`pt_bridge_status` gains one compact block (key order fixed, sent through
`reply_json`):

```json
"platform": {"os": "macos", "os_version": "14.6", "arch": "arm64",
  "state_dir": "~/.local/state/packet-tracer-mcp",
  "mailbox": {"dir": "~/.local/state/packet-tracer-mcp/bridge", "alive": true, "age_s": 0.8, "legacy": false},
  "clipboard": "pbcopy",
  "ui": {"backend": "macos", "ok": false, "reason": "...",
         "permissions": {"accessibility": false, "screen_recording": false}, "grant_to": "Claude"}}
```

Paths are shown with `~`. Permission states come from the preflight APIs only (C3).

`pt-mcp doctor [--json] [--ui] [--request-permissions] [--print-config claude-code|claude-desktop]`
prints one line per check: `id`, `ok`, `detail`, `fix`. The checks are Python
version, install, state dir writable, token present (fingerprint only), PT
running, extension heartbeat or HTTP poll seen, port 54321 free or ours,
clipboard, and UI backend and permissions. It exits 0 when every required check
passes. UI checks count as required only with `--ui`. `--print-config` prints the
MCP config snippet with the absolute `sys.executable` (SYNTHESIS §6: GUI clients
do not inherit the shell PATH).

## 7. Fixture format (`tests/fixtures/macos/*.json`)

```json
{"recorded": "YYYY-MM-DD", "macos": "14.6", "pt": "9.0.0", "qt": "6.x.y", "scale": 2.0,
 "window": {"title": "PC1", "cg_id": 1234, "frame": [x, y, w, h]},
 "tree": {"role": "AXWindow", "subrole": "", "title": "", "description": "", "identifier": "",
          "value": "(str, truncated to 200)", "frame": [x, y, w, h], "actions": ["AXRaise"],
          "children": []}}
```

Depth is capped at 40 and node count at 5,000. Tests convert a fixture to
`UiElement`s through the same `ax.to_element()` the live backend uses, so the
conversion is tested on real data (`EVALUATION.md` §2).
