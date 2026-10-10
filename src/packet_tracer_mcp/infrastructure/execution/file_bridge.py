"""File transport between the MCP server and Packet Tracer's Script Engine.

Why it exists, in addition to the HTTP bridge:
HTTP polling lives in the extension's webview (the window). If the user closes it,
the webview dies and PT stops running commands — even though the extension
remains installed. The Script Engine, in contrast, runs WHENEVER PT is open
(no window), has setInterval and file access, but does NOT have
XMLHttpRequest. So the channel with the Script Engine cannot be HTTP: it is a
file mailbox.

Coexistence (not replacement): HTTP remains the channel while the window is
open; this channel takes over when it is closed. Routing (choosing one
per request, never both) lives in the adapter; only the transport lives here.

Security: the mailbox lives under %LOCALAPPDATA% with a user ACL, just like the
token. A web page in the browser cannot write a local file, so this channel does
not have the CORS vector that forced the HTTP channel to authenticate. The trust
level is the same one the threat model already assumes: the local user.

Protocol (one file per request, atomic write tmp+rename):
    Python  ─ writes req_<seq>.js  (atomic) ─►  Script Engine
    Python  ◄─ reads/deletes res_<seq>.txt    ─   writes res, deletes req
    Script Engine touches alive.txt every tick (liveness heartbeat)
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from ..platform.base import detect_os
from ..platform.paths import mailbox_candidates
from .bridge_token import token_dir

# Mailbox subdirectory, under the same dir as the token.
_BRIDGE_SUBDIR = "bridge"

# The Script Engine is considered alive if it touched alive.txt less than this long ago.
HEARTBEAT_FRESH_S = 6.0


def bridge_dir() -> Path:
    """The canonical mailbox, next to the token."""
    return token_dir() / _BRIDGE_SUBDIR


def ensure_bridge_dir() -> Path:
    d = bridge_dir()
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def _heartbeat_age(directory: Path) -> float | None:
    """Seconds since the Script Engine last touched `directory/alive.txt`."""
    try:
        return max(0.0, time.time() - (directory / "alive.txt").stat().st_mtime)
    except OSError:
        return None


class FileBridge:
    """Python side of the file mailbox.

    No state of its own beyond a sequence counter; the real state is the
    files on disk, so it survives process restarts.

    The mailbox is wherever the extension's heartbeat is (PLAN/INTERFACES.md §5):
    the released V5.2 polls a Windows-shaped directory on macOS and Linux, so the
    server follows the freshest `alive.txt` among the candidates instead of
    assuming its own path. An explicit `directory` (tests, config) wins.
    """

    def __init__(self, directory: Path | None = None, candidates: list[Path] | None = None):
        if directory:
            self.candidates = [Path(directory)]
        elif candidates:
            self.candidates = [Path(c) for c in candidates]
        else:
            self.candidates = mailbox_candidates(detect_os(), os.environ, Path.home())
        self._seq = 0

    def active_dir(self) -> Path:
        """The candidate with the freshest live heartbeat; the canonical one when
        none is live. Evaluated on every call: a cached choice would pile requests
        up in a mailbox nobody reads once PT restarts or switches."""
        fresh = []
        for d in self.candidates:
            age = _heartbeat_age(d)
            if age is not None and age < HEARTBEAT_FRESH_S:
                fresh.append((age, d))
        return min(fresh, key=lambda t: t[0])[1] if fresh else self.candidates[0]

    @property
    def dir(self) -> Path:
        return self.active_dir()

    def _ensure(self, directory: Path | None = None) -> None:
        # Creates the directory being written to (the active one by default), not
        # the module default: if a custom directory was passed (tests, config),
        # creation and writing must point to the same place. A legacy candidate is
        # only ever active when PT already created it, so the server never creates
        # the legacy tree.
        (directory or self.active_dir()).mkdir(parents=True, exist_ok=True, mode=0o700)

    # -- Script Engine liveness ----------------------------------------

    def pt_alive(self) -> bool:
        """True if the Script Engine touched a heartbeat recently, in any candidate."""
        age = _heartbeat_age(self.active_dir())
        return age is not None and age < HEARTBEAT_FRESH_S

    def mailbox_status(self) -> dict:
        """Which mailbox is in use, for diagnostics. `legacy` means PT is polling a
        directory other than the canonical one (the released V5.2 on macOS/Linux)."""
        d = self.active_dir()
        age = _heartbeat_age(d)
        alive = age is not None and age < HEARTBEAT_FRESH_S
        return {"dir": str(d), "alive": alive, "age_s": round(age, 1) if alive else None,
                "legacy": d != self.candidates[0]}

    # -- sending ----------------------------------------------------------

    def _next_name(self) -> str:
        # Monotonic sequence within the process + pid, so concurrent MCP
        # processes sharing the same mailbox do not collide.
        self._seq += 1
        return f"{os.getpid()}_{self._seq:06d}"

    def _write_atomic(self, path: Path, text: str) -> None:
        # tmp + replace: the Script Engine, which lists the directory, never sees a
        # half-written file (replace is atomic within the volume).
        #
        # EXACT bytes: write in binary, not write_text. On Windows text mode
        # translates \n -> \r\n, and a real CR/LF inside a JS string literal is a
        # SyntaxError. The command (e.g. configureIosDevice with \n between
        # CLI lines) must reach the Script Engine exactly as it was generated.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(text.encode("utf-8"))
        os.replace(tmp, path)

    def send(self, js_code: str) -> bool:
        """Queues a fire-and-forget command. Does not wait for a result."""
        directory = self.active_dir()
        try:
            self._ensure(directory)
            name = self._next_name()
            self._write_atomic(directory / f"req_{name}.js", js_code)
            return True
        except OSError:
            return False

    def send_and_wait(self, js_code: str, timeout: float = 12.0) -> str | None:
        """Queues a command and waits for its res_<name>.txt.

        The Script Engine wraps the execution and writes the result; here the
        appearance of the response file is polled and then consumed. The answer
        is read from the same mailbox the request went to.
        """
        directory = self.active_dir()
        try:
            self._ensure(directory)
        except OSError:
            return None
        name = self._next_name()
        res_path = directory / f"res_{name}.txt"
        try:
            self._write_atomic(directory / f"req_{name}.js", js_code)
        except OSError:
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if res_path.exists():
                    body = res_path.read_text(encoding="utf-8")
                    res_path.unlink(missing_ok=True)
                    return body
            except OSError:
                pass
            time.sleep(0.1)
        # Timeout: we leave the req in case the Script Engine processes it late, but we clean
        # up the res if it appeared between the last check and now.
        try:
            res_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None
