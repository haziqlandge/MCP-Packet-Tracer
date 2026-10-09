# PHASE-08 — Bonus: Linux UI backend

> **GATED.** Do not start until the entry criteria below are all met. The user
> asked on 2026-10-10 for it to "work out of box on any os". Headless Linux is
> covered by PHASE-01 and PHASE-02. Linux UI mode waits for a Linux machine with
> PT and for the core to be done.

## Objective

On Linux with PT 9.0.x, UI mode opens and captures device windows through a
`LinuxBackend`, with the same presenter and locators as macOS and Windows.

## Why it exists

It completes "any OS" for UI mode. The seam (PHASE-03) and the locator data
(PHASE-05) make it one more backend rather than a fork. Without it, Linux users
get every tool headless plus a clear "not yet" from the null backend. That is
acceptable, but it is not parity.

## Entry criteria

- [ ] PHASE-00 to PHASE-07 complete, with every acceptance box ticked
- [ ] A Linux machine (X11 or XWayland session) with PT 9.0.x and the `.pts`, available for live runs
- [ ] The user confirms Linux UI mode is still wanted

## Dependencies

PHASE-03 (protocol and locators), PHASE-05 (the `by_shape` fallbacks, which a
Linux AT-SPI tree may also need), PHASE-06 (doctor integration).

## Files to create

```
src/packet_tracer_mcp/infrastructure/ui/backends/linux/__init__.py
src/packet_tracer_mcp/infrastructure/ui/backends/linux/atspi.py     AT-SPI over D-Bus: tree, actions, values
src/packet_tracer_mcp/infrastructure/ui/backends/linux/x11.py       window lookup, capture, click on X11/XWayland
src/packet_tracer_mcp/infrastructure/ui/backends/linux/backend.py   LinuxBackend
tests/fixtures/linux/*.json                                         AT-SPI trees recorded from the real PT
tests/test_linux_*.py
```

## Implementation details

### Spike first (same method as PHASE-00)

Record, on the Linux machine:

- distro and session type (`echo $XDG_SESSION_TYPE`)
- PT's Qt platform plugin (xcb or wayland)
- whether PT exposes AT-SPI (it may need `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1` or
  the accessibility bus enabled)
- whether accessible ids carry objectName paths
- which capture route works for a covered window (XComposite / XGetImage on
  X11; nothing generic on native Wayland)
- which input route works (AT-SPI actions first; XTest moves the cursor)

Commit the fixtures as `tests/fixtures/linux/`.

### Dependencies

Prefer pure-Python, pip-installable packages behind `sys_platform == 'linux'`
markers (a D-Bus client and an X11 client). **Avoid PyGObject**, which needs
system libraries and breaks "out of the box". If a system package is
unavoidable, the null-backend reason and the doctor must name the exact
`apt`/`dnf` command.

### The open question this phase must answer

Is a covered-window capture possible on the user's session type? On native
Wayland, generic capture of another app's window needs a portal and user
consent each time. If that is the case, the honest result is "capture on X11 and
XWayland only", recorded as a finding.

## Tests

- Fixture conversion and locators, as for macOS (`EVALUATION.md` §2).
- Backend selection on Linux returns `LinuxBackend` once importable, and the
  null backend with the install remedy otherwise.

## Acceptance criteria

- [ ] Linux fixtures recorded; conversion and locator tests pass on CI
- [ ] Live, Linux: `tests/live/ui.json` flows report `ok` with non-blank PNGs, or each failing flow is recorded with its cause
- [ ] `pt-mcp doctor --ui` on Linux reports the backend state and any system-package remedy
- [ ] Docs updated: the Linux row of the per-OS table no longer says "not yet" (or says exactly what remains)

## Known failure conditions

- An empty AT-SPI tree → the accessibility bus is off, or Qt accessibility is
  not enabled for PT. Set the environment variable in PT's launcher; the doctor
  explains how.
- Capture is black on Wayland → expected without a portal. Report it as such.
- A click lands elsewhere → the XWayland scale factor. Apply the units rule (C10)
  with the measured scale.
