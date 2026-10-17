"""Rules across rooms: following the person, a possible fall, and not alarming on rooms they left."""

from hub.agent import Config, Rules
from hub.sense import Reading

CFG = Config(night=(0, 24), still_before_up_s=20, too_still_s=25, breath_lost_s=20, presence_hold_s=5,
             fall_still_s=6, fall_jolt=600)


def rd(motion=1.0, bpm=None, jolt=0.0):
    return Reading(bpm, 0.6 if bpm else 0.1, motion, 0.5, 1000, 100, jolt)


def run(rules, script, t=1000.0):
    """script: list of (seconds, {room: Reading}); one update per room per second."""
    out = []
    for secs, rooms in script:
        for _ in range(secs):
            for room, r in rooms.items():
                out += rules.update(room, r, now=t)
            t += 1
    return out


def test_the_watch_follows_the_person_into_another_room():
    ev = run(Rules(CFG), [(30, {"bedroom": rd(bpm=13), "bathroom": rd()}),
                          (4, {"bedroom": rd(motion=8), "bathroom": rd()}),
                          (3, {"bedroom": rd(), "bathroom": rd()}),
                          (3, {"bedroom": rd(), "bathroom": rd(motion=8)}),
                          (30, {"bedroom": rd(), "bathroom": rd()})])
    kinds = [(e.kind, e.room) for e in ev]
    assert kinds[:2] == [("got_up", "bedroom"), ("moved", "bathroom")]
    assert ("too_still", "bathroom") in kinds
    assert not any(r == "bedroom" and k in ("too_still", "breath_lost") for k, r in kinds)  # they left it


def test_jolt_then_stillness_is_a_possible_fall():
    ev = run(Rules(CFG), [(10, {"bathroom": rd(motion=8, jolt=60)}), (1, {"bathroom": rd(motion=60, jolt=1100)}),
                          (10, {"bathroom": rd(bpm=19)})])
    falls = [e for e in ev if e.kind == "fall_suspected"]
    assert len(falls) == 1 and falls[0].facts["jolt"] == 1100 and falls[0].floor == "watch"


def test_walking_is_not_a_fall_and_sleep_rooms_are_exempt():
    assert not run(Rules(CFG), [(10, {"bathroom": rd(motion=8, jolt=150)}), (10, {"bathroom": rd()})])
    ev = run(Rules(CFG), [(1, {"bedroom": rd(motion=60, jolt=1100)}), (10, {"bedroom": rd(bpm=12)})])
    assert "fall_suspected" not in [e.kind for e in ev]  # flopping into bed


def test_a_still_person_stays_present_until_seen_elsewhere():
    r = Rules(CFG)
    run(r, [(3, {"bathroom": rd(motion=8)}), (60, {"bathroom": rd()})])
    assert r.rooms["bathroom"].present  # nobody saw them leave
    run(r, [(3, {"kitchen": rd(motion=8)}), (10, {"kitchen": rd(), "bathroom": rd()})], t=2000.0)
    assert not r.rooms["bathroom"].present and r.rooms["kitchen"].present


def test_a_flicker_of_breathing_in_an_empty_room_is_not_breath_lost():
    ev = run(Rules(CFG), [(2, {"kitchen": rd(bpm=6)}), (40, {"kitchen": rd()})])
    assert ev == []
