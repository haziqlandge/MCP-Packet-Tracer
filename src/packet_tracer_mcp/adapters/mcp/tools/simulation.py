"""Simulation tools: mode, step, packet trace, simple PDU."""

from __future__ import annotations

import json
from mcp.server.fastmcp import FastMCP
from ....domain.services.packet_trace import (
    summarize_pdu_run, summarize_trace, traffic_type_label,
)
from ....infrastructure.execution.pdu_run import PduRunError, run_simulated_pdu
from ....infrastructure.ui.presenter import Presenter
from ..bridge_context import BridgeContext, TIMEOUT_MSG
from ....shared.utils import reply_json


def register(mcp: FastMCP, ctx: BridgeContext) -> None:
    """Register this module's tools on `mcp`."""
    _TIMEOUT_MSG = TIMEOUT_MSG
    _bridge_send_and_wait = ctx.send_and_wait
    _check_bridge = ctx.check_bridge

    # ------------------------------------------------------------------
    # SIMULATION — mode, step by step and reading the event list
    # ------------------------------------------------------------------

    @mcp.tool()
    def pt_simulation_mode(on: bool = True) -> str:
        """
        Switches PT between Realtime and Simulation mode.

        In Simulation mode packets do NOT move on their own: they stay queued in the
        event list and have to be moved with pt_simulation_step. That is what
        allows reading the path packet by packet with pt_read_packet_trace.

        Parameters:
        - on: True enters Simulation (default), False goes back to Realtime.

        Example: pt_simulation_mode(on=True)
        """
        err = _check_bridge()
        if err:
            return err

        want = "true" if on else "false"
        js = (
            "try {"
            "  var __s = ipc.simulation();"
            "  var __before = !!__s.isSimulationMode();"
            f"  __s.setSimulationMode({want});"
            "  reportResult(JSON.stringify({"
            "    before: __before, after: !!__s.isSimulationMode(),"
            "    frames: __s.getFrameInstanceCount(), sim_time: __s.getCurrentSimTime()"
            "  }));"
            "} catch (__e) { reportResult('ERROR:' + __e); }"
        )
        raw = _bridge_send_and_wait(js, timeout=10.0)
        if raw is None:
            return _TIMEOUT_MSG
        if raw.startswith("ERROR:"):
            return f"PT error: {raw}"
        try:
            data = json.loads(raw)
        except Exception as exc:
            return f"Unreadable reply from PT: {exc}"

        mode = "Simulation" if data["after"] else "Realtime"
        data["summary"] = (
            f"{mode} mode. {data['frames']} frame(s) in the event list."
            if data["before"] != data["after"]
            else f"Already in {mode} mode; no changes."
        )
        return reply_json(data)

    @mcp.tool()
    def pt_simulation_step(action: str = "forward", times: int = 1) -> str:
        """
        Steps the simulation forward, back, or resets it.

        Requires Simulation mode (pt_simulation_mode(on=True)). Each
        step moves the packets one event; after stepping, read the result
        with pt_read_packet_trace.

        Parameters:
        - action: "forward" (default) | "back" | "reset".
        - times: how many steps to take (1-100, ignored for "reset").

        Example: step 5 events forward:
          pt_simulation_step(action="forward", times=5)
        """
        err = _check_bridge()
        if err:
            return err

        act = action.strip().lower()
        if act not in ("forward", "back", "reset"):
            return json.dumps(
                {"error": f"Invalid action: '{action}'. Use forward, back or reset."},
                ensure_ascii=False,
            )
        steps = max(1, min(int(times), 100))

        call = {"forward": "__s.forward();", "back": "__s.backward();",
                "reset": "__s.resetSimulation();"}[act]
        loop = call if act == "reset" else f"for (var __i = 0; __i < {steps}; __i++) {{ {call} }}"
        js = (
            "try {"
            "  var __s = ipc.simulation();"
            "  if (!__s.isSimulationMode()) {"
            "    reportResult(JSON.stringify({ simulation_mode: false }));"
            "  } else {"
            "    var __b = __s.getFrameInstanceCount();"
            f"   {loop}"
            "    reportResult(JSON.stringify({"
            "      simulation_mode: true, frames_before: __b,"
            "      frames_after: __s.getFrameInstanceCount(),"
            "      sim_time: __s.getCurrentSimTime(),"
            "      current_index: __s.getCurrentFrameInstanceIndex()"
            "    }));"
            "  }"
            "} catch (__e) { reportResult('ERROR:' + __e); }"
        )
        raw = _bridge_send_and_wait(js, timeout=15.0)
        if raw is None:
            return _TIMEOUT_MSG
        if raw.startswith("ERROR:"):
            return f"PT error: {raw}"
        try:
            data = json.loads(raw)
        except Exception as exc:
            return f"Unreadable reply from PT: {exc}"

        if not data.get("simulation_mode"):
            return (
                "PT is in Realtime mode, so there is nothing to step. "
                "Call pt_simulation_mode(on=True) first."
            )
        data["action"] = act
        data["steps"] = 1 if act == "reset" else steps
        data["summary"] = (
            f"{act} x{data['steps']} — {data['frames_after']} frame(s) in the event list "
            f"(before {data['frames_before']})."
        )
        return reply_json(data)

    @mcp.tool()
    def pt_read_packet_trace(
        limit: int = 20,
        device: str = "",
        include_decisions: bool = True,
    ) -> str:
        """
        Reads the simulation's event list: what each packet did and WHY.

        Besides the path (device, ingress/egress port, source,
        destination, traffic type and outcome) it returns the decision log that
        PT generates per OSI layer — the same text as the "PDU Details" panel of its
        GUI. That is where the real cause of a failing ping shows up, for
        example: "The next-hop IP address is not in the ARP table."

        Requires Simulation mode with generated traffic (pt_simulation_mode(on=True)
        and then a ping, or pt_simulation_step so the events move on).

        Parameters:
        - limit: maximum frames to return (1-200, default 20).
        - device: if given, only the frames that went through that device.
        - include_decisions: if False, omits the per-layer log (shorter reply).

        Example: see why a ping is dropped:
          pt_read_packet_trace(limit=10)
        """
        err = _check_bridge()
        if err:
            return err

        lim = max(1, min(int(limit), 200))
        want = json.dumps(device.strip())
        dec = "true" if include_decisions else "false"
        js = (
            "try {"
            "  var __s = ipc.simulation();"
            f"  var __lim = {lim}; var __want = {want}; var __wd = {dec};"
            "  var __n = __s.getFrameInstanceCount();"
            "  var __out = [];"
            "  for (var __i = 0; __i < __n && __out.length < __lim; __i++) {"
            "    try {"
            "      var __f = __s.getFrameInstanceAt(__i);"
            "      if (!__f) continue;"
            "      var __dev = __f.getDevice();"
            "      var __dn = __dev ? __dev.getName() : '';"
            "      if (__want && __dn !== __want) continue;"
            "      var __prev = __f.getPreviousDevice();"
            "      var __ip = __f.getInPort();"
            "      var __op = null;"
            # getOutPort(0) throws when getOutPortCount() is 0 (frame in a buffer,
            # no egress port chosen yet).
            "      try {"
            "        if (__f.getOutPortCount() > 0) {"
            "          var __o = __f.getOutPort(0); __op = __o ? __o.getName() : null;"
            "        }"
            "      } catch (__oe) {}"
            "      var __dl = [];"
            "      if (__wd) {"
            # There is no getDecisionCount(); the flowchart's node count matches
            # the number of decisions (verified: 6/6 and 3/3 on a real ping).
            "        var __dc = __f.getFlowChartNodeCount();"
            "        for (var __j = 0; __j < __dc; __j++) {"
            "          try {"
            # getFrameDecsionAt: the typo is PT's, not ours.
            "            var __d = __f.getFrameDecsionAt(__j);"
            "            if (!__d) continue;"
            "            __dl.push({ layer: __d.osiLayer, inbound: !!__d.osiIn,"
            "                        description: __d.description });"
            "          } catch (__de) {}"
            "        }"
            "      }"
            "      __out.push({"
            "        index: __i, device: __dn,"
            "        previous_device: __prev ? __prev.getName() : null,"
            "        in_port: __ip ? __ip.getName() : null, out_port: __op,"
            "        source: __f.getSourceString(), destination: __f.getDestinationString(),"
            "        traffic_type_raw: __f.getUserTrafficType(),"
            "        sim_time: __f.getStartSimTime(), transit_time: __f.getTransitTime(),"
            "        sent: !!__f.isFrameSent(), accepted: !!__f.isFrameAccepted(),"
            "        dropped: !!__f.isFrameDropped(), buffered: !!__f.isFrameBuffered(),"
            "        in_transit: !!__f.isFrameOnTransit(),"
            "        collided_at_device: !!__f.isFrameCollidedAtDevice(),"
            "        collided_on_link: !!__f.isFrameCollidedOnLink(),"
            "        not_forwarded: !!__f.isFrameNotForwarded(),"
            "        unexpected: !!__f.isFrameUnexpected(),"
            "        decisions: __dl"
            "      });"
            "    } catch (__pe) {}"
            "  }"
            "  reportResult(JSON.stringify({"
            "    total: __n, simulation_mode: !!__s.isSimulationMode(), frames: __out"
            "  }));"
            "} catch (__e) { reportResult('ERROR:' + __e); }"
        )

        raw = _bridge_send_and_wait(js, timeout=20.0)
        if raw is None:
            return _TIMEOUT_MSG
        if raw.startswith("ERROR:"):
            return f"PT error: {raw}"
        try:
            data = json.loads(raw)
        except Exception as exc:
            return f"Unreadable reply from PT: {exc}"

        frames = data.get("frames", [])
        for frame in frames:
            frame["traffic_type"] = traffic_type_label(frame.pop("traffic_type_raw", None))

        result = summarize_trace(frames)
        result["total_in_event_list"] = data.get("total", 0)
        result["simulation_mode"] = data.get("simulation_mode", False)
        result["trace"] = frames

        if not data.get("simulation_mode"):
            result["summary"] = (
                "PT is in Realtime mode: the event list does not keep packets. "
                "Call pt_simulation_mode(on=True) and generate traffic."
            )
        elif not frames:
            result["summary"] = (
                "Simulation mode is on but there are no frames. Generate traffic "
                "(for example pt_verify_connectivity) and read again."
            )
        elif result["clean"]:
            normal = len(result["expected_drops"])
            result["summary"] = (
                f"{result['frames']} frame(s) read, none failed."
                + (f" {normal} dropped as normal operation (flooded frames, STP BPDUs, multicast at hosts)." if normal else "")
            )
        else:
            reasons = "; ".join(f["reason"] for f in result["failures"][:3] if f["reason"])
            result["summary"] = (
                f"⚠ {len(result['failures'])} frame(s) did not reach their destination. {reasons}"
            )
        return reply_json(result)

    @mcp.tool()
    def pt_simulate_pdu(
        source: str,
        destination: str,
        animate: bool = False,
        warm_up: bool = True,
        clear_list: bool = True,
        only_icmp: bool = True,
        max_steps: int = 200,
        timeout_s: int = 120,
        include_decisions: bool = False,
    ) -> str:
        """
        Sends a simple PDU (ICMP echo) in Simulation mode and runs it to the end.

        The GUI's "Add Simple PDU" + Capture/Forward or Play, until PT marks the
        PDU Successful or Failed. Returns ONLY this PDU's hops (STP and other
        background frames left out), the device path and, on failure, the
        device that dropped it and PT's reason.

        Parameters:
        - source / destination: device NAMES (pt_query_topology), not IPs.
        - animate: True presses Play so the envelope moves on the canvas
          (slow, ~2 s per hop); False steps the engine at once. If PT's
          window stays in Realtime (macOS), its Simulation switch is
          pressed through UI mode (Accessibility); failing that, the reply
          says to click Simulation instead of animating nothing.
        - warm_up: first sends the PDU in Realtime so cold ARP caches do not
          drop it (each cold router hop drops one packet).
        - clear_list: empties the PDU list first (removes the warm-up rows).
        - only_icmp: hides every other event type, so STP BPDUs dropped by
          PCs no longer show red X's.
        - max_steps (headless, 1-1000) / timeout_s (animated, seconds).
        - include_decisions: PT's per-OSI-layer log on every hop (a dropped
          hop always carries it).

        PT stays in Simulation mode; pt_simulation_mode(on=False) returns to
        Realtime.

        Example: pt_simulate_pdu("PC1", "Remote-Server", animate=True)
        """
        err = _check_bridge()
        if err:
            return err
        src, dst = source.strip(), destination.strip()
        if not src or not dst:
            return json.dumps({"error": "source and destination are device names."})
        try:
            data = run_simulated_pdu(
                _bridge_send_and_wait, src, dst, animate=animate, warm_up=warm_up,
                clear_list=clear_list, only_icmp=only_icmp, max_steps=max_steps,
                timeout_s=timeout_s, include_decisions=include_decisions,
                show_simulation=Presenter(_bridge_send_and_wait).show_simulation_mode,
            )
        except PduRunError as exc:
            return _TIMEOUT_MSG if str(exc) == "timeout" else str(exc)
        return reply_json(summarize_pdu_run(data, src, dst))
