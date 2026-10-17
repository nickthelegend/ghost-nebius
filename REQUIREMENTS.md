# GHOST — what we need

Due **Fri Oct 30, 2026, 10:00 AM PT** (Devpost rules §1; aim to submit Oct 29) (Nebius x NVIDIA Global AI Hackathon, Physical AI track).

## Hardware

| Item | Have? | Notes |
|---|---|---|
| Hotaru lamp | ✅ | ESP32-S3, 4× MG996R, 12-LED WS2812 ring, INMP441 mic, MAX98357A + speaker, MX button. Nothing to add for the demo. |
| ESP32 boards ×3 | ? | 1 transmitter + 2 listeners. **ESP32-S3 with an external-antenna (u.FL/IPEX) connector + 2.4 GHz antenna** is best for through-wall work. Plain ESP32-S3 dev boards also work. |
| 5 V USB power for each board | ? | Phone chargers + USB-C cables. |
| Phone #1 | ✅ | Strapped to the chest running **phyphox** (accelerometer) → ground-truth breathing curve. |
| Phone #2 | ✅ | Receives the "Calling your daughter" call in the demo. |
| A helper | ? | Someone sits behind the wall while you film (or you sit there and the camera films). |

**Optional Hotaru upgrade:** the WS2812 ring is the eye, so it's dim for a real path light. A second
ring or a warm 1 W LED inside the cone makes the "night path light" read better on camera.
Not required.

**Power check:** four MG996R servos can draw ~2.5 A each at stall. Keep them on their own 5–6 V
supply, not the ESP32's USB rail, or the board browns out mid-demo.

## Firmware (we write this)

1. **CSI listener firmware** (ESP-IDF + Espressif `esp-csi`) on the 2 listener boards → streams
   CSI over UDP to the hub at ~100 Hz.
2. **Transmitter firmware** on 1 board → sends packets at ~100 Hz.
3. **Hotaru WiFi module**: Hotaru's firmware has motion/LED/audio/input but **no WiFi yet**. We
   add a WebSocket client that takes commands from the hub:
   `pose(name)` · `pan(deg)` · `ring(mode, color)` · `say(audio stream)` · `listen(seconds)` ·
   button events up.

## Software (we write this)

- **Hub** (laptop, Python): CSI ingest → filtering → breathing band (6–36 breaths/min) +
  presence + motion + fall pattern.
- **Routine model**: hourly per-room features → learns "normal" with no labels → anomaly score.
- **Agent**:
  - **Nemotron Nano** writes a running log from the signal.
  - **Nemotron Ultra** reasons about anomalies and picks an action: none / path light / check-in /
    call family. A human always confirms escalations.
- **Voice**: NVIDIA open models keep it all-NVIDIA. **Magpie/Riva TTS** for Hotaru's voice
  and **Parakeet ASR** for the reply. Fallback: macOS `say` + Whisper.
- **Alerts**: Twilio voice call (the phone rings) + Telegram/WhatsApp message.
- **Dashboard**: live waveform per room, breathing rate, routine timeline, agent's reasoning log.

## Accounts / keys you need to create

| Service | Why | Cost |
|---|---|---|
| Nebius (Token Factory + AI Cloud) | Nemotron models (required), Serverless Jobs for nightly retraining, Serverless Endpoint for the agent | Free credits on signup / hackathon |
| Twilio | Places the real phone call | Trial credit; trial can call your verified number |
| Telegram bot (BotFather) | Free text alerts | Free |
| Devpost registration for the Nebius hackathon | Submission | Free |

## Submission checklist (from the rules)

- [ ] Uses Nebius Token Factory / AI Cloud **and** at least one NVIDIA open model (Nemotron)
- [ ] Demo video ≤ 3 min on YouTube, with **≥ 1 min of the hardware actually operating**
- [ ] Public repo with an OSS license visible at the top (MIT ✅) and a README with setup steps
- [ ] README explains Nemotron / Token Factory / Nebius services usage
- [ ] Feedback on Token Factory, AI Cloud and NVIDIA tools (also eligible for "Most Valuable
      Feedback", $100 × 10)
- [ ] Track: Physical AI
- [ ] Optional: attended a Builders & Brews city event → City Winner Award ($500)

## Demo script (3 min)

1. **0:00–0:20.** Hook: a wall, no cameras. "There's a person behind this wall. Watch the lamp."
   Hotaru's ring pulses with their breathing.
2. **0:20–1:10.** Proof: the helper breathes to a metronome at 10 → 15 → 20 breaths/min. The
   dashboard tracks each change, overlaid on the phyphox chest-phone curve.
3. **1:10–2:20.** The 3 am story:
   - Someone gets up → Hotaru fades in the path light.
   - No movement for too long → ring turns amber → Hotaru turns to the room → "Are you okay?"
   - Silence → ring turns red → "Calling your daughter" → phone #2 rings.
4. **2:20–3:00.** How it works: ESP32 mesh → Nemotron on Nebius → Hotaru. The business pitch:
   $15–30 per resident per month for senior living, no cameras anywhere.

## Prior art we must acknowledge (and how we differ)

RuView, WiFi Sense (Hackaday, Aug 2026), CardioNet (Devpost) and Origin Wireless already
detect breathing via WiFi. We don't claim that's new. Ours is new because it closes the loop:
unsupervised routine learning across rooms → Nemotron explains *why* something is unusual →
a physical robot responds, and a human stays in control.
