"""pt_simulate_pdu: the JS run under Node against a fake PT, and the verdict.

The fake mirrors what PT 9.0.1 did live (2026-10-26) for a PDU PC1 →
Remote-Server across a router, an ASA and a second router: addSimplePdu
returns 0 and queues one frame; every forward() adds frames, background STP
frames among them; the PDU's UserTraffic status goes 1 → 3 (successful) or
1 → 2 (failed, the ASA dropping the reply on an ARP miss).
"""

from __future__ import annotations

import json

import pytest

from src.packet_tracer_mcp.domain.services.packet_trace import (
    ADD_PDU_ERRORS, TRAFFIC_STATUS, TRAFFIC_TYPES, summarize_pdu_run,
)
from src.packet_tracer_mcp.infrastructure.execution.pdu_run import (
    WARM_UP_ROUNDS, PduRunError, run_simulated_pdu,
)
from src.packet_tracer_mcp.infrastructure.generator.simulation_js import (
    EVENT_FILTERS, MAX_HOPS, MAX_STEPS, poll_play_js, prepare_js, simple_pdu_js,
    start_play_js, warm_up_js,
)

from tests._pt_js import requires_node, run_pt_js

_ARP_DROP = ("The next-hop IP address is not in the ARP table. The ARP process "
             "tries to send an ARP request for that IP address and drops this packet.")


def _sim_fake(path: list[str], *, outcome: int = 3, add_error: int = 0,
              start_sim: bool = True, stp_every_step: bool = True,
              pdu_rows: tuple[str, ...] = (), playing: bool = False) -> str:
    """A PT whose PDU walks `path`, one device per forward(), then ends in `outcome`.

    With outcome 2 the last device of `path` drops the frame with _ARP_DROP.
    The report carries the fake's own counters under `__fake`.
    """
    return (
        f"var __path={json.dumps(path)};var __outcome={outcome};var __adderr={add_error};"
        f"var __stp={json.dumps(stp_every_step)};var __drop={json.dumps(_ARP_DROP)};"
        f"var __sim={json.dumps(start_sim)};var __fw=0;var __added=[];var __status=0;"
        "var __frames=[];var __pos=0;"
        "function __dev(n){return {getName:function(){return n;}};}"
        "function __traffic(src,dst,type){return {getCanonicalSource:function(){return src;},"
        "getCanonicalDestination:function(){return dst;},getTrafficTypeString:function(){return type;},"
        "getStatus:function(){return type==='ICMP'?__status:0;}};}"
        "var __ours=null;"
        "function __frame(dev,prev,traffic,flags,decs){var f={getDevice:function(){return __dev(dev);},"
        "getPreviousDevice:function(){return prev?__dev(prev):null;},"
        "getInPort:function(){return prev?{getName:function(){return 'In';}}:null;},"
        "getOutPortCount:function(){return flags.dropped?0:1;},"
        "getOutPort:function(i){if(flags.dropped){throw 'no out port';}return {getName:function(){return 'Out';}};},"
        "getUserTrafficType:function(){return traffic.getTrafficTypeString()==='ICMP'?0:11;},"
        "getStartSimTime:function(){return __frames.length;},"
        "isFrameSent:function(){return !!flags.sent;},isFrameAccepted:function(){return !!flags.accepted;},"
        "isFrameDropped:function(){return !!flags.dropped;},isFrameBuffered:function(){return false;},"
        "isFrameOnTransit:function(){return false;},isFrameCollidedAtDevice:function(){return false;},"
        "isFrameCollidedOnLink:function(){return false;},isFrameNotForwarded:function(){return false;},"
        "isFrameUnexpected:function(){return false;},"
        "getFlowChartNodeCount:function(){return decs.length;},"
        "getFrameDecsionAt:function(j){return decs[j];},"
        "getTrafficSource:function(){return traffic;}};__frames.push(f);}"
        "var __bg=__traffic('SW1','STP Multicast Address','STP');"
        "var sim={isSimulationMode:function(){return __sim;},setSimulationMode:function(v){__sim=v;},"
        "getFrameInstanceCount:function(){return __frames.length;},"
        "getFrameInstanceAt:function(i){return __frames[i];},getCurrentSimTime:function(){return __fw;},"
        "forward:function(){__fw++;"
        "if(__stp){__frame('PC9','SW1',__bg,{dropped:true},[]);}"
        "if(__status!==1){return;}"
        "__pos++;var last=__pos===__path.length-1;"
        "if(last&&__outcome===2){__frame(__path[__pos],__path[__pos-1],__ours,{dropped:true},"
        "[{osiLayer:3,osiIn:true,description:'GigabitEthernet1/2 receives the frame.'},"
        "{osiLayer:2,osiIn:false,description:__drop}]);__status=2;return;}"
        "__frame(__path[__pos],__path[__pos-1],__ours,last?{accepted:true}:{sent:true},[]);"
        "if(last){__status=__outcome;}}};"
        # The GUI side: the PDU list (deletePDU throws once empty, like PT) and
        # the Simulation Panel's Play toggle, filters and refresh counter.
        f"var __pdus={json.dumps(pdu_rows)};var __playing={json.dumps(playing)};"
        "var __filters={};var __refreshed=0;var __deleted=0;"
        "var panel={isPlaying:function(){return __playing;},play:function(){__playing=!__playing;},"
        "populateEventList:function(){__refreshed++;},"
        "setFilter:function(n,v){__filters[n]=v;}};"
        "var ipc={simulation:function(){return sim;},appWindow:function(){return {"
        "getSimulationPanel:function(){return panel;},"
        "getUserCreatedPDU:function(){return {"
        "deletePDU:function(i){if(!__pdus.length){throw 'Invalid index';}__pdus.splice(i,1);__deleted++;},"
        "addSimplePdu:function(s,d){__added.push([s,d,__sim]);"
        "if(__adderr){return __adderr;}__pdus.push(s+'>'+d);"
        "if(!__sim){return 0;}"
        "__ours=__traffic(s,d,'ICMP');__status=1;__frame(__path[0],null,__ours,{sent:true},[]);"
        "return 0;}};}};}};"
        "var __report=reportResult;reportResult=function(x){var o=JSON.parse(x);"
        "o.__fake={forwards:__fw,added:__added,sim:__sim,playing:__playing,pdus:__pdus,"
        "deleted:__deleted,filters:__filters,refreshed:__refreshed};"
        "__report(JSON.stringify(o));};"
    )


_ROUND_TRIP = ["PC1", "SW1", "R1", "FW1", "Remote-R", "Remote-Server",
               "Remote-R", "FW1", "R1", "SW1", "PC1"]


def _run(tmp_path, fake, src="PC1", dst="Remote-Server", **kw) -> dict:
    reports = run_pt_js(simple_pdu_js(src, dst, **kw), fake, tmp_path)
    assert len(reports) == 1
    return json.loads(reports[0])


@requires_node
class TestSimplePduJs:
    def test_successful_round_trip_keeps_only_this_pdus_frames(self, tmp_path):
        data = _run(tmp_path, _sim_fake(_ROUND_TRIP))
        assert data["ok"] is True and data["status"] == 3
        # One step per hop after the first, and no extra steps once it ended.
        assert data["steps"] == len(_ROUND_TRIP) - 1
        assert data["__fake"]["forwards"] == len(_ROUND_TRIP) - 1
        # The STP frame added on every step is not in the hop list.
        assert [h["device"] for h in data["hops"]] == _ROUND_TRIP
        assert data["hops"][-1]["accepted"] is True

    def test_failure_stops_and_carries_the_drop_reason(self, tmp_path):
        path = _ROUND_TRIP[:8]  # dropped by FW1 on the way back
        data = _run(tmp_path, _sim_fake(path, outcome=2))
        assert data["status"] == 2
        last = data["hops"][-1]
        assert last["device"] == "FW1" and last["dropped"] is True
        # A dropped hop always carries its decisions, even without include_decisions.
        assert last["decisions"][-1]["description"] == _ARP_DROP
        assert all(h["decisions"] == [] for h in data["hops"][:-1])

    def test_include_decisions_reads_every_hop(self, tmp_path):
        data = _run(tmp_path, _sim_fake(_ROUND_TRIP[:8], outcome=2), include_decisions=True)
        assert data["hops"][-1]["decisions"]

    def test_step_limit_is_honoured(self, tmp_path):
        data = _run(tmp_path, _sim_fake(_ROUND_TRIP), max_steps=3)
        assert data["status"] == 1 and data["steps"] == 3
        assert data["__fake"]["forwards"] == 3

    def test_refused_pdu_reports_the_error_and_does_not_step(self, tmp_path):
        data = _run(tmp_path, _sim_fake(_ROUND_TRIP, add_error=20), src="NOPE")
        fake = data.pop("__fake")
        assert data == {"ok": False, "add_error": 20, "entered_simulation": False}
        assert fake["forwards"] == 0 and fake["added"] == [["NOPE", "Remote-Server", True]]

    def test_the_gui_event_list_is_refreshed(self, tmp_path):
        # forward() on the engine does not redraw PT's Simulation Panel.
        data = _run(tmp_path, _sim_fake(_ROUND_TRIP))
        assert data["__fake"]["refreshed"] == 1

    def test_realtime_is_switched_to_simulation_first(self, tmp_path):
        data = _run(tmp_path, _sim_fake(_ROUND_TRIP, start_sim=False))
        assert data["entered_simulation"] is True and data["__fake"]["sim"] is True
        assert data["status"] == 3

    def test_frames_from_before_the_call_are_ignored(self, tmp_path):
        # An earlier PDU between the same devices is already in the event list.
        fake = _sim_fake(_ROUND_TRIP) + (
            "__frame('PC1',null,__traffic('PC1','Remote-Server','ICMP'),{dropped:true},[]);"
        )
        data = _run(tmp_path, fake)
        assert data["frames_before"] == 1
        assert all(h["index"] >= 1 for h in data["hops"])
        assert not any(h["dropped"] for h in data["hops"])

    def test_names_are_json_escaped(self):
        evil = 'PC1"});reportResult("pwned'
        js = simple_pdu_js(evil, "x")
        assert json.dumps(evil) in js
        assert 'reportResult("pwned' not in js.replace(json.dumps(evil), "")

    def test_arguments_are_clamped(self):
        assert f'"max": {MAX_STEPS}' in simple_pdu_js("a", "b", max_steps=10**9)
        assert '"max": 1' in simple_pdu_js("a", "b", max_steps=-5)
        assert f'"cap": {MAX_HOPS}' in simple_pdu_js("a", "b")


def _js(tmp_path, js: str, fake: str) -> dict:
    reports = run_pt_js(js, fake, tmp_path)
    assert len(reports) == 1
    return json.loads(reports[0])


@requires_node
class TestGuiJs:
    def test_warm_up_sends_in_realtime(self, tmp_path):
        data = _js(tmp_path, warm_up_js("PC1", "Remote-Server"),
                   _sim_fake(_ROUND_TRIP, start_sim=True, playing=True))
        assert data["ok"] is True and data["was_simulation"] is True
        fake = data["__fake"]
        assert fake["sim"] is False and fake["playing"] is False
        assert fake["added"] == [["PC1", "Remote-Server", False]]

    def test_warm_up_refusal_is_reported(self, tmp_path):
        data = _js(tmp_path, warm_up_js("NOPE", "X"), _sim_fake(_ROUND_TRIP, add_error=20))
        assert data["ok"] is False and data["add_error"] == 20

    def test_prepare_empties_the_list_and_shows_only_icmp(self, tmp_path):
        fake = _sim_fake(_ROUND_TRIP, start_sim=False, pdu_rows=("a", "b", "c"), playing=True)
        data = _js(tmp_path, prepare_js(), fake)
        assert data["entered_simulation"] is True and data["deleted"] == 3
        f = data["__fake"]
        assert f["pdus"] == [] and f["sim"] is True and f["playing"] is False
        assert f["filters"]["ICMP"] is True
        assert f["filters"]["STP"] is False and f["filters"]["ARP"] is False
        assert set(f["filters"]) == set(EVENT_FILTERS)

    def test_prepare_can_keep_the_list_and_the_filters(self, tmp_path):
        data = _js(tmp_path, prepare_js(clear_list=False, only_icmp=False),
                   _sim_fake(_ROUND_TRIP, pdu_rows=("a",)))
        assert data["deleted"] == 0
        assert data["__fake"]["pdus"] == ["a"] and data["__fake"]["filters"] == {}

    def test_start_play_presses_play_once(self, tmp_path):
        data = _js(tmp_path, start_play_js("PC1", "Remote-Server"), _sim_fake(_ROUND_TRIP))
        assert data["ok"] is True and data["frames_before"] == 0
        assert data["__fake"]["playing"] is True and data["__fake"]["forwards"] == 0

    def test_start_play_does_not_toggle_a_running_playback_off(self, tmp_path):
        data = _js(tmp_path, start_play_js("PC1", "Remote-Server"),
                   _sim_fake(_ROUND_TRIP, playing=True))
        assert data["__fake"]["playing"] is True

    def _played(self, steps: int, **kw) -> str:
        # The state a few Play ticks later: the PDU was added, the engine moved.
        return (_sim_fake(_ROUND_TRIP, playing=True, **kw)
                + "ipc.appWindow().getUserCreatedPDU().addSimplePdu('PC1','Remote-Server');"
                + f"for(var __k=0;__k<{steps};__k++){{sim.forward();}}")

    def test_poll_while_running_keeps_playing_and_sends_no_hops(self, tmp_path):
        data = _js(tmp_path, poll_play_js("PC1", "Remote-Server", 0), self._played(3))
        assert data["status"] == 1 and data["playing"] is True and "hops" not in data

    def test_poll_after_the_end_pauses_and_returns_the_hops(self, tmp_path):
        data = _js(tmp_path, poll_play_js("PC1", "Remote-Server", 0),
                   self._played(len(_ROUND_TRIP)))
        assert data["status"] == 3 and data["playing"] is False
        assert [h["device"] for h in data["hops"]] == _ROUND_TRIP
        assert data["__fake"]["refreshed"] == 1

    def test_poll_with_finish_pauses_an_unfinished_pdu(self, tmp_path):
        data = _js(tmp_path, poll_play_js("PC1", "Remote-Server", 0, finish=True),
                   self._played(2))
        assert data["status"] == 1 and data["playing"] is False and data["hops"]


class _Script:
    """A fake `send`: answers each JS by what kind of call it is."""

    def __init__(self, *, refuse: int = 0, polls_before_end: int = 2, end_status: int = 3):
        self.calls: list[str] = []
        self.refuse = refuse
        self.polls_left = polls_before_end
        self.end_status = end_status

    def __call__(self, js: str, timeout: float) -> str:
        if "getUserCreatedPDU().addSimplePdu" in js and "was_simulation" in js:
            self.calls.append("warm")
            return json.dumps({"ok": not self.refuse, "add_error": self.refuse,
                               "was_simulation": False})
        if "c.filters" in js:
            self.calls.append("prepare")
            return json.dumps({"ok": True, "entered_simulation": True, "deleted": 4})
        if "while(steps<c.max" in js:
            self.calls.append("headless")
            return json.dumps({"ok": True, "status": 3, "steps": 10, "hops": []})
        if "frames_before:n0,entered_simulation" in js:
            self.calls.append("play")
            return json.dumps({"ok": True, "frames_before": 7, "entered_simulation": False})
        self.calls.append("poll")
        finish = '"finish": true' in js
        if self.polls_left > 0 and not finish:
            self.polls_left -= 1
            return json.dumps({"ok": True, "status": 1, "playing": True})
        return json.dumps({"ok": True, "status": 1 if finish else self.end_status,
                           "playing": False, "hops": []})


class TestRunSimulatedPdu:
    def _run(self, script, **kw):
        t = [0.0]
        return run_simulated_pdu(script, "PC1", "Remote-Server", sleep=lambda s: None,
                                 clock=lambda: t[0], **kw)

    def test_headless_order(self):
        s = _Script()
        data = self._run(s)
        assert s.calls == ["warm"] * WARM_UP_ROUNDS + ["prepare", "headless"]
        assert data["warm_up_rounds"] == WARM_UP_ROUNDS and data["cleared_pdus"] == 4
        assert data["animated"] is False

    def test_animated_polls_until_the_end(self):
        s = _Script(polls_before_end=2)
        data = self._run(s, animate=True, warm_up=False)
        assert s.calls == ["prepare", "play", "poll", "poll", "poll"]
        assert data["status"] == 3 and data["timed_out"] is False and data["animated"] is True
        assert data["entered_simulation"] is True

    def test_animated_timeout_finishes_and_pauses(self):
        s = _Script(polls_before_end=10**6)
        t = [0.0]

        def sleep(sec):
            t[0] += sec

        data = run_simulated_pdu(s, "PC1", "Remote-Server", animate=True, warm_up=False,
                                 timeout_s=3, sleep=sleep, clock=lambda: t[0])
        assert data["timed_out"] is True and data["status"] == 1
        assert s.calls.count("poll") == 3

    def test_refused_warm_up_stops_before_touching_simulation(self):
        s = _Script(refuse=20)
        data = self._run(s)
        assert s.calls == ["warm"] and data["add_error"] == 20

    def test_no_answer_raises(self):
        with pytest.raises(PduRunError, match="timeout"):
            run_simulated_pdu(lambda js, t: None, "PC1", "X", warm_up=False)

    def test_pt_error_is_raised_with_its_text(self):
        with pytest.raises(PduRunError, match="PT_ERROR: boom"):
            run_simulated_pdu(lambda js, t: "PT_ERROR: boom", "PC1", "X", warm_up=False)


def _hop(device, **flags):
    base = {"index": 0, "device": device, "traffic_type_raw": 0, "decisions": []}
    base.update(flags)
    return base


class TestSummarizePduRun:
    def test_successful(self):
        hops = [_hop(d, sent=True) for d in _ROUND_TRIP[:-1]] + [_hop("PC1", accepted=True)]
        out = summarize_pdu_run({"ok": True, "status": 3, "steps": 10, "hops": hops},
                                "PC1", "Remote-Server")
        assert out["result"] == "successful"
        assert out["path"] == _ROUND_TRIP and out["reached_destination"] is True
        assert out["summary"].startswith("Successful")
        assert out["hops"][0]["traffic_type"] == "ICMP"
        assert "decisions" not in out["hops"][0]

    def test_failed_names_the_device_and_the_cause(self):
        hops = [_hop(d, sent=True) for d in _ROUND_TRIP[:7]]
        hops.append(_hop("FW1", dropped=True, decisions=[{"layer": 2, "description": _ARP_DROP}]))
        out = summarize_pdu_run({"ok": True, "status": 2, "steps": 7, "hops": hops},
                                "PC1", "Remote-Server")
        assert out["result"] == "failed" and out["failed_at"] == "FW1"
        assert out["reason"] == _ARP_DROP
        assert "Failed at FW1" in out["summary"] and _ARP_DROP in out["summary"]
        assert out["hops"][-1]["status"] == "dropped"

    def test_unfinished_says_how_to_go_on(self):
        out = summarize_pdu_run({"ok": True, "status": 1, "steps": 3,
                                 "hops": [_hop("PC1", sent=True)]}, "PC1", "Remote-Server")
        assert out["result"] == "in_progress" and out["reached_destination"] is False
        assert "max_steps" in out["summary"]

    @pytest.mark.parametrize("code", sorted(ADD_PDU_ERRORS))
    def test_refusals_are_explained(self, code):
        out = summarize_pdu_run({"ok": False, "add_error": code}, "A", "B")
        assert out["result"] == "not_added"
        assert ADD_PDU_ERRORS[code] in out["summary"]

    def test_unknown_refusal_code_is_passed_through(self):
        out = summarize_pdu_run({"ok": False, "add_error": 99}, "A", "B")
        assert "ADD_PDU_ERROR 99" in out["summary"]

    def test_repeated_device_in_a_row_is_one_path_step(self):
        hops = [_hop("PC1", buffered=True), _hop("PC1", sent=True), _hop("SW1", sent=True)]
        out = summarize_pdu_run({"ok": True, "status": 1, "hops": hops}, "PC1", "X")
        assert out["path"] == ["PC1", "SW1"]


def test_measured_enum_values():
    # Decoded from PT 9.0.1's pt-cep-java-framework jar; 3, 20, 30 and 11 seen live.
    assert TRAFFIC_STATUS == {0: "not_sent", 1: "in_progress", 2: "failed", 3: "successful"}
    assert set(ADD_PDU_ERRORS) == {10, 20, 21, 25, 30, 31}
    assert TRAFFIC_TYPES[11] == "STP"
