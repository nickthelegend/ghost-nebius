"""Explanations cite numbered evidence; citations to evidence that doesn't exist are removed."""

import asyncio
import json

from hub.agent import Event, Evidence, Reasoner, cite
from hub.evidence import Witness
from hub.sense import Reading

EV = [Evidence("E1", "rule", "bathroom", "Rule long_stay: 12 min in this room."),
      Evidence("E2", "csi", "bathroom", "bathroom Wi-Fi: breathing 19.0 breaths/min."),
      Evidence("E3", "routine", "bathroom", "Learned visits: median 4.0 min.")]


def test_cite_strips_invented_ids_and_keeps_real_ones():
    text, used = cite("Still for 12 min [E1], far past the usual 4 [E3][E9].", EV)
    assert "[E9]" not in text and used == ["E1", "E3"]


def test_cite_adds_citations_when_the_model_gave_none():
    text, used = cite("Probably fine.", EV)
    assert used == ["E1", "E2", "E3"] and text.endswith("[E1][E2][E3]")


def test_cite_honours_the_cites_list():
    text, used = cite("Long stay.", EV, ["E3", "E7"])
    assert used == ["E3"] and "[E3]" in text


def long_stay():
    return Event("long_stay", "bathroom", "check_in",
                 {"minutes_in_room": 12, "minutes_without_motion": 8, "typical_visit_min": 4, "p90_visit_min": 5,
                  "longest_visit_min": 5, "visits_learned": 9, "times_typical": 3, "scope": "within 2 h of 03:00",
                  "breathing_now": True, "bpm": 19}, evidence=list(EV))


def test_nemotron_gets_the_evidence_and_its_reasoning_is_stripped(monkeypatch):
    r = Reasoner()
    r.key, r.model = "k", "nvidia/nemotron-test"
    seen = {}

    async def fake_chat(model, system, user, max_tokens):
        seen["user"] = json.loads(user)
        seen["system"] = system
        return ('<think>{"severity": "none"} is tempting but [E1] says 12 min</think>'
                '{"severity": "check_in", "explain": "12 min in the bathroom [E1], 3x the learned 4 min [E3] [E8].", '
                '"cites": ["E1", "E3"], "say": "Are you okay?", "family": ""}')
    monkeypatch.setattr(r, "_chat", fake_chat)
    d = asyncio.run(r.decide(long_stay()))
    assert [x["id"] for x in seen["user"]["evidence"]] == ["E1", "E2", "E3"]
    assert "cite" in seen["system"]
    assert d.severity == "check_in" and d.cites == ["E1", "E3"] and "[E8]" not in d.explain
    assert d.by == "nvidia/nemotron-test"


def test_rules_only_explanations_cite_too():
    d = asyncio.run(Reasoner().decide(long_stay()))
    assert d.by == "rules" and d.cites and all(f"[{c}]" in d.explain for c in d.cites)
    assert "usually last 4 min" in d.explain


def test_witness_writes_numbers_from_the_readings():
    w = Witness()
    for k in range(30):
        w.record("bathroom", 1000 + k, Reading(19.0 if k > 10 else None, 0.6, 8.0 if k < 5 else 1.0, 0.5, 900, 30,
                                              900 if k == 3 else 10), True)
    e = Event("fall_suspected", "bathroom", "watch", {"jolt": 900, "walking_jolt_limit": 600, "seconds_still_after": 25,
                                                      "breathing_now": True, "bpm": 19.0}, t=1029)
    ev = w.for_event(e)
    assert [x.source for x in ev] == ["rule", "csi"] and [x.id for x in ev] == ["E1", "E2"]
    assert "19.0 breaths/min" in ev[1].text and "jolt 900" in ev[1].text
