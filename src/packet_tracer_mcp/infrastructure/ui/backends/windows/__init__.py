"""Windows UI backend: Win32 (windows, capture, posted clicks) + UI Automation (the widget tree).

`win32.py` and `uia.py` were moved here unchanged (CONSTRAINTS C4); `backend.py`
adapts them to `WindowBackend`.
"""

from __future__ import annotations

from .backend import WindowsBackend

__all__ = ["WindowsBackend"]
