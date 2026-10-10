"""The backend for an OS without UI mode: it says why, and does nothing else."""

from __future__ import annotations

from ..backend import BackendUnavailable


class NullBackend:
    name = "null"

    def __init__(self, reason: str):
        self.reason = reason

    def available(self, *, request: bool = False) -> tuple[bool, str]:
        return False, self.reason

    def _unavailable(self, *args, **kwargs):
        raise BackendUnavailable(self.reason)

    find_window = main_window = raise_window = capture = click = _unavailable
    elements = select = press = toggle_state = range_value = set_value = _unavailable
    scroll_to_end = _unavailable
