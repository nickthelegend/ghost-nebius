"""A stand-in HOTARU that speaks the GHOST protocol, for testing the hub without hardware.

It connects to the hub, says hello, acts on commands (printing them), answers
"say" and "listen", and streams synthetic Wi-Fi CSI with a known breathing
rate to the hub's UDP port so the sensing pipeline has ground truth.

    python -m hub.fake_lamp --hub 127.0.0.1 --bpm 14 --reply ""
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import struct
import time


class FakeLamp:
    def __init__(self, host: str, port: int, bpm: float = 14.0, reply: str = "", csi_hz: int = 100,
                 present: bool = True, quiet: bool = False):
        self.host, self.port = host, port
        self.bpm, self.reply, self.csi_hz = bpm, reply, csi_hz
        self.present = present  # False = empty room: no breathing in the CSI
        self.walking = False  # True = someone walking about: large, fast CSI changes
        self.quiet = quiet
        self.ops: list[dict] = []
        self.checkin = False
        self._w: asyncio.StreamWriter | None = None

    def log(self, *a):
        if not self.quiet:
            print("[lamp]", *a, flush=True)

    async def send(self, ev: str, **kw):
        if self._w:
            self._w.write((json.dumps({"ev": ev, **kw}) + "\n").encode())
            await self._w.drain()

    async def tap(self):
        """Press the key briefly, as a person would."""
        if self.checkin:
            self.checkin = False
            await self.send("ok")
        else:
            await self.send("key", kind="tap")

    async def run(self):
        for attempt in range(30):  # like the real lamp: keep trying until the hub is up
            try:
                r, self._w = await asyncio.open_connection(self.host, self.port)
                break
            except OSError:
                await asyncio.sleep(1)
        else:
            raise ConnectionError(f"no hub at {self.host}:{self.port}")
        await self.send("hello", id="fake-hotaru", fw="hotaru3-ghost", ip="127.0.0.1", rssi=-50, actions=60, csi=True)
        csi = asyncio.create_task(self._csi())
        try:
            while line := await r.readline():
                cmd = json.loads(line)
                self.ops.append(cmd)
                await self._handle(cmd)
        finally:
            csi.cancel()

    async def _handle(self, c: dict):
        op = c.get("op")
        if op == "ping":
            await self.send("pong")
        elif op == "checkin":
            self.checkin = bool(c.get("on", True))
        elif op == "say":
            self.log("says:", c.get("text"))
            await asyncio.sleep(min(3.0, 0.04 * len(c.get("text", ""))))
            await self.send("said", text=c.get("text", ""))
        elif op == "listen":
            ms = int(c.get("ms", 5000))
            self.log(f"listening {ms} ms")
            await asyncio.sleep(min(ms / 1000, 1.0))  # fast-forward in tests
            await self.send("heard", text=self.reply, ms=ms)
        elif op == "level":
            pass
        else:
            self.log(op, {k: v for k, v in c.items() if k != "op"})

    async def _csi(self):
        """64 subcarriers. Chest motion modulates a subset of them at the breathing rate."""
        loop = asyncio.get_running_loop()
        tr, _ = await loop.create_datagram_endpoint(asyncio.DatagramProtocol, remote_addr=(self.host, self.port + 1))
        rng = random.Random(1)
        base = [40 + 30 * math.sin(k / 5) for k in range(64)]
        gain = [0.0 if k % 3 else 6.0 * math.cos(k / 7) for k in range(64)]
        t0 = time.time()
        period = 1 / self.csi_hz
        batch = []
        try:
            while True:
                t = time.time() - t0
                breath = math.sin(2 * math.pi * self.bpm / 60 * t) if self.present else 0.0
                walk = self.walking
                amp = bytes(max(0, min(255, int(base[k] + gain[k] * breath + (rng.gauss(0, 12) if walk else 0)
                                              + rng.gauss(0, 1.5)))) for k in range(64))
                batch.append(struct.pack("<Ibb", int(t * 1000), -50, 64) + amp)
                if len(batch) == 8:
                    tr.sendto(b"GC1" + bytes([len(batch)]) + b"".join(batch))
                    batch = []
                await asyncio.sleep(period)
        finally:
            tr.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--bpm", type=float, default=14.0)
    ap.add_argument("--reply", default="", help="what the person answers to a check-in; '' = silence")
    a = ap.parse_args()
    asyncio.run(FakeLamp(a.hub, a.port, a.bpm, a.reply).run())
