"""The macOS UI backend (Accessibility, Core Graphics, ScreenCaptureKit via pyobjc).

pyobjc is imported inside the functions that use it, so this package imports on
every OS (CONSTRAINTS C2); `load_backend` picks it on macOS.
"""

from __future__ import annotations

from .backend import MacBackend

__all__ = ["MacBackend"]
