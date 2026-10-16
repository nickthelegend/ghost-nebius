"""The guardian's rules, the model's floor, and a whole night scenario against the fake lamp."""

import asyncio
import time

import pytest

from hub.agent import Config, Event, Reasoner, Rules
from hub.fake_lamp import FakeLamp
from hub.lamp import LampHub
from hub.run import Guardian
from hub.sense import Reading

CFG = Config(night=(0, 24), still_before_up_s=20, too_still_s=25, breath_lost_s=20)


def rd(motion=1.0, bpm=None):
    return Reading(bpm, 0.6 if bpm else 0.1, motion, 0.5, 1000, 100)


def feed(rules, room, seq, t0=1000.0):
    """seq: list of (seconds, Reading); one reading per second."""
    events, t = [], t0
    for secs, r in seq:
        for _ in range(secs):
            events += rules.update(room, r, now=t)
            t += 1
    return events


def test_got_up_then_too_still():
    ev = feed(Rules(CFG), "bedroom", [(30, rd(bpm=14)), (5, rd(motion=6)), (30, rd())])
    assert [e.kind for e in ev] == ["got_up", "too_still"]
    assert ev[1].floor == "check_in" and ev[1].facts["breathing_now"] is False


def test_fallen_but_breathing_outside_the_bedroom_still_checks_in():
    ev = feed(Rules(CFG), "bathroom", [(30, rd()), (5, rd(motion=6)), (30, rd(bpm=16))])
    assert [e.kind for e in ev] == ["got_up", "too_still"]
    assert ev[1].facts["breathing_now"] is True and ev[1].facts["sleep_room"] is False


def test_got_up_then_settles_back_to_sleep():
    ev = feed(Rules(CFG), "bedroom", [(30, rd(bpm=14)), (5, rd(motion=6)), (40, rd(bpm=13))])
    assert [e.kind for e in ev] == ["got_up"]


def test_daytime_motion_is_not_getting_up():
    cfg = Config(night=(22, 6), still_before_up_s=20, too_still_s=25)
    r = Rules(cfg)
    noon = time.mktime(time.strptime("2026-10-17 12:00", "%Y-%m-%d %H:%M"))
    assert feed(r, "bedroom", [(30, rd(bpm=14)), (5, rd(motion=6)), (30, rd())], t0=noon) == []


def test_breath_lost_without_motion():
    ev = feed(Rules(CFG), "bedroom", [(15, rd(bpm=14)), (25, rd())])
    assert [e.kind for e in ev] == ["breath_lost"]
    assert ev[0].facts["last_bpm"] == 14


def test_breath_gone_after_walking_out_is_not_an_alarm():
    ev = feed(Rules(CFG), "bedroom", [(15, rd(bpm=14)), (3, rd(motion=6)), (25, rd())])
    assert "breath_lost" not in [e.kind for e in ev]


def test_model_cannot_go_below_the_floor(monkeypatch):
    r = Reasoner()
    r.key, r.model = "k", "nemotron-test"

    async def fake_chat(*a, **k):
        return '{"severity": "none", "explain": "probably fine", "say": "", "family": ""}'
    monkeypatch.setattr(r, "_chat", fake_chat)
    d = asyncio.run(r.decide(Event("too_still", "bedroom", "check_in", {"minutes_since_got_up": 1,
                                                                         "minutes_without_motion": 1})))
    assert d.severity == "check_in" and d.by == "nemotron-test"


def test_model_error_falls_back_to_rules(monkeypatch):
    r = Reasoner()
    r.key, r.model = "k", "nemotron-test"

    async def boom(*a, **k):
        raise RuntimeError("503")
    monkeypatch.setattr(r, "_chat", boom)
    d = asyncio.run(r.decide(Event("breath_lost", "bedroom", "check_in",
                                   {"seconds_without_breathing_signal": 60, "last_bpm": 14, "motion": 1})))
    assert d.severity == "check_in" and "rules" in d.by and "14" in d.explain


def test_whole_night_against_fake_lamp():
    """Asleep and breathing -> gets up (walking) -> stops moving, no breathing -> check-in -> silence -> alert."""
    async def go():
        hub = LampHub("127.0.0.1", 18930)
        await hub.start()
        fake = FakeLamp("127.0.0.1", 18930, bpm=14, reply="", quiet=True)
        task = asyncio.create_task(fake.run())
        await hub.wait_for_lamp(10)
        g = Guardian(hub, Config(night=(0, 24), still_before_up_s=6, too_still_s=8, breath_lost_s=30),
                     {"lamp": {"pan": -40}}, Reasoner(), follow_room="lamp")
        kinds = []
        try:
            t0 = time.time()
            while time.time() - t0 < 75 and "no_answer" not in kinds:
                el = time.time() - t0
                fake.walking = 20 <= el < 25
                fake.present = el < 25
                kinds += [e.kind for e in await g.tick()]
                kinds = [d["event"] for d in g.decisions]
                await asyncio.sleep(0.5)
        finally:
            task.cancel()
            await hub.close()
        return kinds, fake.ops, g.decisions

    kinds, ops, decisions = asyncio.run(go())
    assert kinds[:3] == ["got_up", "too_still", "no_answer"], kinds
    names = [o["op"] for o in ops]
    assert {"op": "eye", "mode": "path", "bright": 120, "fade_ms": 4000} in ops  # path light on getting up
    assert {"op": "eye", "mode": "amber"} in ops and {"op": "eye", "mode": "red"} in ops
    assert "listen" in names and {"op": "look", "pan": -40.0} in ops
    assert decisions[-1]["severity"] == "alert"
