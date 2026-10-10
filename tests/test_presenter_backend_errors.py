"""A backend's operation error reaches the tools as a PresenterError (C7).

`BackendError` means an operation failed (every macOS capture route refused, a
window handle went stale). The tools catch `PresenterError` and print it; any
other exception escaped as a bare tool error with no explanation.
"""

from __future__ import annotations

import pytest

from src.packet_tracer_mcp.infrastructure.ui.backend import BackendError
from src.packet_tracer_mcp.infrastructure.ui.presenter import Presenter, PresenterError
from tests.fakes.fake_backend import FakeBackend
from tests.test_presenter_on_backend import pt


class CaptureFails(FakeBackend):
    def capture(self, handle):
        raise BackendError("could not capture the window (sck: timed out; cgimage: no image)")


class StaleHandle(FakeBackend):
    def raise_window(self, handle):
        raise BackendError(f"window {handle} is unknown: find it first")


def test_capture_error_becomes_a_presenter_error(tmp_path):
    send, _ = pt()
    p = Presenter(send, backend=CaptureFails(main=1, windows={"PC1": 7}), sleep=lambda s: None)
    with pytest.raises(PresenterError, match="could not capture the window"):
        p.capture("PC1", tmp_path / "pc1.png")


def test_open_error_becomes_a_presenter_error():
    send, _ = pt(open_=True)
    p = Presenter(send, backend=StaleHandle(main=1, windows={"PC1": 7}), sleep=lambda s: None)
    with pytest.raises(PresenterError, match="is unknown"):
        p.open("PC1")
