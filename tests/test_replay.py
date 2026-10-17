"""The recorded 3 am night, end to end with no hardware, and the dashboard's API."""

import asyncio
import json

import pytest

from hub import scenario
from hub.act import VirtualHub, VirtualLamp
from hub.agent import Config, Reasoner
from hub.replay import Recording, Replay, Writer
from hub.run import Guardian


def test_recording_roundtrip(tmp_path):
    p = tmp_path / "x.ghostcsi"
    w = Writer(p, {"scene_start": 100, "scale": 2, "markers": [{"t": 1, "label": "x"}]})
    w.frame(0.5, "bedroom", 500, -50, bytes([1, 2, 3]))
    w.frame(0.6, "bathroom", 600, -60, bytes([4, 5]))
    w.frame(0.7, "bedroom", 700, -51, bytes([6]))
    w.close()
    r = Recording.load(p)
    assert r.rooms == ["bedroom", "bathroom"] and r.scale == 2 and r.scene_start == 100
    assert [(t, f.source, f.amp) for t, f in r.frames] == [(0.5, "bedroom", b"\x01\x02\x03"),
                                                            (0.6, "bathroom", b"\x04\x05"), (0.7, "bedroom", b"\x06")]


@pytest.fixture(scope="module")
def night(tmp_path_factory):
    return Recording.load(scenario.write_night(tmp_path_factory.mktemp("rec") / "3am.ghostcsi"))


def replay(night, reply=""):
    async def go():
        hub = VirtualHub(VirtualLamp(reply=reply, speed=0.02))
        g = Guardian(hub, Config.replay(), scenario.home()["rooms"], Reasoner(), "auto",
                     routine=scenario.build_routine(night.scene_start), live_csi=False, real_alerts=False)
        rp = Replay(night, g)
        g.clock = rp.scene_now
        await rp.fast()
        return g, hub.lamp
    return asyncio.run(go())


def test_the_3am_night_end_to_end(night):
    g, lamp = replay(night)
    seq = [(d["event"], d["room"], d["severity"]) for d in g.decisions]
    assert seq == [("got_up", "bedroom", "watch"), ("moved", "bathroom", "watch"),
                   ("fall_suspected", "bathroom", "watch"), ("long_stay", "bathroom", "check_in"),
                   ("no_answer", "bathroom", "alert")], seq
    ls = g.decisions[3]
    sources = {e["source"] for e in ls["evidence"]}
    assert {"rule", "csi", "routine"} <= sources
    assert ls["cites"] and all(f"[{c}]" in ls["explain"] for c in ls["cites"])
    assert any("Learned visits to the bathroom" in e["text"] for e in ls["evidence"])
    # HOTARU: path light and turn to the bedroom, follow to the bathroom, amber + ask, then red and the call
    assert {"op": "look", "pan": -47.0} in lamp.ops and {"op": "look", "pan": 7.0} in lamp.ops
    assert {"op": "eye", "mode": "amber"} in lamp.ops and "listen" in [o["op"] for o in lamp.ops]
    assert lamp.state.eye == "red" and lamp.state.pan == 7.0
    assert g.decisions[-1]["outcome"].startswith("family alerted (dry run")


def test_an_answer_stands_it_down(night):
    g, lamp = replay(night, reply="I slipped but I'm okay")
    kinds = [d["event"] for d in g.decisions]
    assert "answered" in kinds and "no_answer" not in kinds
    assert lamp.state.eye == "path" and lamp.state.action == "nod"


def test_dashboard_api(night, tmp_path):
    from hub.server import Session, serve

    async def go():
        server, dash = await serve("127.0.0.1", 0, lambda: Session(scenario.RECORDING if scenario.RECORDING.exists()
                                                                    else scenario.write_night(), speed=4.0))
        port = server.sockets[0].getsockname()[1]

        async def get(path, method="GET"):
            r, w = await asyncio.open_connection("127.0.0.1", port)
            w.write(f"{method} {path} HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n\r\n".encode())
            data = await r.read()
            w.close()
            head, _, body = data.partition(b"\r\n\r\n")
            return int(head.split()[1]), body
        await asyncio.sleep(3)
        st, body = await get("/api/state")
        snap = json.loads(body)
        st2, html = await get("/")
        st3, _ = await get("/../hub/server.py")
        st4, _ = await get("/api/lamp/tap", "POST")
        st5, _ = await get("/api/replay/pause", "POST")
        dash.session.stop()
        server.close()
        return st, snap, st2, html, st3, st4, st5
    st, snap, st2, html, st3, st4, st5 = asyncio.run(go())
    assert st == 200 and snap["mode"] == "replay" and snap["replay"]["scale"] == 20
    assert set(snap["rooms"]) >= {"bedroom", "bathroom", "kitchen", "living", "hall"}
    assert len(snap["routine"]["rooms"]["bedroom"]["baseline"]) == 48
    assert snap["lamp"]["kind"] == "virtual" and snap["rooms"]["bedroom"]["trace"]
    assert st2 == 200 and b"GHOST" in html
    assert st3 == 404 and st4 == 200 and st5 == 200
