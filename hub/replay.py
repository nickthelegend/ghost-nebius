"""Recorded Wi-Fi CSI: record a real night from the boards, replay it with no hardware.

File format (.ghostcsi, gzip):
    line 1   b"GHOSTCSI1\\n"
    line 2   JSON header + "\\n": {"scene_start": epoch, "scale": 1, "markers": [{"t", "label"}], ...}
    records  u8 kind
               kind 1 (room):  u8 index | u8 len | name
               kind 0 (frame): f64 t (s since start) | u8 room index | u32 ms | i8 rssi | u8 n | n x u8 amplitude

`scale` maps recording seconds to scene seconds. A real recording has scale 1;
the bundled 3 am night is played at scene time x20, so twenty minutes of the
night pass in one minute while the breathing in the CSI stays real-time.

    python -m hub.replay record data/replay/my-night.ghostcsi   # capture what the boards send (Ctrl-C to stop)
    python -m hub.replay info data/replay/3am.ghostcsi
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

from .lamp import CsiFrame

MAGIC = b"GHOSTCSI1\n"


class Writer:
    def __init__(self, path: str | Path, header: dict):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.f = gzip.open(path, "wb", compresslevel=6)
        self.f.write(MAGIC + json.dumps(header).encode() + b"\n")
        self.rooms: dict[str, int] = {}
        self.count = 0

    def frame(self, t: float, room: str, ms: int, rssi: int, amp: bytes) -> None:
        i = self.rooms.get(room)
        if i is None:
            i = self.rooms[room] = len(self.rooms)
            name = room.encode()[:255]
            self.f.write(struct.pack("<BBB", 1, i, len(name)) + name)
        self.f.write(struct.pack("<BdBIbB", 0, t, i, ms & 0xFFFFFFFF, rssi, len(amp)) + amp)
        self.count += 1

    def close(self) -> None:
        self.f.close()


@dataclass
class Recording:
    header: dict
    rooms: list[str]
    frames: list[tuple[float, CsiFrame]] = field(default_factory=list)  # (t since start, frame), in time order

    @property
    def duration(self) -> float:
        return self.frames[-1][0] if self.frames else 0.0

    @property
    def scene_start(self) -> float:
        return float(self.header.get("scene_start", 0))

    @property
    def scale(self) -> float:
        return float(self.header.get("scale", 1))

    @classmethod
    def load(cls, path: str | Path) -> "Recording":
        data = gzip.open(path, "rb").read()
        if not data.startswith(MAGIC):
            raise ValueError(f"{path} is not a GHOST CSI recording")
        at = data.index(b"\n", len(MAGIC)) + 1
        header = json.loads(data[len(MAGIC):at])
        names: dict[int, str] = {}
        frames: list[tuple[float, CsiFrame]] = []
        rec = struct.Struct("<dBIbB")
        while at < len(data):
            kind = data[at]
            at += 1
            if kind == 1:
                i, n = data[at], data[at + 1]
                names[i] = data[at + 2:at + 2 + n].decode()
                at += 2 + n
            elif kind == 0:
                t, i, ms, rssi, n = rec.unpack_from(data, at)
                at += rec.size
                frames.append((t, CsiFrame(ms, rssi, data[at:at + n], source=names[i])))
                at += n
            else:
                raise ValueError(f"bad record kind {kind} at byte {at - 1}")
        return cls(header, [names[i] for i in sorted(names)], frames)


class Replay:
    """Feeds a recording into a Guardian and ticks it once per recorded second, in scene time."""

    def __init__(self, rec: Recording, guardian, speed: float = 1.0):
        self.rec, self.g, self.speed = rec, guardian, speed
        self.pos = 0.0  # seconds into the recording
        self._i = 0
        self._next_tick = 1.0
        self.done = False
        self.paused = False
        self.on_tick = None  # async callback after each tick

    def scene_now(self) -> float:
        return self.rec.scene_start + self.pos * self.rec.scale

    def _feed_until(self, pos: float) -> None:
        fr = self.rec.frames
        while self._i < len(fr) and fr[self._i][0] <= pos:
            self.g.feed(fr[self._i][1])
            self._i += 1

    async def _step_to(self, pos: float, settle: bool) -> None:
        while self._next_tick <= pos:
            self.pos = self._next_tick
            self._feed_until(self.pos)
            await self.g.tick(self.scene_now())
            if settle:
                await self.g.idle()
            if self.on_tick:
                await self.on_tick()
            self._next_tick += 1
        self.pos = pos
        self._feed_until(pos)

    async def fast(self, until: float | None = None) -> None:
        """As fast as the CPU allows, waiting for each decision (tests, pre-rolls)."""
        await self._step_to(min(until or self.rec.duration, self.rec.duration), settle=True)
        self.done = self.pos >= self.rec.duration

    async def run(self) -> None:
        """In real time (x speed): the dashboard demo."""
        loop = asyncio.get_running_loop()
        last = loop.time()
        while self.pos < self.rec.duration:
            await asyncio.sleep(0.05)
            now = loop.time()
            if not self.paused:
                await self._step_to(min(self.rec.duration, self.pos + (now - last) * self.speed), settle=False)
            last = now
        await self.g.idle()
        self.done = True


async def record(path: str, port: int, scale: float = 1.0) -> None:
    """Capture every frame the lamp and the nodes send, until Ctrl-C."""
    from .lamp import LampHub
    hub = LampHub(port=port)
    await hub.start()
    t0 = time.time()
    w = Writer(path, {"scene_start": t0, "scale": scale, "recorded": time.strftime("%Y-%m-%d %H:%M"), "markers": []})
    hub.csi_listeners.append(lambda f: w.frame(time.time() - t0, f.source or "lamp", f.lamp_ms, f.rssi, f.amp))
    print(f"recording CSI on udp {port + 1} to {path}; Ctrl-C to stop", flush=True)
    try:
        while True:
            await asyncio.sleep(5)
            print(f"  {w.count} frames, rooms {list(w.rooms)}", flush=True)
    finally:
        w.close()
        await hub.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("path")
    r.add_argument("--port", type=int, default=8770)
    i = sub.add_parser("info")
    i.add_argument("path")
    a = ap.parse_args()
    if a.cmd == "record":
        try:
            asyncio.run(record(a.path, a.port))
        except KeyboardInterrupt:
            pass
    else:
        rec = Recording.load(a.path)
        print(json.dumps(rec.header, indent=1))
        print(f"{len(rec.frames)} frames, {rec.duration:.1f} s, rooms {rec.rooms}")
