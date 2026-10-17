"""The routine is learned from presence alone, with no labels, and judged against past days only."""

import time

import pytest

from hub import scenario
from hub.agent import Config, Rules
from hub.routine import Routine
from hub.sense import Reading

NIGHT = scenario.scene_start()  # 02:50 on the demo night


@pytest.fixture(scope="module")
def routine():
    return scenario.build_routine(NIGHT)


def at(hh, mm, day_offset=0):
    lt = time.localtime(NIGHT)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + day_offset, hh, mm, 0, 0, 0, -1))


def test_learns_where_someone_usually_is(routine):
    b = routine.bin_of(at(3, 10))
    assert routine.model["bedroom"].baseline[b] > 0.85  # asleep at 3 am
    assert routine.model["bathroom"].baseline[b] < 0.25  # rarely in the bathroom then
    assert routine.model["kitchen"].baseline[routine.bin_of(at(7, 20))] > 0.6  # breakfast
    assert routine.nights == 14


def test_presence_surprise_in_both_directions(routine):
    assert routine.presence_score("bathroom", at(3, 10), True)["bits"] > 2
    assert routine.presence_score("bedroom", at(3, 10), False)["bits"] > 3
    assert routine.presence_score("bedroom", at(3, 10), True)["bits"] < 0.5


def test_night_visits_have_a_learned_length(routine):
    usual = routine.dwell_score("bathroom", at(3, 0), 4 * 60)
    long = routine.dwell_score("bathroom", at(3, 0), 12 * 60)
    assert not usual["anomalous"] and usual["n"] >= 5 and "within 2 h" in usual["scope"]
    assert long["anomalous"] and long["z"] >= 2.5 and long["times_typical"] >= 2


def test_tonight_does_not_change_the_model_until_the_next_fit(routine):
    r = Routine.from_json(routine.to_json())
    r.fit(before=NIGHT)
    before = list(r.model["bathroom"].baseline)
    for k in range(30):  # half an hour in the bathroom tonight
        r.observe(at(3, k), "bathroom", True)
    assert r.model["bathroom"].baseline == before
    assert r.today("bathroom", at(3, 40))[r.bin_of(at(3, 10))] == pytest.approx(1.0)
    r.fit(before=at(12, 0, day_offset=1))
    assert r.model["bathroom"].baseline[r.bin_of(at(3, 10))] > before[r.bin_of(at(3, 10))]


def test_save_and_load(tmp_path, routine):
    p = tmp_path / "routine.json"
    routine.save(p)
    r = Routine.load(p)
    r.fit(before=NIGHT)
    assert r.model["bedroom"].baseline == routine.model["bedroom"].baseline
    assert len(r.visits["bathroom"]) == len(routine.visits["bathroom"])


def rd(motion=1.0, bpm=None, jolt=0.0):
    return Reading(bpm, 0.6 if bpm else 0.1, motion, 0.5, 1000, 100, jolt)


def test_long_stay_uses_the_learned_routine(routine):
    """Still in the bathroom at 3 am: checked in once the stay is far past what visits there usually take."""
    rules = Rules(Config.replay(), Routine.from_json(routine.to_json()))
    rules.routine.fit(before=NIGHT)
    t, ev = at(3, 0), []
    for _ in range(3):
        ev += rules.update("bathroom", rd(motion=8), t)
        t += 20
    while t < at(3, 30) and not ev:
        ev += rules.update("bathroom", rd(bpm=18), t)
        t += 20
    assert [e.kind for e in ev] == ["long_stay"]
    f = ev[0].facts
    assert f["minutes_in_room"] >= 1.5 * f["p90_visit_min"] and f["typical_visit_min"] <= 6
    assert ev[0].floor == "check_in"


def test_without_a_routine_there_is_no_long_stay():
    rules = Rules(Config.replay())
    t, ev = at(3, 0), []
    for _ in range(3):
        ev += rules.update("bathroom", rd(motion=8), t)
        t += 20
    for _ in range(60):
        ev += rules.update("bathroom", rd(bpm=18), t)
        t += 20
    assert "long_stay" not in [e.kind for e in ev]
