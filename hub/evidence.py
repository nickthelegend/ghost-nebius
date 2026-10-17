"""What an explanation may cite.

The Witness keeps the last half hour of every room's readings. When an event
fires it writes numbered evidence, one sentence each, with the numbers in it:

  E1 rule      the rule that fired and its facts
  E2.. csi     what the Wi-Fi in the event's room (and the room the person came
               from) actually measured: breathing rate, motion, the strongest jolt
  E.. routine  what the learned routine says about this room at this hour
  E.. lamp     what HOTARU did and heard (a check-in with no answer)
  E.. earlier  events in the last half hour that led here

Nemotron gets these and must cite them by id; the dashboard shows them under
the explanation, so anyone can check the claim against the measurement.
"""

from __future__ import annotations

import time
from collections import deque

from .agent import Event, Evidence
from .sense import Reading


def clock(t: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(t))


RULE_TEXT = {
    "got_up": "Rule got_up: movement (motion {motion}) after {still_minutes} min of stillness, at night.",
    "moved": "Rule moved: the person who got up is now moving here (motion {motion}), came from the {from}.",
    "fall_suspected": "Rule fall_suspected: a half-second jolt of {jolt} (walking stays under {walking_jolt_limit}), "
                      "then {seconds_still_after} s without movement.",
    "long_stay": "Rule long_stay: {minutes_in_room} min in this room, the last {minutes_without_motion} min "
                 "without movement ({times_typical}x a typical visit).",
    "too_still": "Rule too_still: got up {minutes_since_got_up} min ago, no movement for {minutes_without_motion} min.",
    "breath_lost": "Rule breath_lost: breathing was {last_bpm} breaths/min, then no breathing signal for "
                   "{seconds_without_breathing_signal} s, with no movement.",
    "no_answer": "Rule no_answer: the check-in got no voice and no button press in {seconds} s.",
    "answered": "Rule answered: the person answered by {how}.",
}


class Witness:
    def __init__(self, keep_s: float = 1800):
        self.keep_s = keep_s
        self.hist: dict[str, deque] = {}  # room -> (t, bpm, conf, motion, jolt, present)
        self.events: deque = deque(maxlen=50)  # (t, kind, room, severity)

    def record(self, room: str, t: float, r: Reading, present: bool) -> None:
        h = self.hist.setdefault(room, deque())
        h.append((t, r.bpm, r.confidence, r.motion, r.jolt, present))
        while h and t - h[0][0] > self.keep_s:
            h.popleft()

    def decided(self, t: float, kind: str, room: str, severity: str) -> None:
        self.events.append((t, kind, room, severity))

    # ------------------------------------------------------------------------
    def csi(self, room: str, now: float, window_s: float = 600) -> str | None:
        h = [x for x in self.hist.get(room, ()) if now - x[0] <= window_s]
        if not h:
            return None
        span = f"{clock(h[0][0])}-{clock(h[-1][0])}"
        bpms = [x[1] for x in h if x[1]]
        moving = [x for x in h if x[3] >= 3]
        parts = [f"{room} Wi-Fi, {span}:"]
        if bpms:
            confs = [x[2] for x in h if x[1]]
            parts.append(f"breathing {sorted(bpms)[len(bpms) // 2]:.1f} breaths/min (median, confidence "
                         f"{sum(confs) / len(confs):.2f}) in {100 * len(bpms) // len(h)}% of readings;")
        else:
            parts.append("no breathing signal;")
        if moving:
            last = moving[-1][0]
            parts.append(f"movement until {clock(last)} (peak motion {max(x[3] for x in h):.0f}x the quiet level)"
                         + (f", still since then" if now - last >= 5 else "") + ";")
        else:
            parts.append(f"no movement (motion {max(x[3] for x in h):.1f}x the quiet level);")
        jolt = max(h, key=lambda x: x[4])
        if jolt[4] >= 100:
            parts.append(f"strongest jolt {jolt[4]:.0f} at {clock(jolt[0])};")
        last_present = [x for x in h if x[5]]
        if not h[-1][5]:
            parts.append(f"empty now" + (f", last sign of anyone {clock(last_present[-1][0])}" if last_present else "") + ".")
        return " ".join(parts).rstrip(";") + ("" if parts[-1].endswith(".") else ".")

    def for_event(self, e: Event, routine=None, came_from: str | None = None, sleep_rooms=()) -> list[Evidence]:
        out: list[Evidence] = []

        def add(source: str, room: str, text: str | None, data: dict | None = None) -> None:
            if text:
                out.append(Evidence(f"E{len(out) + 1}", source, room, text, dict(data or {})))

        tmpl = RULE_TEXT.get(e.kind)
        if tmpl:
            try:
                add("rule", e.room, tmpl.format(**e.facts), e.facts)
            except (KeyError, ValueError):
                add("rule", e.room, f"Rule {e.kind}: {e.facts}", e.facts)
        if e.kind in ("no_answer", "answered"):
            add("lamp", e.room, f"HOTARU asked at {clock(e.facts.get('asked_at', e.t))}"
                + (f" \"{e.facts['asked']}\"" if e.facts.get("asked") else "")
                + (f" and heard: {e.facts.get('text')!r}." if e.facts.get("text") else
                   f" and got {'a ' + e.facts['how'] if e.facts.get('how') else 'no'} answer."))
        add("csi", e.room, self.csi(e.room, e.t))
        others = [came_from] if came_from else []
        others += [r for r in sleep_rooms if r not in others]
        for room in others:
            if room and room != e.room and room in self.hist:
                add("csi", room, self.csi(room, e.t))
        if routine is not None and routine.model:
            ps = routine.presence_score(e.room, e.t, True)
            if ps["days"]:
                add("routine", e.room,
                    f"Learned, no labels: the {e.room} is occupied at {ps['bin']} on {ps['occupied_days']} of "
                    f"{ps['days']} days (P={ps['p']:.2f}); being here now is {ps['bits']:.1f} bits of surprise.",
                    ps)
            st = routine.dwell_stats(e.room, e.t)
            if st and e.kind in ("long_stay", "too_still", "fall_suspected", "no_answer", "moved"):
                add("routine", e.room,
                    f"Learned visits to the {e.room} {st['scope']}: {st['n']} over {st['nights_with_visit']} days, "
                    f"median {st['median_min']} min, 90% under {st['p90_min']} min, longest {st['longest_min']} min.",
                    {k: v for k, v in st.items() if not k.startswith("log_")})
            for room in others:
                if room and room != e.room and room in routine.model:
                    present = bool(self.hist.get(room)) and self.hist[room][-1][5]
                    ps = routine.presence_score(room, e.t, present)
                    if ps["days"] and not present and ps["p"] and ps["p"] >= 0.5:
                        add("routine", room,
                            f"Learned: the {room} is occupied at {ps['bin']} on {ps['occupied_days']} of "
                            f"{ps['days']} days, and it is empty now.", ps)
        for t, kind, room, sev in self.events:
            if e.t - t <= 1800 and kind not in ("moved",) and (t, kind) != (e.t, e.kind):
                add("earlier", room, f"Earlier at {clock(t)}: {kind.replace('_', ' ')} in the {room} ({sev}).")
        return out
