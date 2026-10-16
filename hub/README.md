# GHOST hub

Runs on a laptop or server on the same network as HOTARU.

| file | |
|---|---|
| `lamp.py` | TCP server the lamp connects to (8770), CSI over UDP (8771), async lamp API (`say`, `listen`, `ask`, `eye`, `look`, `action`) |
| `sense.py` | breathing rate, live breathing waveform and motion index from Wi-Fi CSI |
| `alerts.py` | phone call (Twilio) and text (Telegram); printed when not configured |
| `demo_3am.py` | the night scene for filming, one step per Enter or `--auto` |
| `fake_lamp.py` | a stand-in HOTARU that speaks the protocol and streams synthetic CSI with a known breathing rate |

```bash
python -m hub.demo_3am            # then power up HOTARU with GHOST_HUB_HOST = this machine's IP
python -m hub.fake_lamp --bpm 15  # or test without the lamp
pytest -q
```

Lamp firmware and protocol: `firmware/hotaru/ghost.h` in [hotaru](https://github.com/nickthelegend/hotaru).
