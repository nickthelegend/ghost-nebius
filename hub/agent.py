"""The guardian: watches every room's Wi-Fi readings and decides what HOTARU does.

Two layers, on purpose:

1. Rules (deterministic, tested) turn readings into events and set a FLOOR
   on how serious each one is:
     got_up        motion after a long stillness, at night        -> path light
     too_still     got up, then no movement for too long            -> check in
                   (in a sleep room, calm breathing well after the last movement means
                   they went back to bed; anywhere else, breathing doesn't clear it:
                   someone who fell is still breathing)
     breath_lost   breathing was clear, then gone with no motion   -> check in
     no_answer     a check-in went unanswered                      -> alert family
2. Nemotron (on Nebius Token Factory) reads the event plus recent history
   and writes the explanation, the words HOTARU says, and the message to the
   family. It may raise the severity, never lower it below the rule's floor,
   and it never calls anyone by itself: a check-in always comes first.

    GHOST_LLM_BASE_URL   default https://api.tokenfactory.nebius.com/v1
    NEBIUS_API_KEY       Token Factory key
    GHOST_REASON_MODEL   the big Nemotron (reasoning about events)
    GHOST_LOG_MODEL      the small Nemotron (running log lines)
Without a key the agent still runs on the rules and plain-language templates.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

import httpx

from .sense import Reading

log = logging.getLogger("ghost.agent")

SEVERITY = ["none", "watch", "check_in", "alert"]


@dataclass
class Config:
    night: tuple[int, int] = (22, 6)  # hours: from 22:00 to 06:00
    still_before_up_s: float = 30 * 60  # stillness that makes motion count as "got up"
    too_still_s: float = 20 * 60  # after getting up, this long with no movement -> check in
    breath_lost_s: float = 60  # clear breathing, then nothing and no motion, this long -> check in
    motion_on: float = 3.0  # motion index meaning "someone is moving"
    settle_s: float = 10  # in a sleep room: breathing this long after the last movement = back in bed
    sleep_rooms: set = field(default_factory=lambda: {"bedroom"})

    @classmethod
    def demo(cls) -> "Config":
        """Timings compressed for a live demo."""
        return cls(night=(0, 24), still_before_up_s=20, too_still_s=25, breath_lost_s=20)


@dataclass
class Event:
    kind: str  # got_up | too_still | breath_lost | no_answer | answered
    room: str
    floor: str  # minimum severity
    facts: dict
    t: float = field(default_factory=time.time)


@dataclass
class Decision:
    severity: str
    explain: str  # why, citing the readings
    say: str  # what HOTARU says out loud ("" = nothing)
    family: str  # message for the family ("" = none)
    lamp: list[dict]  # lamp commands, e.g. {"op": "eye", "mode": "amber"}
    by: str  # model name or "rules"


@dataclass
class RoomState:
    last_motion: float | None = None
    still_since: float | None = None
    last_breath: float | None = None  # last time breathing was confidently seen
    bpm: float | None = None
    up_at: float | None = None  # when "got up" fired
    flagged: set = field(default_factory=set)


class Rules:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.rooms: dict[str, RoomState] = {}

    def _night(self, t: float) -> bool:
        a, b = self.cfg.night
        h = time.localtime(t).tm_hour
        return (a <= h < b) if a < b else (h >= a or h < b)

    def update(self, room: str, r: Reading, now: float | None = None) -> list[Event]:
        now = now or time.time()
        s = self.rooms.setdefault(room, RoomState())
        ev: list[Event] = []
        moving = r.motion >= self.cfg.motion_on
        if moving:
            still_for = now - s.still_since if s.still_since else 0
            if s.still_since and still_for >= self.cfg.still_before_up_s and self._night(now) and "got_up" not in s.flagged:
                s.up_at = now
                s.flagged = {"got_up"}
                ev.append(Event("got_up", room, "watch", {"still_minutes": round(still_for / 60, 1), "motion": round(r.motion, 1)}, now))
            s.last_motion = now
            s.still_since = None
        elif s.still_since is None:
            s.still_since = now
        sleep_room = room in self.cfg.sleep_rooms
        if r.bpm:
            s.last_breath, s.bpm = now, r.bpm
            s.flagged.discard("breath_lost")
            # Back in bed: calm breathing in a sleep room, well after the last movement (so the
            # breathing isn't just left over in the sensor's window from before they got up).
            if sleep_room and s.up_at and s.last_motion and now - s.last_motion >= self.cfg.settle_s:
                s.up_at = None
                s.flagged.discard("got_up")
                s.flagged.discard("too_still")

        if s.up_at and not moving and "too_still" not in s.flagged:
            quiet = now - (s.last_motion or s.up_at)
            if quiet >= self.cfg.too_still_s:
                s.flagged.add("too_still")
                ev.append(Event("too_still", room, "check_in",
                                {"minutes_since_got_up": round((now - s.up_at) / 60, 1),
                                 "minutes_without_motion": round(quiet / 60, 1), "breathing_now": bool(r.bpm),
                                 "sleep_room": sleep_room}, now))
        if s.last_breath and not r.bpm and not moving and "breath_lost" not in s.flagged:
            gone = now - s.last_breath
            if gone >= self.cfg.breath_lost_s and (s.last_motion or 0) < s.last_breath:
                s.flagged.add("breath_lost")
                ev.append(Event("breath_lost", room, "check_in",
                                {"seconds_without_breathing_signal": round(gone), "last_bpm": s.bpm,
                                 "motion": round(r.motion, 1)}, now))
        return ev


# ------------------------------------------------------------------ Nemotron ----
SYSTEM = """You are GHOST, a camera-less guardian for an older person living alone. You sense rooms
through Wi-Fi (breathing rate, motion), and you act through HOTARU, a small robot desk lamp that can
light a path, turn toward a room, change its ring colour, and speak.
You get one event, the rule-based minimum severity (the floor), and recent readings.
Decide how serious it is (you may raise it, never go below the floor), explain WHY in one or two
sentences that cite the numbers, write what HOTARU should say out loud (short, warm, calm; or ""),
and a message for the family (only if severity is "alert"; else "").
Never claim certainty you don't have: Wi-Fi sensing can miss someone who left the room.
Reply with JSON only: {"severity": "none|watch|check_in|alert", "explain": str, "say": str, "family": str}"""

TEMPLATES = {
    "got_up": ("Movement in the {room} after {still_minutes} minutes of stillness at night: probably getting up.",
               "", ""),
    "too_still": ("Got up {minutes_since_got_up} min ago in the {room}, then no movement for {minutes_without_motion} "
                  "min. Checking in.", "Are you okay? Say something, or tap my button.", ""),
    "breath_lost": ("Breathing was clear ({last_bpm} breaths/min), then no breathing signal for "
                    "{seconds_without_breathing_signal} s with no movement. Checking in.",
                    "Hey, just checking on you. Are you okay?", ""),
    "no_answer": ("No answer to the check-in after {seconds} s. Alerting the family.",
                  "I'm calling {family_name} now.",
                  "GHOST here: {person} {situation} and didn't answer a check-in. Please check on them."),
    "answered": ("They answered ({how}). Standing down.", "Okay. I'll keep the light on for you.", ""),
}

LAMP = {
    "none": [],
    "watch": [{"op": "eye", "mode": "path", "bright": 120, "fade_ms": 4000}],
    "check_in": [{"op": "eye", "mode": "amber"}],
    "alert": [{"op": "eye", "mode": "red"}, {"op": "action", "name": "attention", "mood": "scared"}],
}


class Reasoner:
    def __init__(self, family_name: str = "your daughter", person: str = "Dad"):
        self.base = os.getenv("GHOST_LLM_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
        self.key = os.getenv("NEBIUS_API_KEY", "")
        self.model = os.getenv("GHOST_REASON_MODEL", "")
        self.log_model = os.getenv("GHOST_LOG_MODEL", "")
        self.family_name, self.person = family_name, person
        self.history: list[str] = []  # recent log lines, newest last

    @property
    def online(self) -> bool:
        return bool(self.key and self.model)

    def note(self, line: str) -> None:
        self.history.append(time.strftime("%H:%M:%S ") + line)
        self.history = self.history[-40:]

    async def decide(self, e: Event) -> Decision:
        floor = e.floor
        tmpl = self._template(e)
        if not self.online:
            return Decision(floor, *tmpl, lamp=LAMP[floor], by="rules")
        try:
            user = json.dumps({"event": e.kind, "room": e.room, "floor": floor, "facts": e.facts,
                               "local_time": time.strftime("%H:%M", time.localtime(e.t)),
                               "recent": self.history[-12:]})
            out = await self._chat(self.model, SYSTEM, user, 500)
            j = json.loads(out[out.find("{"): out.rfind("}") + 1])
            sev = j.get("severity", floor)
            if sev not in SEVERITY or SEVERITY.index(sev) < SEVERITY.index(floor):
                sev = floor  # the rule's floor always holds
            fam = j.get("family", "") if sev == "alert" else ""
            return Decision(sev, j.get("explain") or tmpl[0], j.get("say", tmpl[1]), fam or (tmpl[2] if sev == "alert" else ""),
                            LAMP[sev], self.model)
        except Exception as ex:  # noqa: BLE001 - a model hiccup must not silence the guardian
            log.warning("reasoner fell back to rules: %s", ex)
            return Decision(floor, *tmpl, lamp=LAMP[floor], by="rules (model error)")

    async def summarize(self, readings: dict[str, Reading]) -> str:
        """One running-log line. The small Nemotron phrases it when configured."""
        parts = []
        for room, r in readings.items():
            if r is None:
                continue
            state = "moving" if r.motion >= 3 else (f"still, {r.bpm:.0f} breaths/min" if r.bpm else "still")
            parts.append(f"{room}: {state}")
        plain = "; ".join(parts) or "no readings"
        if not (self.key and self.log_model):
            return plain
        try:
            return (await self._chat(self.log_model, "Rewrite this home-sensing status as one short, calm log line. "
                                     "Keep every number. No preamble.", plain, 60)).strip() or plain
        except Exception:  # noqa: BLE001
            return plain

    def _template(self, e: Event) -> tuple[str, str, str]:
        f = {"room": e.room, "family_name": self.family_name, "person": self.person,
             "situation": e.facts.get("situation", "got up in the night, then stopped moving"), "seconds": "", "how": "",
             **e.facts}
        explain, say, fam = TEMPLATES.get(e.kind, ("{room}: " + e.kind, "", ""))
        return explain.format(**f), say.format(**f), fam.format(**f)

    async def _chat(self, model: str, system: str, user: str, max_tokens: int) -> str:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self.base}/chat/completions", headers={"Authorization": f"Bearer {self.key}"},
                             json={"model": model, "max_tokens": max_tokens, "temperature": 0.2,
                                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
