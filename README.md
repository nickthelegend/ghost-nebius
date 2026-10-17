# GHOST

**A camera-less guardian.** ESP32 Wi-Fi nodes sense presence, breathing and movement in every room,
through walls. GHOST learns each room's routine with no labels. Nemotron on Nebius Token Factory
explains anything unusual, citing the sensor evidence by number. HOTARU, a robot desk lamp, then
acts: it lights a path, turns to the room, asks "Are you okay?", and calls family if nobody answers.

Built for the **Nebius x NVIDIA Global AI Hackathon, Physical AI track**. MIT licensed.

```
ESP32 CSI nodes ──UDP──▶ hub: breathing · motion · jolt per room ──▶ rules (severity floor)
   (one per room)              │                                      │
                               ▼                                      ▼
                        routine model (learned,             Nemotron 3 Ultra on Nebius:
                        no labels): P(occupied) per          explains, cites [E1]…[En],
                        half hour, visit lengths             may raise severity, never lower
                                                                      │
HOTARU lamp ◀──TCP── act path: path light · turn to room · ask · listen · call family
```

## Run the demo (no hardware, no keys)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m hub.server        # then open http://127.0.0.1:8780
```

The dashboard replays a recorded 3 am night at scene time ×20 with a virtual HOTARU:
asleep → gets up → bathroom → a jolt then stillness → still there far longer than the learned
4-minute norm → HOTARU checks in → silence → family alerted (dry run: a replay never places real
calls). Press **HOTARU's button** in the dashboard during the check-in to answer it instead.

The bundled night and its 14-day routine are **synthesized** from the same channel model the tests
use, and are labelled that way in the UI, until a real night is recorded with the boards.

## Run it for real

```bash
cp rooms.example.json rooms.json                  # which way HOTARU turns for each room
export NEBIUS_API_KEY=...                         # Nebius Token Factory
export GHOST_REASON_MODEL=nvidia/Nemotron-3-Ultra-550b-a55b
export GHOST_LOG_MODEL=nvidia/Nemotron-3_5-Lightning   # or nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
.venv/bin/python -m hub.server --live             # dashboard + guardian on the real boards
.venv/bin/python -m hub.server --lamp             # the recorded night, acted out by the real HOTARU
.venv/bin/python -m hub.replay record data/replay/my-night.ghostcsi   # record a real night
.venv/bin/python -m hub.server --recording data/replay/my-night.ghostcsi
```

- Sensing nodes: `firmware/ghost-node` (any ESP32 on arduino-esp32 3.x; each node pings the router
  ~100×/s and streams CSI to the hub). HOTARU's GHOST link is `firmware/hotaru/ghost.h` in
  [nickthelegend/hotaru](https://github.com/nickthelegend/hotaru).
- Alerts: Twilio call and Telegram text turn on when their variables are set (`hub/alerts.py`);
  otherwise they're printed.
- Dashboard source is React + Vite in `web/` (`cd web && npm install && npm run build`); the built
  `web/dist` is committed so the demo needs only Python.

## How Nemotron and Nebius are used

| Where | Model / service | What it does |
|---|---|---|
| `hub/agent.py` `Reasoner.decide` | **Nemotron 3 Ultra** on Token Factory | Gets each event, the rule's severity floor and numbered evidence (CSI readings, the learned routine, what HOTARU heard). Returns severity, an explanation that cites `[E#]`, what HOTARU says, and the family message. Citations to evidence that doesn't exist are stripped; the rules' floor always holds; a check-in always comes before a call. |
| `hub/agent.py` `Reasoner.summarize` | **Nemotron 3.5 Lightning** (or Nemotron 3 Nano) | Writes the running log line every few seconds with reasoning switched off (`chat_template_kwargs.enable_thinking=false`, falling back if refused). |
| `python -m hub.routine fit` | Nebius **Serverless Job** (planned) | The nightly refit of the routine model as a batch job over the day's presence. |

Without a key everything still runs on the rules and plain-language templates, and the dashboard
says so ("Rules + templates").

## What's in the hub

| file | |
|---|---|
| `sense.py` | breathing rate, waveform, motion index and jolt from CSI; breathing read from the quiet stretch after movement; a subcarrier-contrast check so empty rooms don't "breathe" |
| `routine.py` | unsupervised per-room routine: occupancy baseline per half hour, visit lengths by time of day, presence surprise and dwell anomaly scores; refit daily on past days only |
| `agent.py` | rules (got up, moved rooms, possible fall, long stay vs. the routine, too still, breathing lost, no answer) and the Nemotron reasoner |
| `evidence.py` | numbered evidence for every event |
| `act.py` | decision → HOTARU plan; a virtual HOTARU |
| `replay.py`, `scenario.py` | `.ghostcsi` recordings, the recorder, the synthesized night |
| `server.py` | the dashboard server (stdlib only) |
| `run.py` | the guardian; `python -m hub.run` runs it headless |

```bash
.venv/bin/python -m pytest -q        # 47 tests: sensing, routine, rules, citations, act path, the whole night
```

## Prior art

Breathing through a wall with Wi-Fi is not new: RuView, wifisense-pi (Hackaday, Aug 2026),
CardioNet, Origin Wireless, Espressif esp-csi and IEEE 802.11bf all sense this way, and RuView also
learns routines. GHOST's contribution is the closed loop: alerts explained with citations to the
measurements, a rules floor the model can't lower, and a body in the room that acts. Sources:
[RESEARCH.md](RESEARCH.md).
