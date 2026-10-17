# GHOST hub

Runs on a laptop or server on the same network as HOTARU.

| file | |
|---|---|
| `lamp.py` | TCP server the lamp connects to (8770), CSI over UDP (8771), async lamp API (`say`, `listen`, `ask`, `eye`, `look`, `action`) |
| `sense.py` | breathing rate, live breathing waveform and motion index from Wi-Fi CSI |
| `alerts.py` | phone call (Twilio) and text (Telegram); printed when not configured |
| `agent.py` | the guardian: tested rules set a severity floor (got up / too still / breathing lost / no answer); Nemotron on Nebius explains and words it, never below the floor |
| `run.py` | GHOST live: per-room sensors, rules, Nemotron, and HOTARU acting (`--demo` compresses the timings) |
| `demo_3am.py` | the night scene for filming, one step per Enter or `--auto` |
| `fake_lamp.py` | a stand-in HOTARU that speaks the protocol and streams synthetic CSI with a known breathing rate |
| `routine.py` | unsupervised per-room routine (occupancy per half hour, visit lengths) and anomaly scores; `python -m hub.routine fit <file>` |
| `evidence.py` | numbered evidence (CSI, routine, lamp, earlier events) that explanations cite |
| `act.py` | decision → HOTARU plan, `VirtualLamp`, `VirtualHub` |
| `replay.py` | `.ghostcsi` recordings: `record`, `info`, and the replay driver |
| `scenario.py` | the synthesized 3 am night and its 14-day routine (`python -m hub.scenario`) |
| `server.py` | the dashboard (`python -m hub.server`, http://127.0.0.1:8780) |

Sensing nodes (extra ESP32s, one per room): `firmware/ghost-node`, same CSI format as HOTARU,
announcing their room name. Copy `rooms.example.json` to `rooms.json` to tell HOTARU which way each
room is and which rooms are for sleeping.

```bash
NEBIUS_API_KEY=... GHOST_REASON_MODEL=<nemotron ultra id> GHOST_LOG_MODEL=<nemotron nano id> python -m hub.run --demo
python -m hub.demo_3am            # then power up HOTARU with GHOST_HUB_HOST = this machine's IP
python -m hub.fake_lamp --bpm 15  # or test without the lamp
pytest -q
```

Lamp firmware and protocol: `firmware/hotaru/ghost.h` in [hotaru](https://github.com/nickthelegend/hotaru).
