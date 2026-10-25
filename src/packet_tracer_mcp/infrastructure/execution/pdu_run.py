"""Drive one simple PDU through PT's Simulation mode (pt_simulate_pdu).

`send(js, timeout) -> str | None` is injected (BridgeContext.send_and_wait in
the tool, a script in the tests), like console_session.run_commands.

Order, each step learned live on PT 9.0.1 (2026-10-26):

1. Warm-up (optional): send the PDU a few times in Realtime. Every L3 hop
   with a cold ARP cache drops the packet that triggers its ARP (R1, then
   FW1, then Remote-R on the lab topology), and an ASA ARPs for each inside
   host. Without it the first simulated PDU shows red X's and Fails.
2. Prepare: Simulation mode, empty the PDU list (removes the warm-up rows),
   hide every event type but ICMP (STP BPDUs dropped by PCs are red X's).
3. Run: headless (engine forward() in one call, fast) or animated (the
   Play button, then polling: the canvas only moves between script calls).
   Animated, PT's window must show Simulation too: on the Mac
   setSimulationMode(true) leaves it in Realtime and Play draws nothing
   (live 2026-10-26), so `show_simulation` presses the window's switch.
"""

from __future__ import annotations

import json
import time
from typing import Callable

from ..generator.simulation_js import (
    MAX_STEPS, poll_play_js, prepare_js, simple_pdu_js, start_play_js, warm_up_js,
    window_mode_js,
)

Send = Callable[[str, float], "str | None"]

WARM_UP_ROUNDS = 4       # one per cold L3 hop on a 3-router path, plus one
WARM_UP_GAP_S = 2.0      # a Realtime PDU crosses the lab path well under this
POLL_EVERY_S = 1.0
MAX_TIMEOUT_S = 600.0
SWITCH_SETTLE_S = 0.5    # the window followed its switch within this (probe, 2026-10-26)

WINDOW_IN_REALTIME = (
    "PT's window stayed in Realtime although the engine is in Simulation, so Play "
    "would animate nothing on the canvas. Click Simulation (bottom right of PT's "
    "window), then run pt_simulate_pdu again."
)


class PduRunError(Exception):
    """PT did not answer, or answered something unreadable."""


def _window_to_simulation(send: Send, show_simulation: Callable[[], None] | None,
                          sleep: Callable[[float], None]) -> str | None:
    """Press the window's Simulation switch; None once the window shows it,
    else why not."""
    if show_simulation is None:
        return WINDOW_IN_REALTIME
    try:
        show_simulation()
    except Exception as exc:  # the UI path's own reason (Accessibility, no switch...)
        return f"{WINDOW_IN_REALTIME} Switching it automatically failed: {exc}"
    sleep(SWITCH_SETTLE_S)
    if _call(send, window_mode_js(), 10.0).get("window_sim") is False:
        return WINDOW_IN_REALTIME
    return None


def _call(send: Send, js: str, timeout: float) -> dict:
    raw = send(js, timeout)
    if raw is None:
        raise PduRunError("timeout")
    if raw.startswith(("ERROR:", "PT_ERROR")):
        raise PduRunError(f"PT error: {raw}")
    try:
        return json.loads(raw)
    except Exception as exc:
        raise PduRunError(f"Unreadable reply from PT: {exc}") from exc


def run_simulated_pdu(
    send: Send,
    source: str,
    destination: str,
    *,
    animate: bool = False,
    warm_up: bool = True,
    clear_list: bool = True,
    only_icmp: bool = True,
    max_steps: int = 200,
    timeout_s: float = 120.0,
    include_decisions: bool = False,
    show_simulation: Callable[[], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    """Run the PDU and return the raw run data for summarize_pdu_run.

    The result is simple_pdu_js's shape, plus `warm_up_rounds`,
    `cleared_pdus` and `animated`. Raises PduRunError when PT fails to answer.
    `show_simulation` (animated runs only) presses PT's Simulation switch when
    the window stayed in Realtime; it raises when it can't. Without it, or if
    the window is still in Realtime afterwards, the run stops before Play with
    `{ok:false, window_error}`.
    """
    warmed = 0
    if warm_up:
        for _ in range(WARM_UP_ROUNDS):
            data = _call(send, warm_up_js(source, destination), 10.0)
            if not data.get("ok"):
                return data  # refused: same {ok:false, add_error} as a run
            warmed += 1
            sleep(WARM_UP_GAP_S)

    prep = _call(send, prepare_js(clear_list=clear_list, only_icmp=only_icmp), 15.0)
    extra = {"warm_up_rounds": warmed, "cleared_pdus": prep.get("deleted", 0),
             "animated": bool(animate)}

    if not animate:
        steps = max(1, min(int(max_steps), MAX_STEPS))
        js = simple_pdu_js(source, destination, max_steps=steps,
                           include_decisions=include_decisions)
        # Measured: 30 forward() calls take well under a second.
        data = _call(send, js, 60.0)
        data["entered_simulation"] = bool(data.get("entered_simulation")
                                          or prep.get("entered_simulation"))
        data.update(extra)
        return data

    # Only a definite Realtime counts: None means PT could not tell.
    if prep.get("window_sim") is False:
        why = _window_to_simulation(send, show_simulation, sleep)
        if why:
            return {"ok": False, "window_error": why, **extra}
        extra["window_switched"] = True

    start = _call(send, start_play_js(source, destination), 10.0)
    if not start.get("ok"):
        return start
    n0 = int(start.get("frames_before", 0))
    deadline = clock() + max(1.0, min(float(timeout_s), MAX_TIMEOUT_S))
    while True:
        sleep(POLL_EVERY_S)
        finish = clock() >= deadline
        data = _call(send, poll_play_js(source, destination, n0, finish=finish,
                                        include_decisions=include_decisions), 15.0)
        if "hops" in data:
            break
    data["entered_simulation"] = bool(start.get("entered_simulation")
                                      or prep.get("entered_simulation"))
    data["timed_out"] = data.get("status") not in (2, 3)
    data.update(extra)
    return data
