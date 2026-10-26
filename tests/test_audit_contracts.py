"""Local format, provenance, and queue regressions from the audit."""
import asyncio
import gzip
import struct

import pytest

from hub import scenario
from hub.act import VirtualHub, VirtualLamp
from hub.agent import Config, Event, Reasoner
from hub.lamp import CsiFrame, parse_csi
from hub.replay import MAGIC, Recording, Writer
from hub.run import Guardian
from hub.server import Session


def test_truncated_csi_does_not_yield_a_partial_frame():
    packet = b'GC1\x01' + struct.pack('<IbB', 1000, -50, 12) + b'abc'
    assert parse_csi(packet) == []
    packet = b'GC1\x01' + struct.pack('<IbB', 1000, -50, 3) + b'abc'
    assert parse_csi(packet)[0].amp == b'abc'
    assert parse_csi(b'GC1\x01\0') == []


def test_truncated_recording_is_rejected(tmp_path):
    file = tmp_path / 'broken.ghostcsi'
    writer = Writer(file, {'scene_start': 10})
    writer.frame(1, 'room', 1000, -50, b'12345678')
    writer.close()
    raw = gzip.decompress(file.read_bytes())
    file.write_bytes(gzip.compress(raw[:-3]))
    with pytest.raises(ValueError, match='truncated frame'):
        Recording.load(file)
    for payload in (MAGIC+b'{}\n\x01', MAGIC+b'{}\n\x00', b'not a recording'):
        file.write_bytes(gzip.compress(payload))
        with pytest.raises(ValueError):
            Recording.load(file)


def test_unlabelled_recording_never_gets_synthetic_routine(tmp_path):
    file = tmp_path / 'empty.ghostcsi'
    Writer(file, {'scene_start': scenario.scene_start(), 'scale': 1}).close()
    s = Session(file)
    # There is no recorded live routine in this clean audit worktree.
    assert not s.routine.model
    assert s.snapshot()['routine'] is None
    assert not s.snapshot()['replay']['synthetic']
    assert all(r['state'] in ('waiting', 'no sensor') for r in s.snapshot()['rooms'].values())


def test_sensor_warmup_is_waiting_instead_of_invented_empty():
    g = Guardian(VirtualHub(), Config(), {}, Reasoner(), None, live_csi=False)
    g.feed(CsiFrame(1000, -50, b'12345678', source='room'))
    assert g.room_view('room', 1000)['state'] == 'waiting'
    assert g.room_view('room', 1000)['bpm'] is None


def test_guardian_without_devices_ticks_without_inventing_a_lamp():
    async def go():
        s = Session(None)
        await s.g.tick()
        assert not s.snapshot()['lamp']['connected']
        assert s.snapshot()['timeline'] == []
    asyncio.run(go())


def test_decision_queue_recovers_after_invalid_event():
    async def go():
        g = Guardian(VirtualHub(VirtualLamp()), Config(), {}, Reasoner(), None, live_csi=False)
        g._queue = asyncio.Queue()
        g._worker = asyncio.create_task(g._work())
        await g._queue.put(Event('unrecognised', 'room', 'invalid', {}, 10))
        await g._queue.put(Event('moved', 'room', 'watch', {'from':'bedroom'}, 11))
        await asyncio.wait_for(g.idle(), 3)
        assert len(g.decisions) == 1 and g.decisions[0]['event'] == 'moved'
        g._worker.cancel()
        await asyncio.gather(g._worker, return_exceptions=True)
    asyncio.run(go())


def test_headless_calendar_maintenance_uses_real_persisted_history(tmp_path):
    import time
    from hub.routine import Routine
    from hub.run import maintain_routine

    now = scenario.scene_start()
    r = scenario.build_routine(now)  # the same explicitly synthetic bundled history
    path = tmp_path / 'routine.json'
    fitted_day = time.localtime(now).tm_yday
    baseline = list(r.model['bathroom'].baseline)
    for k in range(30):
        r.observe(now + k * 60, 'bathroom', True)
    saved, fitted_day = maintain_routine(r, path, now, 0, fitted_day)
    assert saved == now and Routine.load(path).to_json() == r.to_json()
    assert r.model['bathroom'].baseline == baseline

    lt = time.localtime(now)
    before_noon = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, 11, 59, 0, 0, 0, -1))
    saved, same_day = maintain_routine(r, path, before_noon, saved, fitted_day)
    assert same_day == fitted_day and r.model['bathroom'].baseline == baseline
    noon = before_noon + 60
    saved, fitted_day = maintain_routine(r, path, noon, saved, fitted_day)
    assert fitted_day == time.localtime(noon).tm_yday
    assert r.model['bathroom'].baseline != baseline
    model = r.model
    saved, _ = maintain_routine(r, path, noon + 60, saved, fitted_day)
    assert r.model is model  # a second tick on this day does not fit a second model
    loaded = Routine.load(path)
    loaded.fit(before=noon)
    assert loaded.model['bathroom'].baseline == r.model['bathroom'].baseline
