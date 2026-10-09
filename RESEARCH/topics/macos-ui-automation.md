# macOS UI automation for PT's windows

How each thing the Windows presenter does can be done on macOS, and what it
costs in permissions. Every API name below comes from Apple's documentation or
the pyobjc wrappers. **None has been called on this project's Mac yet.**
`PLAN/CONSTRAINTS.md` C6 requires the PHASE-00 probe to exercise each one before
code depends on it.

## 1. Permission model

- macOS gates these APIs through TCC. Two services matter here.
  **Accessibility** (`kTCCServiceAccessibility`) covers reading and driving
  other apps' UI and posting input events. **Screen Recording**
  (`kTCCServiceScreenCapture`) covers capturing other apps' windows and reading
  their window titles from the window server.
- A grant belongs to the **responsible process**, which is the GUI app at the
  top of the launch chain (S6). The MCP server is a child of the client, so the
  user grants **Claude** (Claude Desktop), **Terminal / iTerm2** (Claude Code in a
  terminal) or **Visual Studio Code**, never "python". Inheritance can fail for
  some launch methods (S7). Re-check it on the user's real client.
- Preflight APIs never prompt. Request APIs show the system prompt once:
  - `AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: False|True})`
    (ApplicationServices / HIServices)
  - `CGPreflightScreenCaptureAccess()` / `CGRequestScreenCaptureAccess()`
    (Quartz, macOS 10.15+)
  - `CGPreflightPostEventAccess()` / `CGRequestPostEventAccess()`
    (Quartz, macOS 10.15+)
- A Screen Recording grant usually takes effect only after the responsible app
  restarts. To verify in PHASE-04.

## 2. Finding PT's windows

- `CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID)` lists
  every window with `kCGWindowNumber` (the CGWindowID), `kCGWindowOwnerPID`,
  `kCGWindowBounds`, `kCGWindowLayer` and `kCGWindowName`. **Without Screen
  Recording, `kCGWindowName` is empty for other apps' windows** (macOS 10.15+),
  so a title lookup cannot go through Core Graphics alone.
- Accessibility gives the titles: `AXUIElementCreateApplication(pid)`, then the
  `AXWindows` attribute, then each window's `AXTitle`, `AXPosition` and `AXSize`.
- **Join.** An AX window and a CG window are the same window when the pid
  matches and the bounds match (AX frame == `kCGWindowBounds`, both in points).
  This yields a JSON-safe CGWindowID handle without the private
  `_AXUIElementGetWindow`, and without needing Screen Recording just to open a
  dialog.
- Bringing a window forward: the `AXRaise` action on the AX window, then
  `NSRunningApplication.runningApplicationWithProcessIdentifier_(pid).activateWithOptions_(...)`.

## 3. Capturing a window that may be covered

In order of preference:

1. **ScreenCaptureKit** (macOS 14+). Call
   `SCShareableContent.getShareableContentWithCompletionHandler_`, pick the
   `SCWindow` whose `windowID()` equals the handle, then build
   `SCContentFilter.alloc().initWithDesktopIndependentWindow_(win)` and an
   `SCStreamConfiguration` sized to frame × backing scale with
   `setShowsCursor_(False)`. Then call
   `SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_`.
   It captures the window alone, even when covered. Handlers are asynchronous:
   wait on a `threading.Event` with a timeout (S9).
2. **`CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, wid,
   kCGWindowImageBoundsIgnoreFraming | kCGWindowImageBestResolution)`**. This is
   the pre-14 route, deprecated in 14 (S8). It may be unavailable or prompt on 15.
3. **`/usr/sbin/screencapture -x -o -l<wid> <file.png>`**: no sound (`-x`), no
   shadow (`-o`), one window (`-l`). It is Apple's own tool, but the grant still
   goes to the responsible app.

CGImage to BGRA: read `CGImageGetWidth`, `CGImageGetHeight`,
`CGImageGetBytesPerRow` and `CGImageGetBitmapInfo`, then
`CGDataProviderCopyData(CGImageGetDataProvider(img))`. **Rows can be padded**
(bytesPerRow > width × 4): strip the padding. **The pixel order follows the
bitmap info**: normalise it to B,G,R,A before `png.bgra_to_png`. A capture with
Screen Recording missing returns an image that is blank or shows only the
desktop. `png.looks_blank` already flags blank images.

## 4. Clicking the canvas

- `CGEventCreateMouseEvent(None, kCGEventLeftMouseDown | kCGEventLeftMouseUp, (x, y),
  kCGMouseButtonLeft)` followed by `CGEventPostToPid(pid, ev)` delivers the event
  to PT's queue without moving the real cursor. Nothing found says whether Qt
  routes such an event to the canvas while PT is not frontmost. Something to
  try: set the `kCGMouseEventWindowUnderMousePointer` and
  `kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent` fields to the
  CGWindowID.
- Visible fallback: activate PT, save the cursor
  (`CGEventGetLocation(CGEventCreate(None))`), post down and up with
  `CGEventPost(kCGHIDEventTap, ev)`, then put the cursor back with
  `CGWarpMouseCursorPosition(saved)`. Report it as `"cursor-restored"`.
- The Select-tool guard in `presenter.py` (`_open_by_click`) applies unchanged.
  With Delete active, a click deletes the device.

## 5. Units

AX frames and CGEvent locations are **points** in global display coordinates,
with the origin at the top left of the main display. Captures are **pixels**
(×2 on Retina). Qt on macOS lays out in device-independent pixels, which are
points, so PT scene coordinates at 100 % zoom should map 1:1 to points. That
extends the Windows calibration in `presenter.py` (`device_point`). It is an
assumption until PHASE-05 measures it.

## 6. UIA call → AX call

| Windows today (`ui/win32.py`, `ui/uia.py`) | macOS | Permission |
|---|---|---|
| `find_window(pid, title)`, EnumWindows | AX `AXWindows` → `AXTitle`; CGWindowID by the bounds join (§2) | Accessibility |
| `main_window(pid)` | the `AXMainWindow` attribute of the app element | Accessibility |
| `raise_window` | `AXRaise` + `activateWithOptions_` | Accessibility |
| `capture`, PrintWindow | §3 | Screen Recording |
| `post_click`, PostMessage | §4 | Accessibility (post-event access) |
| `Uia.descendants`, FindAll | recursive `AXChildren` walk, depth and node count capped | Accessibility |
| SelectionItem `Select` (tab) | `AXPress` on the tab element | Accessibility |
| Invoke | `AXUIElementPerformAction(el, "AXPress")` | Accessibility |
| Toggle `CurrentToggleState` | `AXValue` (0/1) of the toggle or checkbox | Accessibility |
| RangeValue value / `SetValue(max)` | `AXValue`, `AXMaxValue`; set `AXValue` | Accessibility |
| Value `SetValue(text)` | `AXUIElementSetAttributeValue(el, "AXValue", text)` | Accessibility |
| `CurrentIsOffscreen` | none: derive it from a zero size or a frame outside the window's frame | — |
| `CurrentBoundingRectangle` (pixels) | `AXPosition` + `AXSize` (points), unpacked with `AXValueGetValue` | — |
| `AutomationId` | `AXIdentifier` (empty on old Qt: `pt-on-macos.md` §4) | — |
| `Name` | `AXTitle`, else `AXDescription`, else `AXValue` for static text | — |
