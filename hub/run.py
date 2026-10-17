"""GHOST, live: sense every room, decide, act through HOTARU.

    python -m hub.run                 # real timings (night hours, 20-minute rules)
    python -m hub.run --demo          # compressed timings for a live demo
    python -m hub.server              # the dashboard, with the recorded 3 am night (no hardware)

Rooms are the sensing nodes' names (and "lamp" for HOTARU's own link).
rooms.json says which way HOTARU turns to face each one:
    {"bedroom": {"pan": -40}, "bathroom": {"pan": 35}, "lamp": {"pan": 0}}

The routine (routine.py) is learned from the presence the rooms report, saved to
data/live/routine.json, and refit once a day.
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
from .act import plan, send
from .agent import Config, Event, Reasoner, Rules
from .evidence import Witness
from .lamp import CsiFrame, LampHub
from .routine import Routine
from .sense import BreathSensor, Reading

log = logging.getLogger("ghost")
ROOT = Path(__file__).resolve().parents[1]


class Guardian:
    def __init__(self, hub, cfg: Config, rooms: dict, reasoner: Reasoner, follow_room: str | None,
                 routine: Routine | None = None, clock=time.time, live_csi: bool = True, real_alerts: bool = True):
        self.hub, self.cfg, self.rooms = hub, cfg, rooms
        cfg.sleep_rooms = set(cfg.sleep_rooms) | {name for name, v in rooms.items() if v.get("sleep")}
        self.routine = routine
        self.rules = Rules(cfg, routine)
        self.reasoner = reasoner
        self.witness = Witness()
        self.sensors: dict[str, BreathSensor] = {}
        self.readings: dict[str, Reading | None] = {}
        self.follow_room = follow_room  # a room name, "auto" (wherever the person is), or None
        self.clock = clock  # scene time: time.time live, the recording's clock in a replay
        self.real_alerts = real_alerts  # False: print the call/text instead of placing it
        self.busy = False  # a check-in is in progress
        self.decisions: list[dict] = []  # the alert timeline, newest last
        self.log_lines: list[tuple[float, str]] = []
        self._queue: asyncio.Queue[Event] | None = None
        self._worker: asyncio.Task | None = None
        if live_csi:
            hub.csi_listeners.append(self.feed)

    def feed(self, f: CsiFrame) -> None:
        self.sensors.setdefault(f.source or "lamp", BreathSensor()).add(f)

    # ------------------------------------------------------------------ sensing ----
    async def tick(self, now: float | None = None) -> list[Event]:
        now = now if now is not None else self.clock()
        self.readings = {room: s.read() for room, s in self.sensors.items()}
        events: list[Event] = []
        for room, r in self.readings.items():
            if r is not None:
                events += self.rules.update(room, r, now)
                self.witness.record(room, now, r, self.rules.rooms[room].present)
        lamp = self.hub.lamp
        if lamp:
            lamp.clock = self.clock
        follow = self.followed_room()
        fr = self.readings.get(follow) if follow else None
        if lamp and fr and not self.busy:
            await lamp.level(fr.wave)
        if events:
            if self._worker is None or self._worker.done():
                self._queue = asyncio.Queue()
                self._worker = asyncio.create_task(self._work())
            for e in events:
                self._queue.put_nowait(e)
        return events

    def followed_room(self) -> str | None:
        """The room whose breathing HOTARU's ring follows."""
        if self.follow_room != "auto":
            return self.follow_room
        rs = self.rules.rooms
        up = next((n for n, s in rs.items() if s.up_at), None)
        if up:
            return up
        breathing = [n for n, r in self.readings.items() if r and r.bpm and rs.get(n) and rs[n].present]
        return next((n for n in breathing if n in self.cfg.sleep_rooms), breathing[0] if breathing else None)

    async def _work(self) -> None:
        """Decisions run one at a time, in order, without stalling the sensing."""
        assert self._queue
        while True:
            e = await self._queue.get()
            try:
                await self.handle(e)
            except Exception:  # noqa: BLE001 - one bad decision must not stop the guardian
                log.exception("handling %s failed", e.kind)
            finally:
                self._queue.task_done()

    async def idle(self) -> None:
        """Wait until every queued decision (and its check-in) is done."""
        if self._queue is not None and self._worker and not self._worker.done():
            await self._queue.join()

    # ------------------------------------------------------------------- acting ----
    def _came_from(self, e: Event) -> str | None:
        return e.facts.get("from")

    async def handle(self, e: Event) -> None:
        if not e.evidence:
            e.evidence = self.witness.for_event(e, self.routine, self._came_from(e), sorted(self.cfg.sleep_rooms))
        d = await self.reasoner.decide(e)
        self.reasoner.note(f"{e.kind} in {e.room}: {d.severity} - {d.explain}")
        self.witness.decided(e.t, e.kind, e.room, d.severity)
        entry = {"id": len(self.decisions) + 1, "t": e.t, "event": e.kind, "room": e.room, "facts": e.facts,
                 "floor": e.floor, "severity": d.severity, "explain": d.explain, "cites": d.cites,
                 "evidence": [x.as_dict() for x in e.evidence], "say": d.say, "family": d.family, "by": d.by,
                 "lamp": [], "outcome": ""}
        self.decisions.append(entry)
        log.info("[%s] %s in %s -> %s (%s): %s", d.by, e.kind, e.room, d.severity, e.floor, d.explain)
        lamp = self.hub.lamp
        for step in plan(d, e, self.rooms):
            if step["op"] == "call":
                entry["lamp"].append(step)
                msg = step["message"]
                if self.real_alerts:
                    entry["outcome"] = f"call: {await alerts.call(msg)}, text: {await alerts.text(msg)}"
                else:
                    entry["outcome"] = "family alerted (dry run: replay never places real calls)"
                log.info("calling family: %s", entry["outcome"])
                continue
            if not lamp:
                continue
            entry["lamp"].append(step)
            if step["op"] == "ask":
                if self.busy:
                    entry["outcome"] = "a check-in is already running"
                    continue
                await self._check_in(e, step, entry)
            else:
                await send(lamp, step)

    async def _check_in(self, e: Event, step: dict, entry: dict) -> None:
        lamp = self.hub.lamp
        self.busy = True
        try:
            asked_at = self.clock()
            t0 = time.time()
            ans = await lamp.ask(step["text"], listen_ms=step["listen_ms"])
            entry["outcome"] = f"answered by {ans['how']}" if ans["answered"] else "no answer"
            facts = {"asked": step["text"], "asked_at": asked_at, "how": ans["how"] if ans["answered"] else "",
                     "seconds": round(time.time() - t0), "text": ans["text"]}
            if ans["answered"]:
                await self.handle(Event("answered", e.room, "none", facts, self.clock()))
            else:
                situation = {"too_still": "got up in the night, then stopped moving",
                             "long_stay": f"has been in the {e.room} far longer than usual without moving",
                             "breath_lost": "stopped showing any breathing or movement"}.get(e.kind, e.kind)
                await self.handle(Event("no_answer", e.room, "alert", {**facts, "after": e.kind, "situation": situation},
                                        self.clock()))
        finally:
            self.busy = False

    # ---------------------------------------------------------------- reporting ----
    async def status_line(self) -> str:
        line = await self.reasoner.summarize(self.readings)
        self.reasoner.note(line)
        self.log_lines.append((self.clock(), line))
        del self.log_lines[:-30]
        return line

    def room_view(self, room: str, now: float) -> dict:
        r = self.readings.get(room)
        s = self.rules.rooms.get(room)
        sensor = self.sensors.get(room)
        present = bool(s and s.present)
        moving = bool(r and r.motion >= self.cfg.motion_on)
        state = "moving" if moving else ("breathing" if r and r.bpm else ("still" if present else "empty"))
        view = {"present": present, "state": state, "bpm": round(r.bpm, 1) if r and r.bpm else None,
                "confidence": round(r.confidence, 2) if r else None, "motion": round(r.motion, 1) if r else None,
                "jolt": round(r.jolt) if r else None, "trace": sensor.trace if sensor else [],
                "since_min": round((now - s.entered) / 60, 1) if s and s.entered else None,
                "watching": bool(s and s.up_at), "flags": sorted(s.flagged) if s else []}
        if self.routine is not None and self.routine.model:
            a = self.routine.anomaly(room, now, present)
            view["anomaly"] = round(a["score"], 3)
            view["routine_p"] = a["presence"]["p"]
        return view


def load_rooms(path: str | Path | None = None) -> dict:
    p = Path(path or os.getenv("GHOST_ROOMS", ROOT / "rooms.json"))
    if not p.exists():
        return {"lamp": {"pan": 0}}
    j = json.loads(p.read_text())
    return j.get("rooms", j)  # either {"rooms": {...}, "plan": ...} or the bare room map


async def main(demo: bool, port: int, follow: str | None) -> None:
    rooms = load_rooms()
    hub = LampHub(port=port)
    await hub.start()
    routine_path = ROOT / "data" / "live" / "routine.json"
    routine = Routine.load(routine_path) if routine_path.exists() else Routine()
    routine.fit()
    g = Guardian(hub, Config.demo() if demo else Config(), rooms,
                 Reasoner(os.getenv("GHOST_FAMILY_NAME", "your daughter"), os.getenv("GHOST_PERSON", "Dad")), follow,
                 routine=routine)
    mode = f"Nemotron ({g.reasoner.model})" if g.reasoner.online else "rules only (set NEBIUS_API_KEY + GHOST_REASON_MODEL)"
    log.info("GHOST running: %s, %s timings, rooms %s, routine from %d days", mode, "demo" if demo else "real",
             list(rooms), routine.nights)
    last_log = last_save = 0.0
    fitted_day = time.localtime().tm_yday
    while True:
        await asyncio.sleep(1)
        await g.tick()
        now = time.time()
        if now - last_log > (15 if demo else 60):
            last_log = now
            log.info("status: %s", await g.status_line())
        if now - last_save > 600:
            last_save = now
            routine.save(routine_path)
        if time.localtime().tm_yday != fitted_day and time.localtime().tm_hour >= 12:
            fitted_day = time.localtime().tm_yday  # the nightly refit (or run it as a Nebius Serverless Job)
            routine.fit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--follow", default="auto", help="room whose breathing HOTARU's ring follows ('auto', a name, or '' = off)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    asyncio.run(main(a.demo, a.port, a.follow or None))
