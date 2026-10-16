"""The 3 am demo, step by step, for filming.

Starts the hub, waits for HOTARU, keeps its ring breathing with the person
sensed over Wi-Fi, and plays the night scene one step per Enter (or on a
timer with --auto):

  1  follow   the ring pulses with the breathing behind the wall
  2  up       someone gets out of bed: the path light fades in
  3  still    no movement for too long: amber, turn to the room, "Are you okay?"
  4  answer?  a voice or a tap stands it down; silence -> red, call the family

    python -m hub.demo_3am            # Enter to advance
    python -m hub.demo_3am --auto     # timed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import alerts
from .lamp import LampHub
from .sense import BreathSensor

ROOM_PAN = -40.0  # where the bedroom is, from the lamp (deg); set for your room
FAMILY = "Priya"


async def follow_breathing(hub: LampHub, sensor: BreathSensor, state: dict) -> None:
    """Feed the ring the live breathing waveform at 10 Hz, print the rate every 2 s."""
    n = 0
    while True:
        await asyncio.sleep(0.1)
        r = sensor.read() if n % 2 == 0 else state.get("last")
        state["last"] = r
        if r and hub.lamp and state.get("follow"):
            await hub.lamp.level(r.wave)
        if r and n % 20 == 0:
            bpm = f"{r.bpm:4.1f} breaths/min" if r.bpm else "  -- breaths/min"
            print(f"  [sense] {bpm}  confidence {r.confidence:.2f}  motion {r.motion:5.1f}  csi {r.rate_hz:4.0f} Hz  frames {hub.csi_count}", flush=True)
        n += 1


async def step(auto: bool, seconds: float, label: str) -> None:
    print(f"\n== {label}", flush=True)
    if auto:
        await asyncio.sleep(seconds)
    else:
        await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)


async def main(auto: bool, port: int) -> None:
    hub = LampHub(port=port)
    sensor = BreathSensor()
    hub.csi_listeners.append(sensor.add)
    await hub.start()
    print(f"GHOST hub on :{port}. Waiting for HOTARU…", flush=True)
    lamp = await hub.wait_for_lamp()
    print(f"HOTARU connected: {lamp.hello}", flush=True)
    state = {"follow": False}
    asyncio.create_task(follow_breathing(hub, sensor, state))

    await step(auto, 2, "1  press Enter: the ring follows the breathing behind the wall")
    await lamp.action("stand", mood="calm")
    await lamp.eye("follow", bright=140)
    state["follow"] = True

    await step(auto, 20, "2  press Enter: someone gets out of bed -> path light")
    state["follow"] = False
    await lamp.look(ROOM_PAN)
    await lamp.eye("path", bright=120, fade_ms=4000)

    await step(auto, 10, "3  press Enter: no movement for too long -> check in")
    await lamp.eye("amber")
    await lamp.look(ROOM_PAN)
    ans = await lamp.ask("Are you okay? Say something, or tap my button.", listen_ms=5000)
    print(f"  answer: {ans}", flush=True)

    if ans["answered"]:
        await lamp.eye("path", bright=120, fade_ms=500)
        await lamp.action("nod", mood="happy")
        await lamp.say("Okay. I'll keep the light on for you.")
    else:
        await lamp.eye("red")
        await lamp.action("attention", mood="scared")
        await lamp.say(f"I'm calling {FAMILY} now.", wait=False)
        msg = "Hotaru here. Your dad hasn't moved for a while after getting up at night and didn't answer. Please check on him."
        print("  call:", await alerts.call(msg), " text:", await alerts.text(msg), flush=True)

    await step(auto, 5, "done: press Enter to quit")
    await hub.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--port", type=int, default=8770)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main(a.auto, a.port))
