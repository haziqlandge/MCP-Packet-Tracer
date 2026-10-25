"""JS for running one simple PDU through PT's Simulation mode.

This is the GUI's *Add Simple PDU* followed by *Capture / Forward* (or *Play*)
until the PDU's line in the PDU list says Successful or Failed. Every call
was read in PT 9.0.1's IpcAPI reference and exercised live (2026-10-26):

- `ipc.appWindow().getUserCreatedPDU().addSimplePdu(src, dst)` takes two
  device NAMES and returns ADD_PDU_ERROR (0 = no error; 20 / 30 measured for
  an unknown source / destination). It works in Realtime too: the PDU is
  sent at once, which is how the ARP caches are warmed.
- `UserCreatedPDU.deletePDU(0)` removes the first row of the PDU list and
  throws once the list is empty (there is no count getter).
- `FrameInstance.getTrafficSource()` returns the UserTraffic (the PDU) that
  produced the frame, so this PDU's frames can be told apart from STP and
  every other background frame in the event list.
- `UserTraffic.getStatus()` is TrafficStatus: 0 not sent, 1 in progress,
  2 failed, 3 successful (the PDU list's "Last Status").
- `ipc.simulation().forward()` steps the engine synchronously but does NOT
  redraw the GUI: the Simulation Panel's event list stays empty until
  `SimulationPanel.populateEventList()`. `SimulationPanel.play()` is the
  Play button (a second call pauses); the canvas only animates between
  script calls, so a visible run is play + polling from Python.
- `SimulationPanel.setFilter(protocol, bool)` sets one event-list filter.
  Hiding STP matters: a 2960 floods BPDUs every 2 s, PCs drop them, and PT
  draws each drop as a red X on the canvas.

Same conventions as host_js: one IIFE per call, the input travels as ONE
`json.dumps` object.
"""

from __future__ import annotations

import json

# Hard caps; the tool clamps its arguments to these before building the JS.
MAX_STEPS = 1000
MAX_HOPS = 100

# The protocols in PT 9.0.1's "Event List Filters" (read from its GUI).
EVENT_FILTERS = (
    "ACL Filter", "ARP", "BGP", "Bluetooth", "CAPWAP", "CDP", "DHCP", "DHCPv6",
    "DNS", "DTP", "EAPOL", "EIGRP", "EIGRPv6", "FTP", "H.323", "HSRP", "HSRPv6",
    "HTTP", "HTTPS", "ICMP", "ICMPv6", "IEC", "IPSec", "ISAKMP", "IoT", "IoT TCP",
    "LACP", "LLDP", "MODBUS", "Meraki", "NDP", "NETFLOW", "NTP", "OSPF", "OSPFv6",
    "PAgP", "POP3", "PPP", "PPPoED", "PTP", "Profinet", "RADIUS", "REP", "RIP",
    "RIPng", "RTP", "SCCP", "SMTP", "SNMP", "SSH", "STP", "SYSLOG", "TACACS",
    "TCP", "TFTP", "Telnet", "UDP", "USB", "VTP",
)

_FRAME_JS = (
    # One hop of this PDU. Every getter sits in its own try: a buffered frame
    # has no egress port and getOutPort(0) throws.
    "function __hop(i,f,wd){"
    "function g(fn){try{return fn();}catch(e){return null;}}"
    "var dv=g(function(){return f.getDevice();});"
    "var pv=g(function(){return f.getPreviousDevice();});"
    "var ip=g(function(){return f.getInPort();});"
    "var op=g(function(){return f.getOutPortCount()>0?f.getOutPort(0):null;});"
    "var h={index:i,device:dv?String(dv.getName()):'',"
    "previous_device:pv?String(pv.getName()):null,"
    "in_port:ip?String(ip.getName()):null,out_port:op?String(op.getName()):null,"
    "traffic_type_raw:g(function(){return f.getUserTrafficType();}),"
    "sim_time:g(function(){return f.getStartSimTime();}),"
    "sent:!!g(function(){return f.isFrameSent();}),"
    "accepted:!!g(function(){return f.isFrameAccepted();}),"
    "dropped:!!g(function(){return f.isFrameDropped();}),"
    "buffered:!!g(function(){return f.isFrameBuffered();}),"
    "in_transit:!!g(function(){return f.isFrameOnTransit();}),"
    "collided_at_device:!!g(function(){return f.isFrameCollidedAtDevice();}),"
    "collided_on_link:!!g(function(){return f.isFrameCollidedOnLink();}),"
    "not_forwarded:!!g(function(){return f.isFrameNotForwarded();}),"
    "unexpected:!!g(function(){return f.isFrameUnexpected();}),decisions:[]};"
    "var bad=h.dropped||h.collided_at_device||h.collided_on_link||h.not_forwarded||h.unexpected;"
    "if(wd||bad){var dc=g(function(){return f.getFlowChartNodeCount();})||0;"
    "for(var j=0;j<dc;j++){"
    # getFrameDecsionAt: the typo is PT's. Its fields are properties.
    "var d=g(function(){return f.getFrameDecsionAt(j);});"
    "if(d){h.decisions.push({layer:d.osiLayer,inbound:!!d.osiIn,"
    "description:String(d.description)});}}}"
    "return h;}"
)

# `mine`, `status` and `collect` need `c` ({src, dst, n0, wd, cap}) and `s`.
_TRACK_JS = (
    # This PDU's frames: their UserTraffic names our source and destination.
    "function mine(f){try{var t=f.getTrafficSource();"
    "return !!t&&String(t.getCanonicalSource())===c.src"
    "&&String(t.getCanonicalDestination())===c.dst;}catch(e){return false;}}"
    "var first=-1;"
    "function status(){var n=s.getFrameInstanceCount();"
    "if(first<0){for(var i=c.n0;i<n;i++){var f=s.getFrameInstanceAt(i);"
    "if(f&&mine(f)){first=i;break;}}}"
    "if(first<0){return 0;}"
    "try{return s.getFrameInstanceAt(first).getTrafficSource().getStatus();}"
    "catch(e){return 0;}}"
    "function collect(){var hops=[];var n=s.getFrameInstanceCount();var more=0;"
    "for(var k=(first<0?c.n0:first);k<n;k++){var f=s.getFrameInstanceAt(k);"
    "if(!f||!mine(f)){continue;}"
    "if(hops.length>=c.cap){more++;continue;}hops.push(__hop(k,f,c.wd));}"
    "return {hops:hops,hops_omitted:more};}"
)

_PANEL_JS = "var p=ipc.appWindow().getSimulationPanel();"


def _cfg(**fields) -> str:
    return f"var c={json.dumps(fields)};"


def warm_up_js(source: str, destination: str) -> str:
    """Send the PDU once in Realtime so every hop learns its ARP entries.

    Reports `{ok, add_error, was_simulation}`. The Realtime PDU is not
    tracked (it has no frames to read); the caller waits, then clears it.
    """
    return (
        "(function(){" + _cfg(src=source, dst=destination) + _PANEL_JS +
        "var s=ipc.simulation();var was=!!s.isSimulationMode();"
        "if(was){if(p.isPlaying()){p.play();}s.setSimulationMode(false);}"
        "var err=ipc.appWindow().getUserCreatedPDU().addSimplePdu(c.src,c.dst);"
        "reportResult(JSON.stringify({ok:err===0,add_error:err,was_simulation:was}));"
        "})();"
    )


def prepare_js(*, clear_list: bool = True, only_icmp: bool = True) -> str:
    """Enter Simulation mode, optionally empty the PDU list and hide all but ICMP."""
    return (
        "(function(){"
        + _cfg(clear=bool(clear_list), icmp=bool(only_icmp), filters=list(EVENT_FILTERS))
        + _PANEL_JS +
        "var s=ipc.simulation();var was=!!s.isSimulationMode();"
        "if(!was){s.setSimulationMode(true);}if(p.isPlaying()){p.play();}"
        "var del=0;if(c.clear){var u=ipc.appWindow().getUserCreatedPDU();"
        "for(var i=0;i<500;i++){try{u.deletePDU(0);del++;}catch(e){break;}}}"
        "if(c.icmp){for(var k=0;k<c.filters.length;k++){"
        "try{p.setFilter(c.filters[k],c.filters[k]==='ICMP');}catch(e){}}}"
        "p.populateEventList();"
        "reportResult(JSON.stringify({ok:true,entered_simulation:!was,deleted:del}));"
        "})();"
    )


def simple_pdu_js(
    source: str, destination: str, *, max_steps: int = 200, include_decisions: bool = False,
) -> str:
    """Add the PDU and step the engine until it ends; one call, nothing animates.

    Reports `{ok, add_error}` when PT refuses the PDU, otherwise `{ok:true,
    status, steps, entered_simulation, frames_before, hops:[...]}` with only the
    frames that belong to this PDU. The GUI's event list is refreshed at the end.
    """
    cfg = _cfg(src=source, dst=destination, max=max(1, min(int(max_steps), MAX_STEPS)),
               wd=bool(include_decisions), cap=MAX_HOPS, n0=0)
    return (
        "(function(){" + cfg + _FRAME_JS +
        "var s=ipc.simulation();var was=!!s.isSimulationMode();"
        "if(!was){s.setSimulationMode(true);}"
        "c.n0=s.getFrameInstanceCount();"
        "var err=ipc.appWindow().getUserCreatedPDU().addSimplePdu(c.src,c.dst);"
        "if(err!==0){reportResult(JSON.stringify({ok:false,add_error:err,"
        "entered_simulation:!was}));return;}"
        + _TRACK_JS +
        "var st=status();var steps=0;"
        "while(steps<c.max&&st!==2&&st!==3){s.forward();steps++;st=status();}"
        "var r=collect();"
        # Without this the GUI keeps an event list out of step with the engine.
        "try{ipc.appWindow().getSimulationPanel().populateEventList();}catch(e){}"
        "reportResult(JSON.stringify({ok:true,status:st,steps:steps,"
        "entered_simulation:!was,frames_before:c.n0,sim_time:s.getCurrentSimTime(),"
        "hops:r.hops,hops_omitted:r.hops_omitted}));"
        "})();"
    )


def start_play_js(source: str, destination: str) -> str:
    """Add the PDU and press Play: the canvas animates it after this call returns.

    Reports `{ok:true, frames_before}` (pass it to poll_play_js) or `{ok:false,
    add_error}`.
    """
    return (
        "(function(){" + _cfg(src=source, dst=destination) + _PANEL_JS +
        "var s=ipc.simulation();var was=!!s.isSimulationMode();"
        "if(!was){s.setSimulationMode(true);}"
        "var n0=s.getFrameInstanceCount();"
        "var err=ipc.appWindow().getUserCreatedPDU().addSimplePdu(c.src,c.dst);"
        "if(err!==0){reportResult(JSON.stringify({ok:false,add_error:err,"
        "entered_simulation:!was}));return;}"
        "p.populateEventList();if(!p.isPlaying()){p.play();}"
        "reportResult(JSON.stringify({ok:true,frames_before:n0,entered_simulation:!was}));"
        "})();"
    )


def poll_play_js(
    source: str, destination: str, frames_before: int, *,
    finish: bool = False, include_decisions: bool = False,
) -> str:
    """Read the playing PDU's status; pause once it ended (or when `finish`).

    Reports `{ok:true, status, playing}`, plus the hops once the PDU ended or
    `finish` is set.
    """
    cfg = _cfg(src=source, dst=destination, n0=max(0, int(frames_before)),
               wd=bool(include_decisions), cap=MAX_HOPS, finish=bool(finish))
    return (
        "(function(){" + cfg + _FRAME_JS + _PANEL_JS +
        "var s=ipc.simulation();" + _TRACK_JS +
        "var st=status();var end=st===2||st===3||c.finish;"
        "if(end&&p.isPlaying()){p.play();}"
        "var o={ok:true,status:st,playing:!!p.isPlaying(),"
        "sim_time:s.getCurrentSimTime(),frames_before:c.n0};"
        "if(end){var r=collect();o.hops=r.hops;o.hops_omitted=r.hops_omitted;"
        "p.populateEventList();}"
        "reportResult(JSON.stringify(o));"
        "})();"
    )
