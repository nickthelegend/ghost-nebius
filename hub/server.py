"""The GHOST dashboard: floor plan, breathing per room, the learned routine, the alert timeline
with Nemotron's cited explanations, and what HOTARU did.

    python -m hub.server                       # the recorded 3 am night, virtual HOTARU, no hardware
    python -m hub.server --lamp                # same night, but the real HOTARU acts it out
    python -m hub.server --recording f.ghostcsi  # a night you recorded with `python -m hub.replay record`
    python -m hub.server --live                # the real boards, real time
    open http://127.0.0.1:8780

Only the standard library: one asyncio server for the page, a JSON snapshot and a
server-sent-events stream.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import mimetypes
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import scenario
from .act import VirtualHub, VirtualLamp
from .agent import Config, Reasoner
from .lamp import LampHub
from .replay import Recording, Replay
from .routine import Routine
from .run import ROOT, Guardian

log = logging.getLogger("ghost.server")
WEB = ROOT / "web"


def clock(t: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(t))


class Session:
    """One run of the guardian: a replayed recording, or the live boards."""

    def __init__(self, recording: Path | None, lamp_hub: LampHub | None = None, speed: float = 1.0,
                 home: dict | None = None, reply: str = ""):
        self.home = home or scenario.home()
        rooms = self.home["rooms"]
        reasoner = Reasoner(os.getenv("GHOST_FAMILY_NAME", self.home.get("family", "your daughter")),
                            os.getenv("GHOST_PERSON", self.home.get("person", "Dad")))
        self.recording = recording
        self.lamp_hub = lamp_hub
        self.task: asyncio.Task | None = None
        self._today_cache: tuple[int, dict] | None = None
        if recording is not None:
            self.rec = Recording.load(recording)
            live = ROOT / "data" / "live" / "routine.json"
            if self.rec.header.get("synthetic") or not live.exists():
                self.routine = scenario.build_routine(self.rec.scene_start)  # the demo's two weeks
            else:
                self.routine = Routine.load(live)
                self.routine.fit(before=self.rec.scene_start)
            self.hub = lamp_hub or VirtualHub(VirtualLamp(reply=reply))
            self.g = Guardian(self.hub, Config.replay() if self.rec.scale > 1 else Config(), rooms, reasoner, "auto",
                              routine=self.routine, live_csi=False, real_alerts=False)
            self.replay = Replay(self.rec, self.g, speed)
            self.g.clock = self.replay.scene_now
            self.replay.on_tick = self._on_tick
        else:
            self.rec, self.replay = None, None
            path = ROOT / "data" / "live" / "routine.json"
            self.routine = Routine.load(path) if path.exists() else Routine()
            self.routine.fit()
            self.hub = lamp_hub
            self.g = Guardian(lamp_hub, Config(), rooms, reasoner, "auto", routine=self.routine)
        self._ticks = 0

    async def _on_tick(self) -> None:
        self._ticks += 1
        if self._ticks % 10 == 0:  # the running log, in Nemotron Nano's words when configured
            await self.g.status_line()

    async def start(self) -> None:
        if self.replay:
            self.task = asyncio.create_task(self.replay.run())
        else:
            self.task = asyncio.create_task(self._live())

    async def _live(self) -> None:
        while True:
            await asyncio.sleep(1)
            await self.g.tick()
            await self._on_tick()

    def stop(self) -> None:
        if self.task:
            self.task.cancel()
        if self.g._worker:
            self.g._worker.cancel()

    # ------------------------------------------------------------------ the view ----
    def now(self) -> float:
        return self.g.clock()

    def routine_view(self, now: float) -> dict:
        r = self.routine
        minute = int(now // 60)
        if self._today_cache and self._today_cache[0] == minute:
            today = self._today_cache[1]
        else:
            today = {room: r.today(room, now) for room in r.model}
            self._today_cache = (minute, today)
        return {"bin_minutes": r.bin_minutes, "days": r.nights, "now_bin": r.bin_of(now),
                "rooms": {room: {"baseline": m.baseline, "occupied_days": m.occupied_days, "days": m.days,
                                 "today": today.get(room, [])}
                          for room, m in r.model.items()}}

    def snapshot(self) -> dict:
        now = self.now()
        g = self.g
        lamp = self.hub.lamp if self.hub else None
        rooms = {}
        for name, cfg in self.home["rooms"].items():
            v = g.room_view(name, now) if name in g.sensors else {"present": False, "state": "no sensor" if cfg.get("sensor") is False else "waiting"}
            rooms[name] = {"label": cfg.get("label", name), "pan": cfg.get("pan"), "sleep": bool(cfg.get("sleep")),
                           "sensor": cfg.get("sensor", True), **v}
        out = {
            "mode": "replay" if self.replay else "live",
            "now": now, "clock": clock(now),
            "home": {k: self.home.get(k) for k in ("name", "person", "family", "plan", "doors")}
                    | {"rooms": {n: {"label": c.get("label", n), "plan": c.get("plan"), "sensor": c.get("sensor", True)}
                                 for n, c in self.home["rooms"].items()}},
            "rooms": rooms,
            "followed": g.followed_room(),
            "routine": self.routine_view(now) if self.routine.model else None,
            "timeline": [{**d, "clock": clock(d["t"])} for d in g.decisions],
            "lamp": {"kind": getattr(lamp, "kind", None), "connected": lamp is not None, "busy": g.busy,
                     "state": lamp.state.as_dict() if lamp else None,
                     "recent": [{"clock": clock(t), **c} for t, c in (lamp.sent[-12:] if lamp else [])]},
            "model": {"online": g.reasoner.online, "reason": g.reasoner.model or None, "log": g.reasoner.log_model or None},
            "log": [{"clock": clock(t), "line": line} for t, line in g.log_lines[-12:]],
        }
        if self.replay:
            rp, rec = self.replay, self.rec
            out["replay"] = {"pos": round(rp.pos, 2), "duration": rec.duration, "scale": rec.scale, "speed": rp.speed,
                             "paused": rp.paused, "done": rp.done, "synthetic": bool(rec.header.get("synthetic")),
                             "start": rec.scene_start, "end": rec.scene_start + rec.duration * rec.scale,
                             "markers": [{**m, "clock": clock(rec.scene_start + m["t"] * rec.scale)}
                                         for m in rec.header.get("markers", [])]}
        return out


class Dashboard:
    def __init__(self, make_session):
        self.make_session = make_session
        self.session: Session | None = None

    async def restart(self) -> None:
        if self.session:
            self.session.stop()
        self.session = self.make_session()
        await self.session.start()

    # ---------------------------------------------------------------- http ----
    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
            writer.close()
            return
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, target, _ = lines[0].split(" ", 2)
        except ValueError:
            writer.close()
            return
        headers = {k.strip().lower(): v.strip() for k, v in (l.split(":", 1) for l in lines[1:] if ":" in l)}
        if int(headers.get("content-length", 0) or 0):
            await reader.readexactly(min(int(headers["content-length"]), 65536))
        url = urlsplit(target)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            if url.path == "/api/stream" and method == "GET":
                await self._stream(writer)
                return
            status, body, ctype = await self.route(method, url.path, q)
        except Exception as ex:  # noqa: BLE001
            log.exception("request failed")
            status, body, ctype = 500, json.dumps({"error": str(ex)}).encode(), "application/json"
        writer.write(f"HTTP/1.1 {status} {'OK' if status < 400 else 'Error'}\r\nContent-Type: {ctype}\r\n"
                     f"Content-Length: {len(body)}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n".encode() + body)
        try:
            await writer.drain()
        finally:
            writer.close()

    async def route(self, method: str, path: str, q: dict) -> tuple[int, bytes, str]:
        s = self.session
        js = "application/json"
        if path == "/api/state":
            return 200, json.dumps(s.snapshot()).encode(), js
        if method == "POST" and path.startswith("/api/"):
            act = path[5:]
            if act == "replay/restart":
                await self.restart()
            elif act == "replay/pause" and s.replay:
                s.replay.paused = True
            elif act == "replay/resume" and s.replay:
                s.replay.paused = False
            elif act == "replay/speed" and s.replay:
                s.replay.speed = max(0.25, min(4.0, float(q.get("x", 1))))
            elif act == "lamp/tap":
                lamp = s.hub.lamp if s.hub else None
                if not lamp or not hasattr(lamp, "tap"):
                    return 409, b'{"error": "no virtual HOTARU to tap"}', js
                lamp.tap()
            else:
                return 404, b'{"error": "unknown action"}', js
            return 200, b'{"ok": true}', js
        if method != "GET":
            return 405, b"", "text/plain"
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        f = (WEB / rel).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            return 404, b"not found", "text/plain"
        return 200, f.read_bytes(), (mimetypes.guess_type(f.name)[0] or "application/octet-stream")

    async def _stream(self, writer: asyncio.StreamWriter) -> None:
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-store\r\n"
                     b"Connection: keep-alive\r\n\r\n")
        try:
            while True:
                writer.write(b"data: " + json.dumps(self.session.snapshot()).encode() + b"\n\n")
                await writer.drain()
                await asyncio.sleep(0.5)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()


async def serve(host: str, port: int, make_session) -> tuple[asyncio.AbstractServer, Dashboard]:
    d = Dashboard(make_session)
    await d.restart()
    server = await asyncio.start_server(d.handle, host, port)
    return server, d


async def main(a) -> None:
    lamp_hub = None
    if a.lamp or a.live:
        lamp_hub = LampHub(port=a.lamp_port)
        await lamp_hub.start()
    recording = None if a.live else Path(a.recording) if a.recording else scenario.ensure_night()
    server, _ = await serve(a.host, a.port, lambda: Session(recording, lamp_hub, a.speed, reply=a.reply))
    log.info("GHOST dashboard on http://%s:%d  (%s)", a.host, a.port,
             "live boards" if a.live else f"replaying {recording.name}" + (" through HOTARU" if a.lamp else ", virtual HOTARU"))
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--recording", help="a .ghostcsi file (default: the bundled 3 am night)")
    ap.add_argument("--live", action="store_true", help="the real boards instead of a recording")
    ap.add_argument("--lamp", action="store_true", help="let the real HOTARU act out the replay")
    ap.add_argument("--lamp-port", type=int, default=8770)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--reply", default="", help="what the virtual person answers a check-in ('' = silence)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    asyncio.run(main(ap.parse_args()))
