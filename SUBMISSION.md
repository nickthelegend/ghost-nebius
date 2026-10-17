# GHOST: submission kit

Nebius x NVIDIA Global AI Hackathon · **Physical AI track** · deadline **Fri Oct 30, 2026, 10:00 AM PT**
(Devpost rules §1). Submit on Oct 29. Sources for every rule below are in [RESEARCH.md](RESEARCH.md).

## Devpost description

**Tagline:** A camera-less guardian that senses through walls, explains itself, and gets up to check.

**What it is.** GHOST watches over someone who lives alone without a single camera. Small ESP32
boards, one per room, read the Wi-Fi channel state information that ripples when a chest rises and
falls or someone walks. From that alone GHOST measures breathing, movement and sudden jolts in
every room, through walls.

**What's new.** Breathing over Wi-Fi is prior art (RuView, wifisense-pi, CardioNet, Origin Wireless,
IEEE 802.11bf), and we credit it. GHOST closes the loop around it:

1. **It learns the home's routine with no labels.** For each room, every half hour: how often it
   is occupied, and how long visits last at that time of day. Nobody tells it when Dad sleeps or
   how long a night-time bathroom visit takes; it learns "4 minutes, never more than 5" from two
   weeks of presence.
2. **Nemotron explains, and shows its work.** When a rule fires, Nemotron 3 Ultra on Nebius Token
   Factory gets the event with numbered evidence: the Wi-Fi readings, the learned routine, what the
   lamp heard. Its explanation must cite them ("9 min in the bathroom [E1], visits at this hour
   last 4 min [E6], bedroom empty though occupied 14 of 14 nights [E7]"). Citations to evidence that
   doesn't exist are removed. Tested rules set a severity floor the model can raise but never lower,
   and a check-in always comes before a call.
3. **A body acts.** HOTARU, our robot desk lamp, fades in a path light when someone gets up at night,
   turns to follow them, turns amber and asks "Are you okay?" A word or a tap on its button stands
   it down. Silence turns it red and calls the family.

**How it's built.**
- ESP32 CSI nodes stream over UDP to a Python hub. Breathing comes from PCA over the
  most-modulated subcarriers, band-passed 6–36 breaths/min and read from the quiet stretch after
  any movement. A subcarrier-contrast test keeps empty rooms from "breathing".
- Unsupervised routine model: a per-room occupancy baseline and visit-length statistics, scored
  as presence surprise and a robust dwell z-score.
- Nemotron 3 Ultra reasons about events. Nemotron 3.5 Lightning (thinking off) writes the running
  log.
- HOTARU firmware takes commands over TCP.
- The dashboard is a live instrument panel: floor plan, breathing traces, routine mask test, alert
  captures with cited evidence, and the lamp's output.
- A recorded-CSI format lets the 3 am scene replay end to end with no hardware.
- 47 tests.

**Who it's for.** Older people living alone, their families, and senior-living operators. Cameras
in bedrooms and bathrooms are a non-starter; a lamp that notices is not. Business: $15–30 per
resident per month for senior living.

**Honest limits.**
- The bundled replay and its 14-day history are synthesized from our channel model until we record
  real nights.
- Fall detection is a jolt threshold that needs calibrating per home.
- Wi-Fi sensing can miss a person who is completely still.
- GHOST models one person living alone.

## Video script (≤ 3:00; ≥ 1:00 of hardware operating)

| Time | Picture | Voice-over / on screen |
|---|---|---|
| 0:00–0:15 | A bedroom door, closed. HOTARU on a hall table, its ring breathing slowly. | "There's someone asleep behind this wall. No camera anywhere. Watch the lamp." Caption: *HOTARU's ring follows breathing measured over Wi-Fi.* |
| 0:15–0:45 | **Hardware.** Helper behind the wall breathing to a metronome at 10 → 15 → 20/min; split screen with the dashboard's CH1 trace and the phyphox chest-phone curve. | "Wi-Fi ripples when a chest moves. Each room's ESP32 measures it; the hub reads breathing through the wall." |
| 0:45–1:25 | **Hardware.** Lights off. Helper gets up and walks out; HOTARU fades in the path light and turns to follow, bedroom → bathroom. Dashboard: plan lights the bathroom, Got up / Moved rooms captures. | "At 3 am it notices someone getting up, lights the way, and follows them." |
| 1:25–2:10 | **Hardware.** Helper lies still on the bathroom floor (staged on a mat). HOTARU turns amber and says "Are you okay in there?" Silence. Ring goes red: "I'm calling Priya now." Phone #2 rings. Cut to the dashboard capture with its cited explanation; hover E6. | "It doesn't wait a fixed 20 minutes. It learned that visits here at night take 4 minutes. At 9, still not moving, it checks in. Every claim Nemotron makes points at a measurement." |
| 2:10–2:35 | Dashboard: routine mask test (REF vs LIVE), then a second take where the helper taps HOTARU's button and it stands down with a nod. | "It learned this home's routine from two weeks of presence, no labels. And a human always gets the first word." |
| 2:35–3:00 | Architecture card: ESP32 mesh → hub → Nemotron 3 Ultra on Nebius Token Factory → HOTARU. Then the closing card. | "Camera-less sensing, explained alerts, a body that acts. GHOST: $15–30 per resident per month for senior living." |

Hardware on screen runs 0:15–2:10 (≈1:55), comfortably over the 1-minute rule. If the boards
aren't ready, film HOTARU acting out the recorded night (`python -m hub.server --lamp`) and say so
on screen; the lamp is real hardware.

## Your TODOs

**Hardware (this week)**
- [ ] 2–3 ESP32-S3 boards for sensing nodes (external-antenna u.FL boards are best through walls),
      plus a 5 V USB supply each. Flash `firmware/ghost-node` with `NODE_NAME` = `bedroom` /
      `bathroom`. HOTARU's own CSI covers the living room.
- [ ] Flash HOTARU with the GHOST link (`../hotaru`, `firmware/hotaru/ghost.h`) and set
      `GHOST_HUB_HOST` to the laptop's IP. Keep the servos on their own 5–6 V supply.
- [ ] Copy `rooms.example.json` to `rooms.json` and set each room's `pan` to where HOTARU actually
      faces it. Mark bedrooms `"sleep": true`.
- [ ] Record a real night (`python -m hub.replay record data/replay/night1.ghostcsi`). Optionally
      swap it in for the synthetic one in the video.
- [ ] Calibrate `Config.fall_jolt`: drop a heavy bag onto a mat in the bathroom and walk normally,
      read the jolt values on the dashboard, and set the threshold between them.

**Keys (each one costs money or needs your account; I didn't create or call any)**
- [ ] Nebius Token Factory API key, and redeem the $25 promo (`NEBIUS-DEVPOST-GLOBAL26`) plus the
      Builders Program $25. Then set:
  ```bash
  export NEBIUS_API_KEY=...
  export GHOST_REASON_MODEL=nvidia/Nemotron-3-Ultra-550b-a55b
  export GHOST_LOG_MODEL=nvidia/Nemotron-3_5-Lightning
  ```
- [ ] Run one replay with the key and check the explanations. If Ultra replies slowly or wraps its
      JSON in reasoning text, try `GHOST_REASON_SYSTEM_PREFIX`, or `nvidia/nemotron-3-super-120b-a12b`.
- [ ] Optional: Twilio (the phone actually rings) and a Telegram bot.
- [ ] Optional, for the Serverless story: run the nightly routine refit as a Nebius Serverless Job.
      It is billed at Compute rates; there are no AI Cloud credits.
  ```bash
  nebius ai job create --image <hub image> --container-command python --args "-m hub.routine fit data/live/routine.json"
  ```

**Submission**
- [ ] Push the repo public. Set the MIT licence to show in GitHub's About box (the rules require it).
- [ ] Upload the video to YouTube as public, with no copyrighted music.
- [ ] Devpost: description (above), Physical AI track, video link, repo link.
- [ ] Note that the project started before Aug 26 if it did (the rules ask what changed during the
      submission period).
- [ ] **Feedback section (required; also eligible for Most Valuable Feedback).** Cover:
  - what you used (Token Factory, Nemotron 3 Ultra and Lightning)
  - what worked and what didn't (for example, whether `chat_template_kwargs` or
    `reasoning_effort` controls thinking)
  - onboarding time from zero to first call
  - whether you'd build on it again
- [ ] Optional: attend the "Will It Ship" judging session on Tue Oct 20, 9 AM PT, and a Builders &
      Brews event (City Winner, $500).
