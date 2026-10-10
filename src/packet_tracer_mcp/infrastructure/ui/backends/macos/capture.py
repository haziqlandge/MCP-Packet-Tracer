"""Capture one of PT's windows as BGRA pixels, even when it is covered.

Routes, in order (RESEARCH/topics/macos-ui-automation.md §3): ScreenCaptureKit,
CGWindowListCreateImage, then `/usr/sbin/screencapture -l`. On macOS 26.5.1 all
three captured a covered dialog with identical pixels (PREVIOUS_WORK 2.4 #8).
All need Screen Recording for the responsible app.

SCK traps, each measured: without a window-server connection SCK aborts the whole
process (`CGS_REQUIRE_INIT`), so `NSApplication.sharedApplication()` comes first
(it works from a worker thread, measured); the screenshot handler gets the
CGImage as a raw pointer, wrapped inside the handler; and nothing may raise in a
completion handler, which would terminate the process.

`to_bgra` is pure and tested byte-exact: rows can be padded, and the byte order
follows the bitmap info. Captures are in pixels (CONSTRAINTS C10).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading

from ...backend import BackendError, Capture

# CGImage bitmap-info fields (Apple ABI, CGImage.h). On a Mac a test checks them
# against Quartz's own constants.
ALPHA_MASK = 0x1F
ORDER_MASK = 0x7000
ORDER_32_LITTLE = 2 << 12
ORDER_32_BIG = 4 << 12
ALPHA_PREMULTIPLIED_LAST = 1
ALPHA_PREMULTIPLIED_FIRST = 2
ALPHA_LAST = 3
ALPHA_FIRST = 4
ALPHA_NONE_SKIP_LAST = 5
ALPHA_NONE_SKIP_FIRST = 6
_ALPHA_FIRST = (ALPHA_PREMULTIPLIED_FIRST, ALPHA_FIRST, ALPHA_NONE_SKIP_FIRST)

SCK_TIMEOUT_S = 5.0


# -- pure -----------------------------------------------------------------------

def layout_for(bitmap_info: int) -> str:
    """Memory order of a 32-bit pixel's four channels."""
    first = (bitmap_info & ALPHA_MASK) in _ALPHA_FIRST
    if bitmap_info & ORDER_MASK == ORDER_32_LITTLE:
        return "BGRA" if first else "ABGR"
    return "ARGB" if first else "RGBA"   # big-endian, or the default order


def to_bgra(data: bytes, width: int, height: int, bytes_per_row: int, bitmap_info: int) -> bytes:
    """Tightly packed top-down B,G,R,A from 32-bit pixels. Padding at the end of
    each row is dropped; premultiplied alpha is left as it is."""
    row_len = width * 4
    if bytes_per_row < row_len:
        raise ValueError(f"rows of {bytes_per_row} bytes cannot hold {width} 32-bit pixels")
    if height > 0 and len(data) < bytes_per_row * (height - 1) + row_len:
        raise ValueError(f"{len(data)} bytes is too short for {width}x{height}")
    layout = layout_for(bitmap_info)
    src = [layout.index(ch) for ch in "BGRA"]
    out = bytearray(row_len * height)
    view = memoryview(out)
    for y in range(height):
        row = data[y * bytes_per_row: y * bytes_per_row + row_len]
        dst = view[y * row_len:(y + 1) * row_len]
        for i, s in enumerate(src):
            dst[i::4] = row[s::4]
    return bytes(out)


# -- CGImage → Capture ----------------------------------------------------------

def _quartz():
    import Quartz
    return Quartz


def from_cgimage(img) -> Capture:
    Q = _quartz()
    if int(Q.CGImageGetBitsPerPixel(img)) != 32:
        raise BackendError(f"unexpected pixel size {Q.CGImageGetBitsPerPixel(img)} bits")
    w, h = int(Q.CGImageGetWidth(img)), int(Q.CGImageGetHeight(img))
    data = bytes(Q.CGDataProviderCopyData(Q.CGImageGetDataProvider(img)))
    return Capture(w, h, to_bgra(data, w, h, int(Q.CGImageGetBytesPerRow(img)),
                                 int(Q.CGImageGetBitmapInfo(img))))


# -- routes ---------------------------------------------------------------------

def _sck(cg_id: int) -> Capture | None:
    import objc
    import ScreenCaptureKit as SCK
    from AppKit import NSApplication, NSScreen
    NSApplication.sharedApplication()  # window-server connection, or SCK aborts the process

    content: dict = {}
    got = threading.Event()

    def on_content(c, error):
        try:
            content["c"], content["e"] = c, error
        finally:
            got.set()

    SCK.SCShareableContent.getShareableContentWithCompletionHandler_(on_content)
    if not got.wait(SCK_TIMEOUT_S):
        raise BackendError("capture timed out (listing windows)")
    if content.get("e") is not None or content.get("c") is None:
        raise BackendError(f"no shareable content: {content.get('e')}")
    win = next((w for w in content["c"].windows() if int(w.windowID()) == cg_id), None)
    if win is None:
        return None
    flt = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(win)
    cfg = SCK.SCStreamConfiguration.alloc().init()
    scale = float(NSScreen.mainScreen().backingScaleFactor())
    frame = win.frame()
    cfg.setWidth_(int(frame.size.width * scale))
    cfg.setHeight_(int(frame.size.height * scale))
    cfg.setShowsCursor_(False)

    shot: dict = {}
    done = threading.Event()

    def on_image(image, error):
        # The image arrives as a raw ^{CGImage=} pointer, valid only here.
        try:
            if image is not None and hasattr(image, "pointerAsInteger"):
                image = objc.objc_object(c_void_p=image.pointerAsInteger)
            shot["i"], shot["e"] = image, error
        except Exception as exc:
            shot["i"], shot["e"] = None, exc
        finally:
            done.set()

    SCK.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(flt, cfg, on_image)
    if not done.wait(SCK_TIMEOUT_S):
        raise BackendError("capture timed out")
    if shot.get("e") is not None or shot.get("i") is None:
        raise BackendError(f"screenshot failed: {shot.get('e')}")
    return from_cgimage(shot["i"])


def _cgimage(cg_id: int) -> Capture | None:
    Q = _quartz()
    img = Q.CGWindowListCreateImage(
        Q.CGRectNull, Q.kCGWindowListOptionIncludingWindow, cg_id,
        Q.kCGWindowImageBoundsIgnoreFraming | Q.kCGWindowImageBestResolution)
    return from_cgimage(img) if img is not None else None


def _screencapture(cg_id: int) -> Capture | None:
    Q = _quartz()
    from Foundation import NSURL
    fd, path = tempfile.mkstemp(suffix=".png", prefix="pt-mcp-capture-")
    os.close(fd)
    try:
        proc = subprocess.run(["/usr/sbin/screencapture", "-x", "-o", f"-l{cg_id}", path],
                              capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            raise BackendError(f"screencapture rc={proc.returncode}: {proc.stderr.strip()}")
        src = Q.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(path), None)
        img = Q.CGImageSourceCreateImageAtIndex(src, 0, None) if src is not None else None
        return from_cgimage(img) if img is not None else None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


ROUTES = (("sck", _sck), ("cgimage", _cgimage), ("screencapture", _screencapture))


def capture_window(cg_id: int) -> tuple[Capture, str]:
    """The first route that returns an image, and its name."""
    errors = []
    for name, route in ROUTES:
        try:
            cap = route(cg_id)
        except Exception as exc:  # one route failing is not the end: try the next
            errors.append(f"{name}: {exc}")
            continue
        if cap is not None:
            return cap, name
        errors.append(f"{name}: no image")
    raise BackendError("could not capture the window (" + "; ".join(errors) + ")")
