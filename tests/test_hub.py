"""GHOST hub tests: the breathing estimator against known synthetic CSI, and the
lamp link against a fake HOTARU over real sockets."""

import asyncio
import math
import random

import pytest

from hub.fake_lamp import FakeLamp
from hub.lamp import CsiFrame, LampHub, parse_csi
from hub.sense import BreathSensor


def frames(seconds=40, hz=100, bpm=14.0, present=True, walking=False, seed=0):
    rng = random.Random(seed)
    base = [40 + 30 * math.sin(k / 5) for k in range(64)]
    gain = [0.0 if k % 3 else 6.0 * math.cos(k / 7) for k in range(64)]
    t = 0.0
    while t < seconds:
        breath = math.sin(2 * math.pi * bpm / 60 * t) if present else 0.0
        walk = [rng.gauss(0, 12) if walking else 0.0 for _ in range(64)]
        amp = bytes(max(0, min(255, int(base[k] + gain[k] * breath + walk[k] + rng.gauss(0, 1.5)))) for k in range(64))
        yield CsiFrame(int(t * 1000), -50, amp)
        t += 1 / hz * rng.uniform(0.6, 1.4)  # Wi-Fi packets don't arrive on a clock


@pytest.mark.parametrize("bpm", [8.0, 14.0, 22.0])
def test_breathing_rate(bpm):
    s = BreathSensor()
    for f in frames(bpm=bpm):
        s.add(f)
    r = s.read()
    assert r is not None and r.bpm is not None
    assert r.bpm == pytest.approx(bpm, abs=1.0)
    assert r.confidence > 0.35


def test_empty_room_has_no_confident_breathing():
    s = BreathSensor()
    for f in frames(present=False):
        s.add(f)
    r = s.read()
    assert r is not None and r.bpm is None


def test_walking_raises_motion_and_suppresses_rate():
    s = BreathSensor()
    for f in frames(seconds=35):
        s.add(f)
    calm = s.read()
    for f in frames(seconds=8, walking=True, seed=3):
        s.add(CsiFrame(f.lamp_ms + 35_000, f.rssi, f.amp))
    moving = s.read()
    assert moving.motion > 3 * max(calm.motion, 0.3)
    assert moving.bpm is None


def test_parse_csi_roundtrip():
    import struct
    recs = [struct.pack("<Ibb", 1000 + i, -40, 3) + bytes([i, i + 1, i + 2]) for i in range(2)]
    out = parse_csi(b"GC1" + bytes([2]) + b"".join(recs))
    assert [o.lamp_ms for o in out] == [1000, 1001]
    assert out[1].amp == bytes([1, 2, 3])
    assert parse_csi(b"nope") == []


async def _with_lamp(reply: str, body):
    hub = LampHub("127.0.0.1", 0)
    hub.port = 0
    # bind to free ports: start TCP first, then UDP on its neighbour
    for port in range(18770, 18870, 2):
        hub.port = port
        try:
            await hub.start()
            break
        except OSError:
            continue
    fake = FakeLamp("127.0.0.1", hub.port, reply=reply, quiet=True)
    task = asyncio.create_task(fake.run())
    try:
        lamp = await hub.wait_for_lamp(5)
        return await body(hub, lamp, fake)
    finally:
        task.cancel()
        await hub.close()


def test_link_hello_commands_and_csi():
    async def body(hub, lamp, fake):
        assert lamp.hello.get("fw") == "hotaru3-ghost"
        await lamp.eye("path", fade_ms=4000)
        await lamp.look(-40)
        await lamp.action("nod", mood="happy")
        await asyncio.sleep(0.5)
        ops = [o["op"] for o in fake.ops]
        assert ops[:3] == ["eye", "look", "action"]
        assert fake.ops[0] == {"op": "eye", "mode": "path", "fade_ms": 4000}
        assert hub.csi_count > 10  # fake lamp streams CSI at 100 Hz
    asyncio.run(_with_lamp("", body))


def test_ask_voice_answer():
    async def body(hub, lamp, fake):
        return await lamp.ask("Are you okay?", listen_ms=1000)
    r = asyncio.run(_with_lamp("I'm fine, just getting water", body))
    assert r == {"answered": True, "how": "voice", "text": "I'm fine, just getting water"}


def test_ask_button_answer():
    async def body(hub, lamp, fake):
        async def press_later():
            await asyncio.sleep(1.5)  # after the recording ends, during the grace period
            await fake.tap()
        asyncio.create_task(press_later())
        return await lamp.ask("Are you okay?", listen_ms=1000)
    r = asyncio.run(_with_lamp("", body))
    assert r["answered"] and r["how"] == "button"


def test_ask_no_answer():
    async def body(hub, lamp, fake):
        return await lamp.ask("Are you okay?", listen_ms=1000)
    r = asyncio.run(_with_lamp("", body))
    assert r == {"answered": False, "how": "silence", "text": ""}
