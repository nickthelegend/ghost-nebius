"""Hub side of the GHOST link to HOTARU.

The lamp connects to us over TCP and speaks newline-delimited JSON (see
hotaru/firmware/hotaru/ghost.h for the full protocol). It also streams Wi-Fi
CSI over UDP to port + 1. This module runs both servers and gives the rest of
the hub a small async API:

    hub = LampHub()
    await hub.start()
    lamp = await hub.wait_for_lamp()
    await lamp.eye("path", fade_ms=4000)
    reply = await lamp.ask("Are you okay?", listen_ms=5000)
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("ghost.lamp")

DEFAULT_PORT = 8770


@dataclass
class CsiFrame:
    lamp_ms: int  # lamp clock
    rssi: int
    amp: bytes  # one amplitude per subcarrier
    t: float = field(default_factory=time.time)  # hub clock on arrival
    source: str = ""  # which room: a node's name, or "lamp"


def parse_csi(datagram: bytes) -> list[CsiFrame]:
    """'GC1' | u8 count | count x { u32 ms | i8 rssi | u8 n | n x u8 }."""
    if len(datagram) < 4 or datagram[:3] != b"GC1":
        return []
    count, at, out = datagram[3], 4, []
    for _ in range(count):
        if at + 6 > len(datagram):
            break
        ms, rssi, n = struct.unpack_from("<Ibb", datagram, at)
        n &= 0xFF
        at += 6
        out.append(CsiFrame(ms, rssi, datagram[at:at + n]))
        at += n
    return out


class Lamp:
    """One connected HOTARU."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader, self.writer = reader, writer
        self.hello: dict = {}
        self.status: dict = {}
        self.events: asyncio.Queue[dict] = asyncio.Queue()
        self._waiters: list[tuple[Callable[[dict], bool], asyncio.Future]] = []
        self.closed = asyncio.Event()

    @property
    def peer(self) -> str:
        p = self.writer.get_extra_info("peername")
        return f"{p[0]}:{p[1]}" if p else "?"

    async def send(self, op: str, **kw) -> None:
        msg = json.dumps({"op": op, **kw}, separators=(",", ":")) + "\n"
        self.writer.write(msg.encode())
        await self.writer.drain()

    async def wait_event(self, pred: Callable[[dict], bool], timeout: float) -> dict | None:
        fut = asyncio.get_running_loop().create_future()
        self._waiters.append((pred, fut))
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self._waiters = [w for w in self._waiters if w[1] is not fut]

    def _dispatch(self, ev: dict) -> None:
        if ev.get("ev") == "hello":
            self.hello = ev
        elif ev.get("ev") == "status":
            self.status = ev
        for pred, fut in list(self._waiters):
            if not fut.done() and pred(ev):
                fut.set_result(ev)
        self.events.put_nowait(ev)

    async def _read_loop(self) -> None:
        try:
            while line := await self.reader.readline():
                line = line.strip()
                if not line:
                    continue
                try:
                    self._dispatch(json.loads(line))
                except json.JSONDecodeError:
                    log.warning("bad line from lamp: %r", line[:120])
        finally:
            self.closed.set()

    # ---- the vocabulary -------------------------------------------------
    async def action(self, name: str, mood: str | None = None):
        await self.send("action", name=name, **({"mood": mood} if mood else {}))

    async def look(self, pan_deg: float):
        await self.send("look", pan=round(pan_deg, 1))

    async def pose(self, pan: float, shoulder: float, elbow: float, head: float):
        await self.send("pose", a=[pan, shoulder, elbow, head])

    async def eye(self, mode: str, mood: str | None = None, bright: int | None = None, fade_ms: int | None = None):
        kw = {k: v for k, v in (("mood", mood), ("bright", bright), ("fade_ms", fade_ms)) if v is not None}
        await self.send("eye", mode=mode, **kw)

    async def level(self, v: float):
        await self.send("level", v=round(max(0.0, min(1.0, v)), 3))

    async def checkin(self, on: bool = True):
        await self.send("checkin", on=on)

    async def say(self, text: str, wait: bool = True, timeout: float = 30) -> bool:
        await self.send("say", text=text)
        if not wait:
            return True
        return await self.wait_event(lambda e: e.get("ev") == "said", timeout) is not None

    async def listen(self, ms: int = 5000) -> dict | None:
        await self.send("listen", ms=ms)
        return await self.wait_event(lambda e: e.get("ev") == "heard", ms / 1000 + 20)

    async def ask(self, text: str, listen_ms: int = 5000) -> dict:
        """Say something, then listen, while also accepting a tap ("I'm OK") as the answer."""
        await self.checkin(True)
        await self.say(text)
        await self.send("listen", ms=listen_ms)
        ev = await self.wait_event(lambda e: e.get("ev") in ("heard", "ok"), listen_ms / 1000 + 20)
        await self.checkin(False)
        if ev is None:
            return {"answered": False, "how": "timeout", "text": ""}
        if ev["ev"] == "ok":
            return {"answered": True, "how": "button", "text": ""}
        text = (ev.get("text") or "").strip()
        if not text:
            # Nothing said: a tap can still come in once the recording ends.
            await self.checkin(True)
            late = await self.wait_event(lambda e: e.get("ev") == "ok", 6)
            await self.checkin(False)
            if late:
                return {"answered": True, "how": "button", "text": ""}
        return {"answered": bool(text), "how": "voice" if text else "silence", "text": text}

    async def lamp(self, on: bool, bright: int | None = None):
        await self.send("lamp", on=on, **({"bright": bright} if bright is not None else {}))

    async def stop(self):
        await self.send("stop")


class LampHub:
    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT):
        self.host, self.port = host, port
        self.lamp: Lamp | None = None
        self._lamp_ready = asyncio.Event()
        self.csi_listeners: list[Callable[[CsiFrame], None]] = []
        self.csi_count = 0
        self.sources: dict[str, str] = {}  # sender IP -> room name (nodes announce themselves)
        self.lamp_room = "lamp"

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._on_lamp, self.host, self.port)
        loop = asyncio.get_running_loop()
        hub = self

        class _Csi(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                if data.startswith(b"GH1 "):  # a sensing node says which room it watches
                    name = data[4:68].decode(errors="replace").strip()
                    if hub.sources.get(addr[0]) != name:
                        log.info("sensing node %s is '%s'", addr[0], name)
                    hub.sources[addr[0]] = name
                    return
                lamp_ip = hub.lamp.peer.split(":")[0] if hub.lamp else None
                src = hub.sources.get(addr[0]) or (hub.lamp_room if addr[0] == lamp_ip else addr[0])
                for f in parse_csi(data):
                    f.source = src
                    hub.csi_count += 1
                    for cb in hub.csi_listeners:
                        cb(f)

        self._udp, _ = await loop.create_datagram_endpoint(_Csi, local_addr=(self.host, self.port + 1))
        log.info("GHOST hub listening on tcp %d, csi udp %d", self.port, self.port + 1)

    async def _on_lamp(self, reader, writer) -> None:
        lamp = Lamp(reader, writer)
        self.lamp = lamp
        log.info("lamp connected from %s", lamp.peer)
        reader_task = asyncio.create_task(lamp._read_loop())
        hello = await lamp.wait_event(lambda e: e.get("ev") == "hello", 5)
        if hello:
            log.info("lamp says hello: %s", hello)
        self._lamp_ready.set()
        await lamp.closed.wait()
        reader_task.cancel()
        log.info("lamp disconnected")
        if self.lamp is lamp:
            self.lamp = None
            self._lamp_ready.clear()

    async def wait_for_lamp(self, timeout: float | None = None) -> Lamp:
        await asyncio.wait_for(self._lamp_ready.wait(), timeout)
        assert self.lamp
        return self.lamp

    async def close(self) -> None:
        self._server.close()
        self._udp.close()
        if self.lamp:
            self.lamp.writer.close()
