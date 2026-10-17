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
     moved         the person who got up shows up in another room  -> the lamp turns to follow
     fall_suspected a violent half-second jolt, then stillness     -> watch (not a sleep room)
     long_stay     still, in a visit far longer than the LEARNED routine says visits to this
                   room at this hour last (see routine.py)            -> check in
2. Nemotron (on Nebius Token Factory) reads the event plus recent history
   and writes the explanation, the words HOTARU says, and the message to the
   family. It may raise the severity, never lower it below the rule's floor,
   and it never calls anyone by itself: a check-in always comes first.
   Every event carries numbered evidence (E1, E2, ...) from the CSI, the
   learned routine and the lamp; the explanation must cite it, and citations
   to evidence that doesn't exist are removed.

    GHOST_LLM_BASE_URL   default https://api.tokenfactory.nebius.com/v1
    NEBIUS_API_KEY       Token Factory key
    GHOST_REASON_MODEL   the big Nemotron (reasoning about events)
    GHOST_LOG_MODEL      the small Nemotron (running log lines)
    GHOST_REASON_SYSTEM_PREFIX  optional line put before the system prompt (some Nemotron
                         releases switch reasoning on with e.g. "detailed thinking on")
Without a key the agent still runs on the rules and plain-language templates.
"""

from __future__ import annotations

import json
import logging
import os
import re
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
    presence_hold_s: float = 90  # a room someone walked out of stays "occupied" this long after the last sign
    unseen_s: float = 30 * 60  # ...and one nobody was seen leaving, this long (a still person is still there)
    fall_jolt: float = 600  # a half-second motion burst this strong (walking is ~50-200; calibrate per home)
    fall_still_s: float = 30  # ...followed by this much stillness = possible fall
    long_stay_still_s: float = 5 * 60  # learned-routine check runs once the room has been still this long

    @classmethod
    def demo(cls) -> "Config":
        """Timings compressed for a live demo."""
        return cls(night=(0, 24), still_before_up_s=20, too_still_s=25, breath_lost_s=20, presence_hold_s=10,
                   unseen_s=120, fall_still_s=6, long_stay_still_s=8)

    @classmethod
    def replay(cls) -> "Config":
        """The recorded 3 am night: real-world timings in scene time (the replay runs scene time x20)."""
        return cls(night=(22, 6), still_before_up_s=10 * 60, too_still_s=20 * 60, breath_lost_s=6 * 60,
                   settle_s=3 * 60, presence_hold_s=3 * 60, fall_still_s=2 * 60, long_stay_still_s=3 * 60)


@dataclass
class Evidence:
    id: str  # "E1", what explanations cite
    source: str  # csi | routine | rule | lamp
    room: str
    text: str  # one sentence with the numbers
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "source": self.source, "room": self.room, "text": self.text}


@dataclass
class Event:
    kind: str  # got_up | moved | fall_suspected | long_stay | too_still | breath_lost | no_answer | answered
    room: str
    floor: str  # minimum severity
    facts: dict
    t: float = field(default_factory=time.time)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Decision:
    severity: str
    explain: str  # why, citing the evidence as [E1]
    say: str  # what HOTARU says out loud ("" = nothing)
    family: str  # message for the family ("" = none)
    lamp: list[dict]  # lamp commands, e.g. {"op": "eye", "mode": "amber"}
    by: str  # model name or "rules"
    cites: list[str] = field(default_factory=list)


@dataclass
class RoomState:
    last_motion: float | None = None
    still_since: float | None = None
    last_breath: float | None = None  # last time breathing was confidently seen
    bpm: float | None = None
    up_at: float | None = None  # when "got up" fired (follows the person from room to room)
    flagged: set = field(default_factory=set)
    present: bool = False
    entered: float | None = None  # start of the current stay
    last_seen: float | None = None  # last breath or movement
    vacated: bool = False  # the person walked out to another room
    jolt: float = 0.0  # strongest jolt in the current or last movement
    motion_peak: float = 0.0
    breath_streak: int = 0  # consecutive readings with confident breathing
    breath_clear: int = 0  # longest such streak since the last movement: breath_lost needs a clear signal first


class Rules:
    def __init__(self, cfg: Config | None = None, routine=None):
        self.cfg = cfg or Config()
        self.rooms: dict[str, RoomState] = {}
        self.routine = routine  # a routine.Routine: enables the learned long_stay check

    def _night(self, t: float) -> bool:
        a, b = self.cfg.night
        h = time.localtime(t).tm_hour
        return (a <= h < b) if a < b else (h >= a or h < b)

    def update(self, room: str, r: Reading, now: float | None = None) -> list[Event]:
        now = now or time.time()
        cfg = self.cfg
        s = self.rooms.setdefault(room, RoomState())
        ev: list[Event] = []
        moving = r.motion >= cfg.motion_on
        sleep_room = room in cfg.sleep_rooms

        # Presence: breathing or movement. Breathing comes and goes in the sensor, and someone lying
        # still may show neither, so a room only empties once they were seen somewhere else (one
        # person living alone), or after a long time with no sign at all.
        s.breath_streak = s.breath_streak + 1 if r.bpm else 0
        if moving or s.breath_streak >= 3:
            s.last_seen = now
            if not s.present:
                s.present, s.entered = True, now
        elif s.present:
            unseen = now - (s.last_seen or now)
            if (s.vacated and unseen > cfg.presence_hold_s) or unseen > cfg.unseen_s:
                s.present, s.entered = False, None
        if self.routine is not None:
            self.routine.observe(now, room, s.present)

        if moving:
            new_bout = s.last_motion is None or s.still_since is not None
            if new_bout:
                s.jolt, s.motion_peak = 0.0, 0.0
                s.flagged.discard("fall")
                for n, o in self.rooms.items():  # whoever was elsewhere has walked in here
                    if n != room and o.present and (o.last_motion or 0) < now - 1:
                        o.vacated = True
            s.jolt, s.motion_peak = max(s.jolt, r.jolt), max(s.motion_peak, r.motion)
            s.vacated = False
            src = next((n for n, o in self.rooms.items() if n != room and o.up_at), None) if not s.up_at else None
            if src:  # the person who got up has walked in here: the watch moves with them
                o = self.rooms[src]
                s.up_at, s.flagged = o.up_at, {"got_up"}
                o.up_at, o.vacated = None, True
                o.flagged -= {"got_up", "too_still", "long_stay"}
                ev.append(Event("moved", room, "watch", {"from": src, "minutes_since_got_up": round((now - s.up_at) / 60, 1),
                                                         "motion": round(r.motion, 1)}, now))
            else:
                still_for = now - s.still_since if s.still_since else 0
                if s.still_since and still_for >= cfg.still_before_up_s and self._night(now) and "got_up" not in s.flagged:
                    s.up_at = now
                    s.flagged = {"got_up"}
                    ev.append(Event("got_up", room, "watch", {"still_minutes": round(still_for / 60, 1), "motion": round(r.motion, 1)}, now))
            s.last_motion = now
            s.still_since = None
            s.breath_clear = 0
        elif s.still_since is None:
            s.still_since = now
        if r.bpm:
            s.breath_clear = max(s.breath_clear, s.breath_streak)
            s.last_breath, s.bpm = now, r.bpm
            s.flagged.discard("breath_lost")
            # Back in bed: calm breathing in a sleep room, well after the last movement (so the
            # breathing isn't just left over in the sensor's window from before they got up).
            if sleep_room and s.up_at and s.last_motion and now - s.last_motion >= cfg.settle_s:
                s.up_at = None
                s.flagged -= {"got_up", "too_still", "long_stay"}

        quiet = now - (s.last_motion or now)
        if not moving and not sleep_room and s.jolt >= cfg.fall_jolt and "fall" not in s.flagged and quiet >= cfg.fall_still_s:
            s.flagged.add("fall")
            ev.append(Event("fall_suspected", room, "watch",
                            {"jolt": round(s.jolt), "walking_jolt_limit": round(cfg.fall_jolt),
                             "seconds_still_after": round(quiet), "breathing_now": bool(r.bpm),
                             "bpm": round(r.bpm, 1) if r.bpm else None}, now))
        if (self.routine is not None and s.present and s.entered and not moving and not sleep_room
                and "long_stay" not in s.flagged and now - (s.last_motion or s.entered) >= cfg.long_stay_still_s):
            d = self.routine.dwell_score(room, s.entered, now - s.entered)
            if d["anomalous"]:
                s.flagged |= {"long_stay", "too_still"}  # one check-in per stay
                ev.append(Event("long_stay", room, "check_in",
                                {"minutes_in_room": d["minutes"], "minutes_without_motion": round(quiet / 60, 1),
                                 "typical_visit_min": d["median_min"], "p90_visit_min": d["p90_min"],
                                 "longest_visit_min": d["longest_min"], "visits_learned": d["n"],
                                 "times_typical": d["times_typical"], "scope": d["scope"],
                                 "breathing_now": bool(r.bpm), "bpm": round(r.bpm, 1) if r.bpm else None}, now))
        if s.up_at and not moving and "too_still" not in s.flagged:
            quiet = now - (s.last_motion or s.up_at)
            if quiet >= cfg.too_still_s:
                s.flagged |= {"too_still", "long_stay"}
                ev.append(Event("too_still", room, "check_in",
                                {"minutes_since_got_up": round((now - s.up_at) / 60, 1),
                                 "minutes_without_motion": round(quiet / 60, 1), "breathing_now": bool(r.bpm),
                                 "sleep_room": sleep_room}, now))
        if (s.last_breath and not r.bpm and not moving and not s.vacated and "breath_lost" not in s.flagged
                and s.breath_clear >= 10):
            gone = now - s.last_breath
            if gone >= cfg.breath_lost_s and (s.last_motion or 0) < s.last_breath:
                s.flagged.add("breath_lost")
                ev.append(Event("breath_lost", room, "check_in",
                                {"seconds_without_breathing_signal": round(gone), "last_bpm": s.bpm,
                                 "motion": round(r.motion, 1)}, now))
        return ev


# ------------------------------------------------------------------ Nemotron ----
SYSTEM = """You are GHOST, a camera-less guardian for an older person living alone. You sense rooms
through Wi-Fi (breathing rate, motion), you have learned the home's normal routine from weeks of
unlabelled presence data, and you act through HOTARU, a small robot desk lamp that can light a path,
turn toward a room, change its ring colour, and speak.
You get one event, the rule-based minimum severity (the floor), recent log lines, and numbered
EVIDENCE items (E1, E2, ...) from the Wi-Fi sensors, the learned routine and the lamp.
Decide how serious it is (you may raise it, never go below the floor). Explain WHY in one or two
plain sentences that cite the evidence inline like [E2], using only the ids you were given, and
say what is unusual compared with the learned routine when the evidence shows it. Write what
HOTARU should say out loud (short, warm, calm; or ""), and a message for the family (only if
severity is "alert"; else "").
Never claim certainty you don't have: Wi-Fi sensing can miss someone who left the room, and a
"possible fall" is a guess from a motion burst.
Reply with JSON only:
{"severity": "none|watch|check_in|alert", "explain": str, "cites": ["E1", ...], "say": str, "family": str}"""

TEMPLATES = {
    "got_up": ("Movement in the {room} after {still_minutes} minutes of stillness at night: probably getting up.",
               "", ""),
    "moved": ("Now moving in the {room}, {minutes_since_got_up} min after getting up in the {from}. "
              "Turning to follow.", "", ""),
    "fall_suspected": ("A sharp motion burst in the {room} (jolt {jolt}, walking stays under {walking_jolt_limit}), "
                       "then {seconds_still_after} s of stillness: possibly a fall. Watching closely.", "", ""),
    "long_stay": ("{minutes_in_room} min in the {room}, {minutes_without_motion} min of it without moving. Visits "
                  "{scope} usually last {typical_visit_min} min (longest {longest_visit_min} of "
                  "{visits_learned}). Checking in.", "Are you okay in there? Say something, or tap my button.", ""),
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
RULE_ONLY = {"moved"}  # bookkeeping: never worth a model call

LAMP = {
    "none": [],
    "watch": [{"op": "eye", "mode": "path", "bright": 120, "fade_ms": 4000}],
    "check_in": [{"op": "eye", "mode": "amber"}],
    "alert": [{"op": "eye", "mode": "red"}, {"op": "action", "name": "attention", "mood": "scared"}],
}

_CITE = re.compile(r"\[(E\d+)\]")
_THINK = re.compile(r"<think>.*?</think>", re.S)


def cite(text: str, evidence: list[Evidence], cites: list[str] | None = None) -> tuple[str, list[str]]:
    """Keep only citations to evidence that exists; make sure the explanation cites something."""
    known = {e.id for e in evidence}
    text = _CITE.sub(lambda m: m.group(0) if m.group(1) in known else "", text)
    text = re.sub(r"\s+([.,;:])", r"\1", re.sub(r"  +", " ", text)).strip()
    used = list(dict.fromkeys(_CITE.findall(text) + [c for c in (cites or []) if c in known]))
    if not used and evidence:
        used = [e.id for e in evidence if e.source in ("rule", "routine", "csi")][:3] or [evidence[0].id]
    missing = [c for c in used if f"[{c}]" not in text]
    if missing:
        text = text.rstrip() + " " + "".join(f"[{c}]" for c in missing)
    return text, used


class _Blank(dict):
    def __missing__(self, k):
        return ""


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

    def _rules(self, e: Event, by: str) -> Decision:
        explain, say, fam = self._template(e)
        explain, used = cite(explain, e.evidence)
        return Decision(e.floor, explain, say, fam, LAMP[e.floor], by, used)

    async def decide(self, e: Event) -> Decision:
        floor = e.floor
        if not self.online or e.kind in RULE_ONLY:
            return self._rules(e, "rules")
        tmpl = self._template(e)
        try:
            user = json.dumps({"event": e.kind, "room": e.room, "floor": floor, "facts": e.facts,
                               "local_time": time.strftime("%H:%M", time.localtime(e.t)),
                               "evidence": [x.as_dict() for x in e.evidence],
                               "recent": self.history[-12:]})
            prefix = os.getenv("GHOST_REASON_SYSTEM_PREFIX", "")
            out = await self._chat(self.model, (prefix + "\n" if prefix else "") + SYSTEM, user, 900)
            out = _THINK.sub("", out)
            j = json.loads(out[out.find("{"): out.rfind("}") + 1])
            sev = j.get("severity", floor)
            if sev not in SEVERITY or SEVERITY.index(sev) < SEVERITY.index(floor):
                sev = floor  # the rule's floor always holds
            fam = j.get("family", "") if sev == "alert" else ""
            explain, used = cite(j.get("explain") or tmpl[0], e.evidence, j.get("cites"))
            return Decision(sev, explain, j.get("say", tmpl[1]), fam or (tmpl[2] if sev == "alert" else ""),
                            LAMP[sev], self.model, used)
        except Exception as ex:  # noqa: BLE001 - a model hiccup must not silence the guardian
            log.warning("reasoner fell back to rules: %s", ex)
            return self._rules(e, "rules (model error)")

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
        try:
            return explain.format(**f), say.format(**f), fam.format(**f)
        except KeyError:  # a fact the template expects is missing: say less, never crash
            return f"{e.kind.replace('_', ' ')} in the {e.room}.", say.format_map(_Blank(f)), fam.format_map(_Blank(f))

    async def _chat(self, model: str, system: str, user: str, max_tokens: int) -> str:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self.base}/chat/completions", headers={"Authorization": f"Bearer {self.key}"},
                             json={"model": model, "max_tokens": max_tokens, "temperature": 0.2,
                                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
