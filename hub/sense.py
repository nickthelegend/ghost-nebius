"""Breathing and motion from Wi-Fi CSI.

Chest motion changes how the radio signal reflects around a room, which shows
up as a slow ripple (6-36 breaths/min = 0.1-0.6 Hz) on some subcarrier
amplitudes. Walking shows up as fast, large changes on many of them.

Pipeline per update:
  1. resample the last window onto a uniform 20 Hz grid (Wi-Fi packets jitter)
  2. per subcarrier: remove the mean and slow drift
  3. keep the subcarriers that carry the most breathing-band energy and take
     their first principal component (signs and gains differ per subcarrier)
  4. band-pass 0.1-0.6 Hz -> breathing waveform; FFT peak -> breaths/min
  5. 0.8-4 Hz energy across all subcarriers -> motion index
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from scipy import signal as sps

from .lamp import CsiFrame

FS = 20.0  # analysis rate, Hz
BREATH_BAND = (0.1, 0.6)  # Hz -> 6..36 breaths/min
MOTION_BAND = (0.8, 4.0)


@dataclass
class Reading:
    bpm: float | None  # breaths per minute, None if not confident
    confidence: float  # 0..1, how far the breathing peak stands out
    motion: float  # motion index; > ~3 means someone is moving
    wave: float  # latest breathing waveform value, 0..1, for the lamp's ring
    frames: int  # CSI frames in the window
    rate_hz: float  # CSI packet rate actually received


class BreathSensor:
    def __init__(self, window_s: float = 30.0, top_k: int = 8):
        self.window_s = window_s
        self.top_k = top_k
        self.buf: deque[tuple[float, np.ndarray]] = deque()
        self._wave_scale = 1e-6
        self._motion_base: float | None = None

    def add(self, f: CsiFrame) -> None:
        if len(f.amp) < 8:
            return
        t = f.lamp_ms / 1000.0
        if self.buf and t < self.buf[-1][0] - 5:  # lamp rebooted: clock went back
            self.buf.clear()
        self.buf.append((t, np.frombuffer(f.amp, np.uint8).astype(np.float32)))
        while self.buf and self.buf[-1][0] - self.buf[0][0] > self.window_s:
            self.buf.popleft()

    def _grid(self) -> tuple[np.ndarray, float] | None:
        if len(self.buf) < 40:
            return None
        n_sc = min(len(a) for _, a in self.buf)
        t = np.array([x[0] for x in self.buf])
        a = np.stack([x[1][:n_sc] for x in self.buf])
        span = t[-1] - t[0]
        if span < 8:
            return None
        g = np.arange(t[0], t[-1], 1 / FS)
        # median-filter each subcarrier lightly to knock out single-packet glitches
        a = sps.medfilt(a, kernel_size=(3, 1))
        out = np.stack([np.interp(g, t, a[:, k]) for k in range(n_sc)], axis=1)
        return out, len(t) / span

    def read(self) -> Reading | None:
        grid = self._grid()
        if grid is None:
            return None
        x, rate = grid
        x = sps.detrend(x, axis=0)

        sos_b = sps.butter(3, BREATH_BAND, btype="bandpass", fs=FS, output="sos")
        sos_m = sps.butter(3, MOTION_BAND, btype="bandpass", fs=FS, output="sos")
        xb = sps.sosfiltfilt(sos_b, x, axis=0)
        xm = sps.sosfiltfilt(sos_m, x, axis=0)

        # Motion: high-band energy, relative to a slowly learned quiet baseline.
        m_now = float(np.mean(xm[-int(4 * FS):] ** 2))
        if self._motion_base is None:
            self._motion_base = m_now
        motion = m_now / max(self._motion_base, 1e-6)
        if motion < 2:  # only learn the baseline while the room is calm
            self._motion_base = 0.98 * self._motion_base + 0.02 * m_now

        # Breathing: PCA over the subcarriers that carry the most breathing energy.
        energy = np.var(xb, axis=0)
        top = np.argsort(energy)[::-1][: self.top_k]
        sub = xb[:, top]
        u, s, vt = np.linalg.svd(sub - sub.mean(axis=0), full_matrices=False)
        pc = u[:, 0] * s[0]

        win = np.hanning(len(pc))
        spec = np.abs(np.fft.rfft(pc * win)) ** 2
        f = np.fft.rfftfreq(len(pc), 1 / FS)
        band = (f >= BREATH_BAND[0]) & (f <= BREATH_BAND[1])
        if not band.any():
            return None
        fb, sb = f[band], spec[band]
        i = int(np.argmax(sb))
        # Confidence: share of in-band power within +-0.03 Hz of the peak.
        near = np.abs(fb - fb[i]) <= 0.03
        conf = float(sb[near].sum() / max(sb.sum(), 1e-12))
        bpm = float(fb[i] * 60)
        if 0 < i < len(sb) - 1:  # parabolic refine
            a, b, c = np.log(sb[i - 1:i + 2] + 1e-12)
            d = a - 2 * b + c
            if d:
                bpm = float((fb[i] + 0.5 * (a - c) / d * (fb[1] - fb[0])) * 60)

        # Waveform for the ring: latest value scaled by a slow-moving peak level.
        peak = float(np.max(np.abs(pc[-int(10 * FS):])))
        self._wave_scale = max(peak, 0.9 * self._wave_scale)
        wave = 0.5 + 0.5 * float(pc[-1]) / (self._wave_scale or 1)

        moving = motion > 3
        good = conf > 0.35 and not moving
        return Reading(bpm if good else None, conf, motion, min(1.0, max(0.0, wave)), len(self.buf), rate)
