"""The hub -> HOTARU act path: what the lamp does for each decision, with a virtual lamp."""

import asyncio

from hub.act import VirtualLamp, plan, send
from hub.agent import LAMP, Decision, Event

ROOMS = {"bathroom": {"pan": 7}, "bedroom": {"pan": -47}}


def dec(sev, say="", family=""):
    return Decision(sev, "why [E1]", say, family, LAMP[sev], "rules", ["E1"])


def ops(steps):
    return [s["op"] for s in steps]


def test_plans():
    e = Event("long_stay", "bathroom", "check_in", {})
    assert plan(dec("watch"), e, ROOMS) == [{"op": "eye", "mode": "path", "bright": 120, "fade_ms": 4000},
                                            {"op": "look", "pan": 7.0}]
    ci = plan(dec("check_in", "Are you okay?"), e, ROOMS)
    assert ops(ci) == ["eye", "look", "ask"] and ci[0]["mode"] == "amber" and ci[2]["text"] == "Are you okay?"
    al = plan(dec("alert", "I'm calling Priya now.", "Dad fell"), e, ROOMS)
    assert ops(al) == ["eye", "action", "look", "say", "call"] and al[-1]["message"] == "Dad fell"
    assert ops(plan(dec("none", "Okay."), Event("answered", "bathroom", "none", {}), ROOMS)) == ["eye", "action", "say"]
    assert plan(dec("none"), Event("x", "kitchen", "none", {}), ROOMS) == []


def test_plans_never_hand_out_the_shared_templates():
    steps = plan(dec("watch"), Event("got_up", "bedroom", "watch", {}), ROOMS)
    steps[0]["mode"] = "broken"
    assert LAMP["watch"][0]["mode"] == "path"


def test_virtual_lamp_state_and_silence():
    async def go():
        lamp = VirtualLamp(speed=0.01)
        for s in plan(dec("check_in"), Event("too_still", "bedroom", "check_in", {}), ROOMS)[:2]:
            await send(lamp, s)
        ans = await lamp.ask("Are you okay?", listen_ms=2000)
        return lamp, ans
    lamp, ans = asyncio.run(go())
    assert lamp.state.eye == "amber" and lamp.state.pan == -47.0 and lamp.state.said == "Are you okay?"
    assert ans == {"answered": False, "how": "silence", "text": ""}


def test_virtual_lamp_tap_answers_a_check_in():
    async def go():
        lamp = VirtualLamp(speed=0.05)

        async def tap_soon():
            while not lamp.state.listening:
                await asyncio.sleep(0.01)
            lamp.tap()
        asyncio.create_task(tap_soon())
        return await lamp.ask("Are you okay?", listen_ms=4000)
    assert asyncio.run(go()) == {"answered": True, "how": "button", "text": ""}


def test_virtual_lamp_voice_answer():
    r = asyncio.run(VirtualLamp(reply="I'm fine, just slow", speed=0.01).ask("Are you okay?", 2000))
    assert r == {"answered": True, "how": "voice", "text": "I'm fine, just slow"}
