"""The 3 am night, as a recording, plus the two weeks of routine before it.

Until the ESP32 boards are in the flat, this synthesizes both from the same
channel model the tests use (each room's subcarriers ripple with the chest,
walking adds broadband noise, an impact adds a short violent burst):

  history   14 days of one person's minute-by-minute presence: sleep around
            22:30-06:45, meals, the sofa, the odd night-time bathroom visit of
            3-6 minutes. GHOST learns its routine from this with no labels.
  the night 02:50  asleep in the bedroom, breathing ~12.5/min
            03:04  gets up, walks out
            03:06  in the bathroom, moving about
            03:09  falls; lies still, breathing ~19/min, a weaker ripple
            ...    the long_stay check-in comes ~03:15, the alert after it

Once you have hardware, record a real night with `python -m hub.replay record`
and point the dashboard at it with `python -m hub.server --recording <file>`.

    python -m hub.scenario            # (re)writes data/replay/3am.ghostcsi
"""

from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path

import numpy as np

from .replay import Writer
from .routine import Routine

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "demo" / "home.json"
RECORDING = ROOT / "data" / "replay" / "3am.ghostcsi"
SCALE = 20  # scene seconds per recorded second
CSI_HZ = 30
SENSED = ["bedroom", "bathroom", "kitchen", "living"]


def scene_start() -> float:
    return time.mktime((2026, 10, 17, 2, 50, 0, 0, 0, -1))


# Ground truth, in recording seconds. GHOST never sees these labels.
TRUTH = [
    (0, "Asleep, breathing ~12.5/min"),
    (42, "Gets up"),
    (47, "To the bathroom"),
    (56, "Falls, then lies still breathing ~19/min"),
]
DURATION = 130.0


def _person(t: float) -> dict[str, dict]:
    """Where the person is at recording time t and what their body is doing there."""
    if t < 42:
        return {"bedroom": {"bpm": 12.5, "gain": 1.0}}
    if t < 47:
        return {"bedroom": {"walk": 10.0}}
    if t < 50:
        return {}  # the hall has no sensor
    if t < 55.5:
        return {"bathroom": {"walk": 10.0}}
    if t < 56.1:
        return {"bathroom": {"walk": 50.0}}  # the impact
    return {"bathroom": {"bpm": 19.0, "gain": 0.7}}


def write_night(path: str | Path = RECORDING, seed: int = 3) -> Path:
    rng = np.random.default_rng(seed)
    w = Writer(path, {"scene_start": scene_start(), "scale": SCALE, "synthetic": True, "csi_hz": CSI_HZ,
                      "markers": [{"t": t, "label": s} for t, s in TRUTH],
                      "note": "Synthesized from the channel model in hub/scenario.py until a real night is recorded."})
    streams = []
    for k, room in enumerate(SENSED):
        r = np.random.default_rng(seed * 100 + k)
        n = int(DURATION * CSI_HZ * 1.02)
        dt = (1 / CSI_HZ) * r.uniform(0.6, 1.4, n)  # Wi-Fi packets don't arrive on a clock
        ts = np.cumsum(dt) + r.uniform(0, 1 / CSI_HZ)
        ts = ts[ts < DURATION]
        sc = np.arange(64)
        base = 40 + 30 * np.sin(sc / (4 + k)) + 8 * k
        gain = np.where((sc + k) % 3, 0.0, 6.0 * np.cos(sc / (6 + k)))
        streams.append((room, ts, base, gain))
    frames = []
    for room, ts, base, gain in streams:
        amps = np.empty((len(ts), 64), np.uint8)
        for j, t in enumerate(ts):
            body = _person(float(t)).get(room, {})
            x = base + rng.normal(0, 1.5, 64)
            if "bpm" in body:
                x = x + body["gain"] * gain * math.sin(2 * math.pi * body["bpm"] / 60 * t)
            if "walk" in body:
                x = x + rng.normal(0, body["walk"], 64)
            amps[j] = np.clip(x, 0, 255).astype(np.uint8)
        frames += [(float(t), room, amps[j].tobytes()) for j, t in enumerate(ts)]
    frames.sort(key=lambda f: f[0])
    rssi = {"bedroom": -52, "bathroom": -58, "kitchen": -61, "living": -47}
    for t, room, amp in frames:
        w.frame(t, room, int(t * 1000), rssi[room], amp)
    w.close()
    return Path(path)


def ensure_night() -> Path:
    return RECORDING if RECORDING.exists() else write_night()


# ----------------------------------------------------------------- the routine ----
def _days_of(end: float, days: int) -> list[float]:
    lt = time.localtime(end)
    return [time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - d, 0, 0, 0, 0, 0, -1)) for d in range(days, -1, -1)]


def history_segments(end: float, days: int = 14, seed: int = 7) -> list[tuple[float, float, str | None]]:
    """(start, end, room) from `days` days before `end` up to `end`. None = out, or in the hall."""
    rng = random.Random(seed)
    m = 60.0
    segs: list[tuple[float, float, str | None]] = []
    mids = _days_of(end, days + 1)
    prev_bed = mids[0] - 90 * m  # the evening before the first day
    for D in mids[1:]:
        wake = D + (6 * 60 + 45 + rng.gauss(0, 15)) * m
        # the night: bed from last night's bedtime to this morning, maybe one bathroom visit
        if rng.random() < 0.6 and D + 4.5 * 3600 < end:
            at = D + rng.uniform(1.5, 4.5) * 3600
            dur = math.exp(rng.gauss(math.log(4.2), 0.3)) * m
            segs += [(prev_bed, at, "bedroom"), (at + 30, at + 30 + dur, "bathroom"), (at + 60 + dur, wake, "bedroom")]
        else:
            segs.append((prev_bed, wake, "bedroom"))
        if wake >= end:
            break
        t = wake

        def go(room: str | None, minutes: float, gap: float = 1.0) -> None:
            nonlocal t
            segs.append((t + gap * m, t + (gap + minutes) * m, room))
            t += (gap + minutes) * m

        go("bathroom", rng.gauss(10, 2.5))
        go("kitchen", rng.gauss(30, 6))
        go("living", (12 * 60 + 10 + rng.gauss(0, 20)) - (t - D) / m)
        go("kitchen", rng.gauss(40, 8))
        if rng.random() < 0.3:
            go(None, rng.gauss(75, 15))  # out for a walk
        go("living", (18 * 60 + 30 + rng.gauss(0, 20)) - (t - D) / m)
        go("kitchen", rng.gauss(45, 8))
        go("living", (22 * 60 + 10 + rng.gauss(0, 12)) - (t - D) / m)
        go("bathroom", rng.gauss(12, 3))
        prev_bed = t + m
    return [(a, min(b, end), r) for a, b, r in segs if a < end and b > a]


def build_routine(end: float | None = None, days: int = 14, seed: int = 7) -> Routine:
    """A Routine that has watched `days` days of presence (no labels) up to `end`, fit on the days before it."""
    end = end or scene_start()
    r = Routine()
    segs = sorted(history_segments(end, days, seed))
    first = _days_of(end, days)[0]
    i = 0
    t = first
    while t < end:
        while i < len(segs) and segs[i][1] <= t:
            i += 1
        here = next((room for a, b, room in segs[i:i + 3] if a <= t < b), None)
        for room in SENSED:
            r.observe(t, room, room == here)
        t += 60
    r.fit(before=end)
    return r


def home() -> dict:
    return json.loads(HOME.read_text())


if __name__ == "__main__":
    p = write_night()
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")
    r = build_routine()
    for room in SENSED:
        print(r.summary(room, scene_start() + 25 * 60))
