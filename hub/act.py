"""The hub -> HOTARU act path: from a decision to what the lamp physically does.

`plan()` is a pure function, so what HOTARU does for each kind of decision is
tested without hardware:

    watch     path light fades in, turn toward the room
    check_in  ring amber, turn toward the room, ask "Are you okay?" and listen
              (a voice or a tap on HOTARU's button stands it down)
    alert     ring red, the "attention" action, say who it's calling, call family
    answered  path light back, a nod, "I'll keep the light on for you"

Steps are lamp protocol commands (see hotaru/firmware/hotaru/ghost.h) plus two
hub-side steps: {"op": "ask"} (say + listen + wait for a tap) and {"op": "call"}.

`VirtualLamp` speaks the same API with no hardware: it keeps the lamp's state
for the dashboard, "speaks" for as long as the line would take, and listens
for a tap from the dashboard's "I'm OK" button. The replay demo uses it when no
HOTARU is connected.
"""

from __future__ import annotations

import asyncio
import time

from .agent import Decision, Event
from .lamp import Lamp

ASK = "Are you okay? Say something, or tap my button."


def plan(d: Decision, e: Event, rooms: dict) -> list[dict]:
    steps = [dict(c) for c in d.lamp]  # the templates are shared; never hand them out
    pan = rooms.get(e.room, {}).get("pan")
    if e.kind == "answered":
        return [{"op": "eye", "mode": "path", "bright": 120, "fade_ms": 500}, {"op": "action", "name": "nod", "mood": "happy"},
                *([{"op": "say", "text": d.say}] if d.say else [])]
    if pan is not None and d.severity != "none":
        steps.append({"op": "look", "pan": round(float(pan), 1)})
    if d.severity == "check_in":
        steps.append({"op": "ask", "text": d.say or ASK, "listen_ms": 6000})
    elif d.severity == "alert":
        if d.say:
            steps.append({"op": "say", "text": d.say})
        steps.append({"op": "call", "message": d.family or d.explain})
    elif d.say:
        steps.append({"op": "say", "text": d.say})
    return steps


async def send(lamp: Lamp, step: dict) -> None:
    """One protocol step (not ask/call) through the lamp's own vocabulary."""
    c = dict(step)
    op = c.pop("op")
    if op == "look":
        await lamp.look(c["pan"])
    elif op == "say":
        await lamp.say(c["text"], wait=False)
    else:
        await lamp.send(op, **c)


class VirtualLamp(Lamp):
    """A HOTARU that exists only in the hub: same API, no sockets."""

    kind = "virtual"

    def __init__(self, reply: str = "", speed: float = 1.0):
        super().__init__(None, None)
        self.reply = reply  # what the person answers when asked ("" = silence)
        self.speed = speed  # < 1 fast-forwards speech and listening (tests)
        self.hello = {"ev": "hello", "id": "virtual-hotaru", "fw": "virtual"}
        self.ops: list[dict] = []

    @property
    def peer(self) -> str:
        return "virtual"

    async def send(self, op: str, **kw) -> None:
        self._track(op, kw)
        self.ops.append({"op": op, **kw})
        loop = asyncio.get_running_loop()
        if op == "say":
            text = kw.get("text", "")
            loop.call_later(min(4.0, 0.3 + 0.055 * len(text)) * self.speed, self._dispatch, {"ev": "said", "text": text})
        elif op == "listen":
            ms = int(kw.get("ms", 5000))
            loop.call_later(ms / 1000 * self.speed, self._dispatch, {"ev": "heard", "text": self.reply, "ms": ms})
        elif op == "ping":
            self._dispatch({"ev": "pong"})

    def tap(self) -> bool:
        """Someone pressed HOTARU's button (the dashboard's "I'm OK")."""
        self._dispatch({"ev": "ok"} if self.state.checkin else {"ev": "key", "kind": "tap"})
        return True

    async def ask(self, text: str, listen_ms: int = 5000, grace_s: float = 6) -> dict:
        return await super().ask(text, listen_ms, grace_s * self.speed)


class VirtualHub:
    """Stands in for LampHub when there's no HOTARU: a virtual lamp, CSI fed by the replay."""

    def __init__(self, lamp: Lamp | None = None):
        self.lamp = lamp or VirtualLamp()
        self.csi_listeners: list = []
        self.csi_count = 0
        self.started = time.time()

    async def close(self) -> None:
        pass
