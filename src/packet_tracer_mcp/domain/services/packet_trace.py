"""
Reading PT's simulation event list: what each packet did and why.

Pure logic, no bridge — testable with synthetic dicts, like topology_diff.

What makes this useful is not the packet list but the decision log: PT
exposes, per frame and per OSI layer, the same prose explanation it shows in the
"PDU Details" panel of its GUI. Verified against PT 9.0.0.0810 with a ping from
PC1 to its gateway:

    L3 :: The source IP address is not specified. The device sets it to the port's IP address.
    L3 :: The destination IP address is in the same subnet. The device sets the next-hop to destination.
    L2 :: The next-hop IP address is not in the ARP table. The ARP process ... buffers this packet.

That turns "the ping does not work" into a concrete cause.
"""

from __future__ import annotations

# getUserTrafficType() returns an integer. 0 is ICMP and 5 is ARP, MEASURED (ping
# from PC1 to its gateway: the ICMP stays buffered and the ARP broadcast goes out first).
# 11 is STP, MEASURED (PT 9.0.1: a 2960's BPDU frames, whose UserTraffic's
# getTrafficTypeString() is "STP").
# Anything else has not been observed, so the raw value is returned instead of inventing names.
TRAFFIC_TYPES = {0: "ICMP", 5: "ARP", 11: "STP"}

# UserCreatedPDU.addSimplePdu() returns ADD_PDU_ERROR. Int values decoded from
# the enum in PT 9.0.1's pt-cep-java-framework jar; 20 and 30 also measured live.
ADD_PDU_ERRORS = {
    10: "PT is not in add-PDU mode",
    20: "there is no device with the source name",
    21: "the source device has no IP address",
    25: "the selected device has no IP address",
    30: "there is no device with the destination name",
    31: "the destination device has no IP address",
}

# UserTraffic.getStatus() returns TrafficStatus (same jar): the "Last Status"
# column of PT's PDU list. 3 measured live on a successful ping.
TRAFFIC_STATUS = {0: "not_sent", 1: "in_progress", 2: "failed", 3: "successful"}

# Precedence order when deriving ONE state per frame. Whatever blocks goes first:
# a dropped frame matters more than a "sent" one in the same tick.
_STATUS_ORDER = (
    ("dropped", "dropped"),
    ("collided_on_link", "collided_on_link"),
    ("collided_at_device", "collided_at_device"),
    ("not_forwarded", "not_forwarded"),
    ("unexpected", "unexpected"),
    ("buffered", "buffered"),
    ("in_transit", "in_transit"),
    ("accepted", "accepted"),
    ("sent", "sent"),
)

# States meaning "this packet did not reach its destination".
FAILURE_STATUSES = frozenset({
    "dropped", "collided_on_link", "collided_at_device",
    "not_forwarded", "unexpected",
})


def traffic_type_label(raw) -> str:
    """Label for the traffic type; passes the raw value through if it was not observed."""
    return TRAFFIC_TYPES.get(raw, f"type{raw}")


def frame_status(frame: dict) -> str:
    """A single state per frame, derived from PT's boolean flags."""
    for flag, status in _STATUS_ORDER:
        if frame.get(flag):
            return status
    return "pending"


def summarize_trace(frames: list[dict]) -> dict:
    """Groups the event list and separates what failed from what did not."""
    by_status: dict[str, int] = {}
    by_device: dict[str, int] = {}
    failures: list[dict] = []

    for frame in frames:
        status = frame_status(frame)
        frame["status"] = status
        by_status[status] = by_status.get(status, 0) + 1

        device = frame.get("device") or "?"
        by_device[device] = by_device.get(device, 0) + 1

        if status in FAILURE_STATUSES:
            failures.append({
                "device": device,
                "status": status,
                "destination": frame.get("destination", ""),
                "traffic": frame.get("traffic_type", ""),
                # The last decision is the one that explains the outcome.
                "reason": (frame.get("decisions") or [{}])[-1].get("description", ""),
            })

    return {
        "frames": len(frames),
        "by_status": dict(sorted(by_status.items())),
        "by_device": dict(sorted(by_device.items())),
        "failures": failures,
        "clean": not failures,
    }


def _path(hops: list[dict]) -> list[str]:
    """Devices in the order the PDU visited them, repeats in a row collapsed."""
    path: list[str] = []
    for hop in hops:
        device = hop.get("device") or "?"
        if not path or path[-1] != device:
            path.append(device)
    return path


def summarize_pdu_run(data: dict, source: str, destination: str) -> dict:
    """Turns the reply of simple_pdu_js into a verdict, a path and a cause."""
    if not data.get("ok"):
        code = data.get("add_error")
        return {
            "result": "not_added",
            "add_error": code,
            "summary": (f"PT refused the PDU {source} → {destination}: "
                        f"{ADD_PDU_ERRORS.get(code, f'ADD_PDU_ERROR {code}')}."),
        }

    hops = data.get("hops") or []
    for hop in hops:
        hop["traffic_type"] = traffic_type_label(hop.pop("traffic_type_raw", None))
        hop["status"] = frame_status(hop)
        if not hop.get("decisions"):
            hop.pop("decisions", None)

    raw = data.get("status")
    result = TRAFFIC_STATUS.get(raw, f"status{raw}")
    path = _path(hops)
    failure = next((h for h in hops if h["status"] in FAILURE_STATUSES), None)
    out = {
        "result": result,
        "source": source,
        "destination": destination,
        "path": path,
        "reached_destination": destination in path,
        "entered_simulation": bool(data.get("entered_simulation")),
        "hops": hops,
    }
    if not data.get("animated"):
        out["steps"] = data.get("steps", 0)
    if data.get("hops_omitted"):
        out["hops_omitted"] = data["hops_omitted"]
    for key in ("animated", "warm_up_rounds", "cleared_pdus"):
        if key in data:
            out[key] = data[key]

    route = " → ".join(path) if path else "(no frame)"
    if result == "successful":
        out["summary"] = f"Successful: {source} → {destination} and back. Path: {route}."
    elif result == "failed":
        reason = ""
        if failure:
            out["failed_at"] = failure.get("device", "")
            reason = (failure.get("decisions") or [{}])[-1].get("description", "")
            out["reason"] = reason
        where = f" at {out['failed_at']}" if out.get("failed_at") else ""
        out["summary"] = (f"Failed{where}: {source} → {destination}. Path: {route}."
                          + (f" Cause: {reason}" if reason else ""))
    elif data.get("animated"):
        out["summary"] = (f"Not finished before timeout_s ({result}); playback paused. "
                          f"Path so far: {route}. Call again with a higher timeout_s.")
    else:
        out["summary"] = (f"Not finished after {out.get('steps', 0)} step(s) ({result}). "
                          f"Path so far: {route}. Step on with pt_simulation_step "
                          "or call again with a higher max_steps.")
    return out
