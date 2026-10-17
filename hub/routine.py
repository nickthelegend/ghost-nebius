"""Learning a home's routine with no labels.

Nobody tells GHOST when Dad sleeps, cooks or uses the bathroom. It only sees,
minute by minute, which rooms have someone in them (breathing or movement on
that room's Wi-Fi). From that alone it learns, per room:

  occupancy baseline   for each half hour of the day, on how many of the past
                       days the room was occupied at all -> P(occupied)
  visits               unbroken stretches of presence, and how long they last
                       at that time of day (a 3 am bathroom visit vs. a bath)

and scores what is happening now against it:

  presence surprise    someone where there usually isn't anyone, or nobody
                       where there usually is (bits of surprise, -log2 P)
  dwell                this visit is far longer than visits at this hour
                       usually are (robust z-score on log-duration)

The model is refit from the history once a day (`fit`), like a nightly job, so
the current night is always judged against the nights before it.

    python -m hub.routine fit data/live/routine.json     # refit a saved history
    python -m hub.routine show data/live/routine.json bathroom
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DAY = 86400
UNSEEN, ABSENT, PRESENT = -1, 0, 1


def _local(t: float) -> tuple[int, int]:
    """(day number, minute of day) in local time."""
    lt = time.localtime(t)
    day = int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 12, 0, 0, 0, 0, -1)) // DAY)
    return day, lt.tm_hour * 60 + lt.tm_min


def _midnight(day: int) -> float:
    """Local midnight at the start of a day number from _local."""
    lt = time.localtime(day * DAY + DAY / 2)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


def hhmm(minute: int) -> str:
    return f"{minute // 60 % 24:02d}:{minute % 60:02d}"


@dataclass
class Visit:
    start: float
    end: float

    @property
    def minutes(self) -> float:
        return (self.end - self.start) / 60


@dataclass
class RoomModel:
    """What was learned for one room at the last fit."""
    baseline: list[float]  # P(occupied) per bin, smoothed
    occupied_days: list[int]  # raw counts per bin, for citing
    days: list[int]
    visits: list[Visit] = field(default_factory=list)


class Routine:
    def __init__(self, bin_minutes: int = 30, gap_s: float = 120, min_visit_s: float = 45, hours_around: float = 2.0):
        self.bin_minutes = bin_minutes
        self.bins = 1440 // bin_minutes
        self.gap_s = gap_s  # a gap shorter than this doesn't end a visit
        self.min_visit_s = min_visit_s
        self.hours_around = hours_around  # visits that started within this many hours count as "this time of day"
        self.minutes: dict[str, dict[int, np.ndarray]] = {}  # room -> day -> 1440 x {-1, 0, 1}
        self.visits: dict[str, list[Visit]] = {}
        self._open: dict[str, list[float]] = {}  # room -> [start, last seen]
        self.model: dict[str, RoomModel] = {}
        self.fitted_until: int | None = None  # the model uses days before this one

    # ------------------------------------------------------------ observing ----
    def observe(self, t: float, room: str, present: bool) -> None:
        day, minute = _local(t)
        arr = self.minutes.setdefault(room, {}).get(day)
        if arr is None:
            arr = self.minutes[room][day] = np.full(1440, UNSEEN, np.int8)
        arr[minute] = max(arr[minute], PRESENT if present else ABSENT)
        o = self._open.get(room)
        if present:
            if o and t - o[1] <= self.gap_s:
                o[1] = t
            else:
                self._close(room)
                self._open[room] = [t, t]
        elif o and t - o[1] > self.gap_s:
            self._close(room)

    def _close(self, room: str) -> None:
        o = self._open.pop(room, None)
        if o and o[1] - o[0] >= self.min_visit_s:
            self.visits.setdefault(room, []).append(Visit(o[0], o[1]))

    def current_visit(self, room: str) -> Visit | None:
        o = self._open.get(room)
        return Visit(o[0], o[1]) if o else None

    # -------------------------------------------------------------- learning ----
    def fit(self, before: float | None = None) -> None:
        """Learn from every whole day before the day of `before` (default: now)."""
        cutoff_day, _ = _local(before if before is not None else time.time())
        cutoff_t = _midnight(cutoff_day)
        self.model = {}
        for room, days in self.minutes.items():
            occ = np.zeros(self.bins)
            seen = np.zeros(self.bins)
            for day, arr in days.items():
                if day >= cutoff_day:
                    continue
                b = arr.reshape(self.bins, self.bin_minutes)
                observed = (b != UNSEEN).sum(axis=1) >= self.bin_minutes // 3
                seen += observed
                occ += observed & (b == PRESENT).any(axis=1)
            p = (occ + 0.5) / (seen + 1.0)  # Jeffreys prior: no days -> 0.5, honest about not knowing
            p = 0.2 * np.roll(p, 1) + 0.6 * p + 0.2 * np.roll(p, -1)
            self.model[room] = RoomModel([round(float(x), 4) for x in p], [int(x) for x in occ], [int(x) for x in seen],
                                         [v for v in self.visits.get(room, []) if v.start < cutoff_t])
        self.fitted_until = cutoff_day

    @property
    def nights(self) -> int:
        """How many whole days the model has learned from."""
        return max((max(m.days) for m in self.model.values()), default=0)

    # --------------------------------------------------------------- scoring ----
    def bin_of(self, t: float) -> int:
        return _local(t)[1] // self.bin_minutes

    def bin_label(self, b: int) -> str:
        return f"{hhmm(b * self.bin_minutes)}-{hhmm((b + 1) * self.bin_minutes)}"

    def presence_score(self, room: str, t: float, present: bool) -> dict:
        """How surprising it is that the room is (or isn't) occupied right now."""
        m = self.model.get(room)
        b = self.bin_of(t)
        if not m or not m.days[b]:
            return {"score": 0.0, "bits": 0.0, "p": None, "occupied_days": 0, "days": 0, "bin": self.bin_label(b)}
        p = m.baseline[b]
        bits = -math.log2(max(1e-3, p if present else 1 - p))
        return {"score": round(min(1.0, bits / 5), 3), "bits": round(bits, 2), "p": round(p, 3),
                "occupied_days": m.occupied_days[b], "days": m.days[b], "bin": self.bin_label(b), "present": present}

    def dwell_stats(self, room: str, t: float) -> dict | None:
        """Visits to this room that started around this time of day."""
        m = self.model.get(room)
        if not m or not m.visits:
            return None
        _, minute = _local(t)
        win = self.hours_around * 60

        def near(v: Visit) -> bool:
            d = abs(_local(v.start)[1] - minute)
            return min(d, 1440 - d) <= win
        vs = [v for v in m.visits if near(v)]
        scope = f"within {self.hours_around:g} h of {hhmm(minute)}"
        if len(vs) < 3:
            vs, scope = m.visits, "at any time of day"
        if len(vs) < 3:
            return None
        mins = np.array([v.minutes for v in vs])
        logs = np.log(mins)
        med = float(np.median(logs))
        mad = float(np.median(np.abs(logs - med))) * 1.4826
        return {"n": len(vs), "scope": scope, "median_min": round(float(np.exp(med)), 1),
                "p90_min": round(float(np.percentile(mins, 90)), 1), "longest_min": round(float(mins.max()), 1),
                "log_median": med, "log_spread": max(mad, 0.15),
                "nights_with_visit": len({_local(v.start)[0] for v in vs})}

    def dwell_score(self, room: str, start: float, seconds: float) -> dict:
        """Is a visit that started at `start` and has lasted `seconds` unusually long?"""
        st = self.dwell_stats(room, start)
        minutes = seconds / 60
        if st is None or minutes <= 0:
            return {"score": 0.0, "anomalous": False, "minutes": round(minutes, 1), "n": 0}
        z = (math.log(minutes) - st["log_median"]) / st["log_spread"]
        anomalous = z >= 2.5 and minutes >= 1.5 * st["p90_min"]
        out = {k: v for k, v in st.items() if not k.startswith("log_")}
        return {**out, "score": round(max(0.0, min(1.0, z / 5)), 3), "z": round(z, 2), "anomalous": anomalous,
                "minutes": round(minutes, 1), "times_typical": round(minutes / max(st["median_min"], 0.1), 1)}

    def anomaly(self, room: str, t: float, present: bool) -> dict:
        """One 0..1 number for the dashboard: the larger of presence surprise and dwell."""
        ps = self.presence_score(room, t, present)
        v = self.current_visit(room) if present else None
        ds = self.dwell_score(room, v.start, t - v.start) if v else {"score": 0.0}
        return {"score": max(ps["score"], ds["score"]), "presence": ps, "dwell": ds if v else None}

    # ------------------------------------------------------------- reporting ----
    def today(self, room: str, now: float) -> list[float | None]:
        """Share of observed minutes occupied, per bin of the day, over the 24 h ending now.
        Indexed by bin of day, like the baseline (the bins after now are from yesterday)."""
        out: list[list[int]] = [[0, 0] for _ in range(self.bins)]
        days = self.minutes.get(room, {})
        start = now - DAY + 60
        for k in range(0, 1440, 1):
            day, minute = _local(start + k * 60)
            arr = days.get(day)
            if arr is None or arr[minute] == UNSEEN:
                continue
            c = out[minute // self.bin_minutes]
            c[0] += int(arr[minute] == PRESENT)
            c[1] += 1
        return [round(a / n, 3) if n else None for a, n in out]

    def summary(self, room: str, t: float) -> str:
        ps = self.presence_score(room, t, True)
        st = self.dwell_stats(room, t)
        bits = [f"{room} occupied at {ps['bin']} on {ps['occupied_days']} of {ps['days']} days"]
        if st:
            bits.append(f"{st['n']} visits {st['scope']}, median {st['median_min']} min, longest {st['longest_min']} min")
        return "; ".join(bits)

    # ------------------------------------------------------------ persistence ----
    def to_json(self) -> dict:
        enc = {UNSEEN: ".", ABSENT: "0", PRESENT: "1"}
        return {"bin_minutes": self.bin_minutes, "gap_s": self.gap_s, "min_visit_s": self.min_visit_s,
                "minutes": {r: {str(d): "".join(enc[int(x)] for x in a) for d, a in days.items()}
                            for r, days in self.minutes.items()},
                "visits": {r: [[v.start, v.end] for v in vs] for r, vs in self.visits.items()}}

    @classmethod
    def from_json(cls, j: dict) -> "Routine":
        r = cls(j.get("bin_minutes", 30), j.get("gap_s", 120), j.get("min_visit_s", 45))
        dec = {".": UNSEEN, "0": ABSENT, "1": PRESENT}
        for room, days in j.get("minutes", {}).items():
            r.minutes[room] = {int(d): np.array([dec[c] for c in s], np.int8) for d, s in days.items()}
        r.visits = {room: [Visit(a, b) for a, b in vs] for room, vs in j.get("visits", {}).items()}
        return r

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_json()))

    @classmethod
    def load(cls, path: str | Path) -> "Routine":
        return cls.from_json(json.loads(Path(path).read_text()))


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    r = Routine.load(path)
    r.fit()
    if cmd == "fit":
        r.save(path)
        print(f"fit {path}: {r.nights} days, rooms {sorted(r.model)}")
    elif cmd == "show":
        room = sys.argv[3]
        m = r.model[room]
        for b in range(r.bins):
            print(f"{r.bin_label(b)}  {'#' * round(m.baseline[b] * 40):40s} {m.occupied_days[b]}/{m.days[b]}")
        print(r.summary(room, time.time()))
