"""macOS probe: measure what PT exposes before any backend code depends on it.

Every pyobjc selector and constant the macOS UI backend will use is exercised
here first, on the real Mac, against the real Packet Tracer (CONSTRAINTS C6).
Output is JSON so it can be pasted into PREVIOUS_WORK or committed as a fixture.

Run from the repo root (macOS only; pyobjc installed in the venv):

    python -m src.packet_tracer_mcp.devtools.macos_probe perms [--request]
    python -m src.packet_tracer_mcp.devtools.macos_probe windows --pid N
    python -m src.packet_tracer_mcp.devtools.macos_probe ax --pid N --title T --out file.json
    python -m src.packet_tracer_mcp.devtools.macos_probe click --pid N --x X --y Y [--route pid|pid-fields|post]
    python -m src.packet_tracer_mcp.devtools.macos_probe capture --wid W --route sck|cgimage|screencapture --out file.png

Units (CONSTRAINTS C10): frames and click coordinates are points; captures are pixels.
`perms` without --request only calls preflight APIs and never shows a prompt (C3).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform as _platform
import plistlib
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from ..infrastructure.platform.base import detect_os

MAX_NODES = 5000
_HOME = str(Path.home())


# -- pyobjc access, imported lazily so the module imports on every OS (C2) --------

def _q():
    import Quartz
    return Quartz


def _as():
    import ApplicationServices
    return ApplicationServices


def _redact(text: str) -> str:
    return text.replace(_HOME, "~") if _HOME and _HOME != "/" else text


# -- permissions --------------------------------------------------------------------

def responsible_chain(pid: int) -> list[dict]:
    """The ppid chain of `pid`, with each executable path (home redacted)."""
    chain: list[dict] = []
    seen: set[int] = set()
    while pid > 1 and pid not in seen and len(chain) < 30:
        seen.add(pid)
        try:
            out = subprocess.run(["/bin/ps", "-o", "ppid=,comm=", "-p", str(pid)],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            break
        if not out:
            break
        ppid_s, _, comm = out.partition(" ")
        chain.append({"pid": pid, "exe": _redact(comm.strip())})
        try:
            pid = int(ppid_s)
        except ValueError:
            break
    return chain


def responsible_app(chain: list[dict]) -> str | None:
    """First ancestor that is an app bundle. Homebrew/python.org interpreters run
    from `Python.framework/.../Python.app`, which is never the one TCC asks about."""
    for link in chain:
        exe = link["exe"]
        marker = ".app/Contents/MacOS/"
        if marker in exe and "/Python.framework/" not in exe:
            return exe.split(marker)[0].rsplit("/", 1)[-1]
    return None


def tcc_responsible(pid: int) -> dict | None:
    """The process TCC attributes `pid` to, as the kernel reports it.

    `responsibility_get_pid_responsible_for_pid` is libSystem SPI: the probe uses it
    to check the ppid-chain heuristic above, never product code.
    """
    try:
        import ctypes
        fn = ctypes.CDLL("/usr/lib/libSystem.B.dylib").responsibility_get_pid_responsible_for_pid
    except (OSError, AttributeError):
        return None
    fn.restype, fn.argtypes = ctypes.c_int, [ctypes.c_int]
    rpid = int(fn(pid))
    if rpid <= 0:
        return None
    chain = responsible_chain(rpid)
    return {"pid": rpid, "exe": chain[0]["exe"] if chain else ""}


def cmd_perms(request: bool) -> dict:
    AS, Q = _as(), _q()
    out: dict = {
        "accessibility": bool(AS.AXIsProcessTrustedWithOptions(
            {AS.kAXTrustedCheckOptionPrompt: bool(request)})),
        "screen_recording": bool(Q.CGPreflightScreenCaptureAccess()),
        "post_event": bool(Q.CGPreflightPostEventAccess()),
    }
    if request:
        out["screen_recording_request"] = bool(Q.CGRequestScreenCaptureAccess())
        out["post_event_request"] = bool(Q.CGRequestPostEventAccess())
    chain = responsible_chain(os.getpid())
    out["responsible_app"] = responsible_app(chain)
    out["tcc_responsible"] = tcc_responsible(os.getpid())
    out["chain"] = chain
    return out


# -- windows ------------------------------------------------------------------------

def cg_windows(pid: int) -> list[dict]:
    Q = _q()
    info = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionAll, Q.kCGNullWindowID) or []
    out = []
    for w in info:
        if int(w.get(Q.kCGWindowOwnerPID, -1)) != pid:
            continue
        b = w.get(Q.kCGWindowBounds) or {}
        out.append({
            "cg_id": int(w[Q.kCGWindowNumber]),
            "name": str(w.get(Q.kCGWindowName) or ""),
            "layer": int(w.get(Q.kCGWindowLayer, 0)),
            "onscreen": bool(w.get(Q.kCGWindowIsOnscreen, False)),
            "frame": [float(b.get("X", 0)), float(b.get("Y", 0)),
                      float(b.get("Width", 0)), float(b.get("Height", 0))],
        })
    return out


def ax_attr(el, name: str):
    err, val = _as().AXUIElementCopyAttributeValue(el, name, None)
    return val if err == 0 else None


def ax_frame(el) -> list[float] | None:
    AS = _as()
    pos, size = ax_attr(el, "AXPosition"), ax_attr(el, "AXSize")
    if pos is None or size is None:
        return None
    ok1, p = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
    ok2, s = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
    if not (ok1 and ok2):
        return None
    return [float(p.x), float(p.y), float(s.width), float(s.height)]


def ax_app(pid: int):
    AS = _as()
    app = AS.AXUIElementCreateApplication(pid)
    AS.AXUIElementSetMessagingTimeout(app, 3.0)
    return app


def ax_windows(pid: int) -> list[tuple[object, str, list[float] | None]]:
    wins = ax_attr(ax_app(pid), "AXWindows") or []
    return [(w, str(ax_attr(w, "AXTitle") or ""), ax_frame(w)) for w in wins]


def join_window(frame: list[float] | None, cg: list[dict], title: str = "") -> int | None:
    """CGWindowID of the CG window whose bounds equal the AX frame (both points).

    Bounds alone are ambiguous: PT opens every device dialog at the same frame
    (seen: R1 and PC1 both at 406,103 700x708), and keeps hidden twins of some
    windows ("Logs - MCP BUILDER" as 3578 on screen and 3513 off screen). So a
    CG name equal to the AX title wins (names are readable only with Screen
    Recording), then an on-screen window.
    """
    if frame is None:
        return None
    same = [w for w in cg
            if w["layer"] == 0 and all(abs(a - b) < 1.0 for a, b in zip(frame, w["frame"]))]
    same.sort(key=lambda w: (not (title and w["name"] == title), not w["onscreen"]))
    return same[0]["cg_id"] if same else None


def cmd_windows(pid: int) -> dict:
    cg = cg_windows(pid)
    t0 = time.perf_counter()
    ax = ax_windows(pid)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "cg": cg,
        "ax": [{"title": _redact(t), "frame": f, "cg_id": join_window(f, cg, t)} for _, t, f in ax],
        "ax_ms": ms,
    }


# -- AX tree ------------------------------------------------------------------------

def dump_tree(root) -> tuple[dict, dict]:
    # The backend's own walk (backends/macos/ax.py), so fixtures and live data
    # take the same path through to_element().
    from ..infrastructure.ui.backends.macos import ax
    return ax.walk(root, redact=_redact)


def _bundle_versions(pid: int) -> tuple[str, str]:
    try:
        from AppKit import NSRunningApplication
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        bundle = Path(str(app.bundleURL().path()))
    except Exception:
        return "", ""

    def read(p: Path, *keys: str) -> str:
        try:
            data = plistlib.loads(p.read_bytes())
        except (OSError, plistlib.InvalidFileException):
            return ""
        return next((str(data[k]) for k in keys if k in data), "")

    pt = read(bundle / "Contents/Info.plist", "CFBundleShortVersionString", "CFBundleVersion")
    if not pt:
        # PT 9.0.1 has no version key; the version only lives in the bundle id
        # (com.netacad.PacketTracer9.0.1).
        ident = read(bundle / "Contents/Info.plist", "CFBundleIdentifier")
        m = re.search(r"(\d+(?:\.\d+)+)$", ident)
        pt = m.group(1) if m else ""
    qt = read(bundle / "Contents/Frameworks/QtCore.framework/Resources/Info.plist",
              "CFBundleVersion", "CFBundleShortVersionString")
    return pt, qt


def _scale() -> float:
    from AppKit import NSScreen
    return float(NSScreen.mainScreen().backingScaleFactor())


def cmd_ax(pid: int, title: str, out_path: str) -> dict:
    cg = cg_windows(pid)
    wins = ax_windows(pid)
    match = [w for w in wins if w[1] == title] or [w for w in wins if title.lower() in w[1].lower()]
    if not match:
        return {"error": f"no AX window titled {title!r}", "titles": [t for _, t, _ in wins]}
    el, wtitle, frame = match[0]
    t0 = time.perf_counter()
    tree, stats = dump_tree(el)
    stats["walk_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    pt, qt = _bundle_versions(pid)
    fixture = {
        "recorded": _dt.date.today().isoformat(),
        "macos": _platform.mac_ver()[0],
        "pt": pt,
        "qt": qt,
        "scale": _scale(),
        "window": {"title": _redact(wtitle), "cg_id": join_window(frame, cg, wtitle), "frame": frame},
        "tree": tree,
    }
    Path(out_path).write_text(json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"out": out_path, "window": fixture["window"], **stats}


# -- press --------------------------------------------------------------------------

def find_elements(root, title: str = "", role: str = "", ident_suffix: str = "") -> list:
    """Depth-first search of `root` for elements matching every given filter."""
    found, stack, seen = [], [root], 0
    while stack and seen < MAX_NODES:
        el = stack.pop()
        seen += 1
        ok = True
        if role and str(ax_attr(el, "AXRole") or "") != role:
            ok = False
        if ok and title and str(ax_attr(el, "AXTitle") or "") != title:
            ok = False
        if ok and ident_suffix and not str(ax_attr(el, "AXIdentifier") or "").endswith(ident_suffix):
            ok = False
        if ok:
            found.append(el)
        stack.extend(reversed(list(ax_attr(el, "AXChildren") or [])))
    return found


def cmd_press(pid: int, window: str, title: str, role: str, ident_suffix: str, action: str) -> dict:
    wins = [w for w in ax_windows(pid) if w[1] == window]
    if not wins:
        return {"error": f"no AX window titled {window!r}"}
    hits = find_elements(wins[0][0], title, role, ident_suffix)
    if not hits:
        return {"error": "no matching element"}
    el = hits[0]
    t0 = time.perf_counter()
    if action == "focus-space":
        # Qt's mac bridge maps AXPress on a CHECKABLE button to toggle(), which
        # flips the check without emitting clicked(): PT's Config/Services menus
        # ignore it. A focused Qt button clicks on Space, and keyboard events
        # posted to the pid do reach PT (mouse events posted to the pid do not).
        err = _as().AXUIElementSetAttributeValue(el, "AXFocused", True)
        Q = _q()
        for down in (True, False):
            Q.CGEventPostToPid(pid, Q.CGEventCreateKeyboardEvent(None, 49, down))  # kVK_Space
    else:
        err = _as().AXUIElementPerformAction(el, action)
    return {"err": int(err), "matches": len(hits), "action": action,
            "role": str(ax_attr(el, "AXRole") or ""), "title": str(ax_attr(el, "AXTitle") or ""),
            "identifier": _redact(str(ax_attr(el, "AXIdentifier") or "")),
            "ms": round((time.perf_counter() - t0) * 1000, 1)}


# -- click --------------------------------------------------------------------------

def cmd_click(pid: int, x: float, y: float, route: str, wid: int | None) -> dict:
    Q = _q()
    pt = (float(x), float(y))
    down = Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseDown, pt, Q.kCGMouseButtonLeft)
    up = Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseUp, pt, Q.kCGMouseButtonLeft)
    t0 = time.perf_counter()
    if route in ("pid", "pid-fields"):
        if route == "pid-fields":
            if wid is None:
                return {"error": "--wid is required for route pid-fields"}
            for ev in (down, up):
                Q.CGEventSetIntegerValueField(ev, Q.kCGMouseEventWindowUnderMousePointer, wid)
                Q.CGEventSetIntegerValueField(
                    ev, Q.kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent, wid)
        Q.CGEventPostToPid(pid, down)
        Q.CGEventPostToPid(pid, up)
        result = "posted"
    else:
        # A HID-level click lands on whatever window is on top: bring PT forward
        # and refuse to click unless it really is frontmost.
        from AppKit import NSRunningApplication, NSWorkspace
        NSRunningApplication.runningApplicationWithProcessIdentifier_(pid).activateWithOptions_(0)
        for w, _, _ in ax_windows(pid)[:1]:
            _as().AXUIElementPerformAction(w, "AXRaise")
        time.sleep(0.4)
        front = NSWorkspace.sharedWorkspace().frontmostApplication()
        if front is None or int(front.processIdentifier()) != pid:
            return {"error": "PT is not frontmost; not clicking", "route": route}
        saved = Q.CGEventGetLocation(Q.CGEventCreate(None))
        Q.CGEventPost(Q.kCGHIDEventTap, down)
        Q.CGEventPost(Q.kCGHIDEventTap, up)
        time.sleep(0.05)
        Q.CGWarpMouseCursorPosition(saved)
        result = "cursor-restored"
    return {"result": result, "route": route, "ms": round((time.perf_counter() - t0) * 1000, 1)}


# -- hit test -----------------------------------------------------------------------

def cmd_hit(x: float, y: float) -> dict:
    """What is on top at a screen point: the element and its parents (read-only).
    The macOS click route checks this before it clicks (backends/macos/events.py)."""
    from ..infrastructure.ui.backends.macos.events import QuartzIO
    t0 = time.perf_counter()
    idents = QuartzIO().hit_idents(x, y)
    err, el = _as().AXUIElementCopyElementAtPosition(_as().AXUIElementCreateSystemWide(), x, y, None)
    top = {"role": str(ax_attr(el, "AXRole") or ""), "title": str(ax_attr(el, "AXTitle") or "")} if err == 0 and el else {}
    return {"err": int(err), "top": top, "idents": [_redact(i) for i in idents],
            "ms": round((time.perf_counter() - t0) * 1000, 1)}


# -- capture ------------------------------------------------------------------------

def cgimage_to_bgra(img) -> tuple[int, int, bytes, dict]:
    """Normalise any 32-bit CGImage to top-down B,G,R,A rows with no padding."""
    Q = _q()
    w, h = int(Q.CGImageGetWidth(img)), int(Q.CGImageGetHeight(img))
    bpr = int(Q.CGImageGetBytesPerRow(img))
    info = int(Q.CGImageGetBitmapInfo(img))
    data = bytes(Q.CGDataProviderCopyData(Q.CGImageGetDataProvider(img)))
    alpha = info & Q.kCGBitmapAlphaInfoMask
    order = info & Q.kCGBitmapByteOrderMask
    alpha_first = alpha in (Q.kCGImageAlphaPremultipliedFirst, Q.kCGImageAlphaFirst,
                            Q.kCGImageAlphaNoneSkipFirst)
    little = order == Q.kCGBitmapByteOrder32Little
    # Memory order of the four channels, as indexes into B,G,R,A.
    if little and alpha_first:
        layout = "BGRA"
    elif little:
        layout = "ABGR"
    elif alpha_first:
        layout = "ARGB"
    else:
        layout = "RGBA"
    out = bytearray(w * 4 * h)
    for row in range(h):
        src = data[row * bpr: row * bpr + w * 4]
        dst = memoryview(out)[row * w * 4: (row + 1) * w * 4]
        for i, ch in enumerate("BGRA"):
            dst[i::4] = src[layout.index(ch)::4]
    meta = {"width": w, "height": h, "bytes_per_row": bpr, "bitmap_info": info, "layout": layout}
    return w, h, bytes(out), meta


def _write_png(img, out_path: str) -> dict:
    from ..infrastructure.ui.png import bgra_to_png, looks_blank
    w, h, bgra, meta = cgimage_to_bgra(img)
    Path(out_path).write_bytes(bgra_to_png(w, h, bgra))
    return {**meta, "blank": looks_blank(bgra)}


def _capture_sck(wid: int, out_path: str, timeout: float = 10.0) -> dict:
    import objc
    import ScreenCaptureKit as SCK
    from AppKit import NSApplication
    # A bare CLI process has no window-server connection; SCK then aborts the
    # whole process (CGS_REQUIRE_INIT assertion). NSApplication opens one.
    NSApplication.sharedApplication()
    box: dict = {}
    got = threading.Event()

    def on_content(content, error):
        try:
            box["content"], box["error"] = content, error
        finally:
            got.set()

    SCK.SCShareableContent.getShareableContentWithCompletionHandler_(on_content)
    if not got.wait(timeout):
        return {"error": "getShareableContent timed out"}
    if box.get("error") is not None or box.get("content") is None:
        return {"error": f"getShareableContent: {box.get('error')}"}
    win = next((w for w in box["content"].windows() if int(w.windowID()) == wid), None)
    if win is None:
        return {"error": f"no SCWindow with id {wid}"}
    flt = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(win)
    cfg = SCK.SCStreamConfiguration.alloc().init()
    frame = win.frame()
    scale = _scale()
    cfg.setWidth_(int(frame.size.width * scale))
    cfg.setHeight_(int(frame.size.height * scale))
    cfg.setShowsCursor_(False)
    shot: dict = {}
    done = threading.Event()

    def on_image(image, error):
        # pyobjc has no block metadata for this argument and hands over a raw
        # ^{CGImage=} pointer, valid only during the callback: wrap (and so
        # retain) it here. Nothing may raise in a completion block: an uncaught
        # Python exception there terminates the process.
        try:
            if image is not None and hasattr(image, "pointerAsInteger"):
                image = objc.objc_object(c_void_p=image.pointerAsInteger)
            shot["image"], shot["error"] = image, error
        except Exception as exc:
            shot["image"], shot["error"] = None, f"wrap failed: {exc}"
        finally:
            done.set()

    SCK.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(flt, cfg, on_image)
    if not done.wait(timeout):
        return {"error": "captureImage timed out"}
    if shot.get("error") is not None or shot.get("image") is None:
        return {"error": f"captureImage: {shot.get('error')}"}
    return _write_png(shot["image"], out_path)


def _capture_cgimage(wid: int, out_path: str) -> dict:
    Q = _q()
    img = Q.CGWindowListCreateImage(
        Q.CGRectNull, Q.kCGWindowListOptionIncludingWindow, wid,
        Q.kCGWindowImageBoundsIgnoreFraming | Q.kCGWindowImageBestResolution)
    if img is None:
        return {"error": "CGWindowListCreateImage returned None"}
    return _write_png(img, out_path)


def _capture_screencapture(wid: int, out_path: str) -> dict:
    proc = subprocess.run(["/usr/sbin/screencapture", "-x", "-o", f"-l{wid}", out_path],
                          capture_output=True, text=True, timeout=20)
    if proc.returncode != 0 or not Path(out_path).exists():
        return {"error": f"screencapture rc={proc.returncode} {proc.stderr.strip()}"}
    # Read the file back through ImageIO so the blank check sees the same pixels.
    Q = _q()
    from Foundation import NSURL
    src = Q.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(out_path), None)
    img = Q.CGImageSourceCreateImageAtIndex(src, 0, None) if src is not None else None
    if img is None:
        return {"error": "could not read back the PNG"}
    from ..infrastructure.ui.png import looks_blank
    w, h, bgra, meta = cgimage_to_bgra(img)
    return {**meta, "blank": looks_blank(bgra)}


def cmd_capture(wid: int, route: str, out_path: str) -> dict:
    t0 = time.perf_counter()
    fn = {"sck": _capture_sck, "cgimage": _capture_cgimage,
          "screencapture": _capture_screencapture}[route]
    try:
        res = fn(wid, out_path)
    except Exception as exc:  # a probe reports, it does not crash
        res = {"error": f"{type(exc).__name__}: {exc}"}
    return {"route": route, "ms": round((time.perf_counter() - t0) * 1000, 1), **res}


# -- CLI ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    if detect_os() != "macos":
        print(json.dumps({"error": "macos_probe runs on macOS only"}))
        return 2
    ap = argparse.ArgumentParser(prog="macos_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("perms")
    p.add_argument("--request", action="store_true")
    p = sub.add_parser("windows")
    p.add_argument("--pid", type=int, required=True)
    p = sub.add_parser("ax")
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("press")
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--window", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--role", default="")
    p.add_argument("--ident-suffix", default="")
    p.add_argument("--action", default="AXPress")
    p = sub.add_parser("click")
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--x", type=float, required=True)
    p.add_argument("--y", type=float, required=True)
    p.add_argument("--route", choices=("pid", "pid-fields", "post"), default="pid")
    p.add_argument("--wid", type=int)
    p = sub.add_parser("hit")
    p.add_argument("--x", type=float, required=True)
    p.add_argument("--y", type=float, required=True)
    p = sub.add_parser("capture")
    p.add_argument("--wid", type=int, required=True)
    p.add_argument("--route", choices=("sck", "cgimage", "screencapture"), required=True)
    p.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "perms":
        res = cmd_perms(a.request)
    elif a.cmd == "windows":
        res = cmd_windows(a.pid)
    elif a.cmd == "ax":
        res = cmd_ax(a.pid, a.title, a.out)
    elif a.cmd == "press":
        res = cmd_press(a.pid, a.window, a.title, a.role, a.ident_suffix, a.action)
    elif a.cmd == "click":
        res = cmd_click(a.pid, a.x, a.y, a.route, a.wid)
    elif a.cmd == "hit":
        res = cmd_hit(a.x, a.y)
    else:
        res = cmd_capture(a.wid, a.route, a.out)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 1 if isinstance(res, dict) and "error" in res else 0


if __name__ == "__main__":
    sys.exit(main())
