"""GHOST, live: sense every room, decide, act through HOTARU.

    python -m hub.run                 # real timings (night hours, 20-minute rules)
    python -m hub.run --demo          # compressed timings for a live demo

Rooms are the sensing nodes' names (and "lamp" for HOTARU's own link).
rooms.json says which way HOTARU turns to face each one:
    {"bedroom": {"pan": -40}, "bathroom": {"pan": 35}, "lamp": {"pan": 0}}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path

from . import alerts
from .agent import Config, Event, Reasoner, Rules
from .lamp import CsiFrame, LampHub
from .sense import BreathSensor

log = logging.getLogger("ghost")


class Guardian:
    def __init__(self, hub: LampHub, cfg: Config, rooms: dict, reasoner: Reasoner, follow_room: str | None):
        self.hub, self.cfg, self.rooms = hub, cfg, rooms
        cfg.sleep_rooms = set(cfg.sleep_rooms) | {name for name, v in rooms.items() if v.get("sleep")}
        self.rules = Rules(cfg)
        self.reasoner = reasoner
        self.sensors: dict[str, BreathSensor] = {}
        self.follow_room = follow_room
        self.busy = False  # a check-in is in progress
        self.decisions: list[dict] = []
        hub.csi_listeners.append(self._on_csi)

    def _on_csi(self, f: CsiFrame) -> None:
        self.sensors.setdefault(f.source or "lamp", BreathSensor()).add(f)

    async def tick(self) -> list[Event]:
        readings = {room: s.read() for room, s in self.sensors.items()}
        events: list[Event] = []
        for room, r in readings.items():
            if r is not None:
                events += self.rules.update(room, r)
        lamp = self.hub.lamp
        fr = readings.get(self.follow_room) if self.follow_room else None
        if lamp and fr and not self.busy and self.follow_room:
            await lamp.level(fr.wave)
        for e in events:
            await self.handle(e)
        return events

    async def handle(self, e: Event) -> None:
        d = await self.reasoner.decide(e)
        self.reasoner.note(f"{e.kind} in {e.room}: {d.severity} - {d.explain}")
        self.decisions.append({"t": e.t, "event": e.kind, "room": e.room, "facts": e.facts, "severity": d.severity,
                               "explain": d.explain, "by": d.by})
        log.info("[%s] %s in %s -> %s (%s): %s", d.by, e.kind, e.room, d.severity, e.floor, d.explain)
        lamp = self.hub.lamp
        if not lamp:
            return
        pan = self.rooms.get(e.room, {}).get("pan")
        for cmd in d.lamp:
            c = dict(cmd)  # the templates are shared; don't consume them
            await lamp.send(c.pop("op"), **c)
        if pan is not None and d.severity != "none":
            await lamp.look(pan)
        if d.severity == "check_in" and not self.busy:
            self.busy = True
            try:
                t0 = time.time()
                ans = await lamp.ask(d.say or "Are you okay? Say something, or tap my button.", listen_ms=6000)
                if ans["answered"]:
                    await self.handle(Event("answered", e.room, "none", {"how": ans["how"], "text": ans["text"]}))
                    await lamp.eye("path", bright=120, fade_ms=500)
                    await lamp.action("nod", mood="happy")
                else:
                    situation = {"too_still": "got up in the night, then stopped moving",
                                 "breath_lost": "stopped showing any breathing or movement"}.get(e.kind, e.kind)
                    await self.handle(Event("no_answer", e.room, "alert",
                                            {"seconds": round(time.time() - t0), "after": e.kind, "situation": situation}))
            finally:
                self.busy = False
        elif d.severity == "alert":
            if d.say:
                await lamp.say(d.say, wait=False)
            msg = d.family or d.explain
            log.info("calling family: %s / text: %s", await alerts.call(msg), await alerts.text(msg))
        elif d.say and d.severity == "none":
            await lamp.say(d.say, wait=False)


async def main(demo: bool, port: int, follow: str | None) -> None:
    rooms_path = Path(os.getenv("GHOST_ROOMS", Path(__file__).resolve().parents[1] / "rooms.json"))
    rooms = json.loads(rooms_path.read_text()) if rooms_path.exists() else {"lamp": {"pan": 0}}
    hub = LampHub(port=port)
    await hub.start()
    g = Guardian(hub, Config.demo() if demo else Config(), rooms,
                 Reasoner(os.getenv("GHOST_FAMILY_NAME", "your daughter"), os.getenv("GHOST_PERSON", "Dad")), follow)
    mode = f"Nemotron ({g.reasoner.model})" if g.reasoner.online else "rules only (set NEBIUS_API_KEY + GHOST_REASON_MODEL)"
    log.info("GHOST running: %s, %s timings, rooms %s", mode, "demo" if demo else "real", list(rooms))
    last_log = 0.0
    while True:
        await asyncio.sleep(1)
        await g.tick()
        if time.time() - last_log > (15 if demo else 60):
            last_log = time.time()
            readings = {room: s.read() for room, s in g.sensors.items()}
            line = await g.reasoner.summarize(readings)
            g.reasoner.note(line)
            log.info("status: %s", line)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--follow", default="lamp", help="room whose breathing HOTARU's ring follows ('' = off)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    asyncio.run(main(a.demo, a.port, a.follow or None))
