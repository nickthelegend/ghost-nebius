# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript for the hub dashboard (user chose "a framework"; React/Vite was the named example and is the choice). The built output in `web/dist` is committed and served by the stdlib Python hub (`python -m hub.server`), so running the demo never needs npm. The hub itself stays plain Python.

## Users

Primary audience of the dashboard (confirmed): hackathon judges and builders, the Nebius x NVIDIA Global AI Hackathon, Physical AI track. They watch a ≤3 min video or run the replay themselves, and they judge Technological Implementation, Design, Potential Impact and Quality of the Idea, equally weighted. They need to see the sense → reason → act loop working, and be able to check each claim against the measurement.

The end customer the product serves (from the pitch, not this surface's audience): older people living alone and the family or senior-living staff who look after them.

## Product Purpose

GHOST is a camera-less guardian. ESP32 Wi-Fi CSI nodes sense presence, breathing and movement in each room through walls. GHOST learns each room's normal routine from presence alone (no labels), Nemotron on Nebius Token Factory explains anomalies citing numbered sensor evidence, and HOTARU, a robot desk lamp, physically responds: lights a path, turns to the room, asks "Are you okay?", and calls family when nobody answers. Success for this surface: a judge understands the whole loop from one screen and trusts it because every explanation points at the numbers.

## Positioning

Breathing-through-walls sensing alone is prior art (RuView, wifisense-pi, CardioNet, Origin Wireless, IEEE 802.11bf), and RuView also advertises routine learning. GHOST's distinct mechanism is the closed, inspectable loop: alerts whose explanations cite the CSI and the learned routine by evidence id, a rules floor the model can raise but never lower, and an embodied responder that acts in the room. No cameras anywhere.

## Operating Context

- The bundled replay: a synthesized 3 am night (recorded-CSI format, scene time ×20): asleep → gets up → bathroom → possible fall → long stay vs. the learned 4-minute norm → HOTARU checks in → no answer → family alerted. Labelled synthetic until a real night is recorded.
- Live mode with real boards and the real HOTARU over TCP/UDP on the local network.
- Filmed for the demo video; also opened on a laptop by judges. Mobile must work.

## Capabilities and Constraints

- Rooms: bedroom, bathroom, kitchen, living room (HOTARU's own sensor), hall (no sensor). Floor plan geometry in `demo/home.json`.
- Per room: presence, state, breathing rate + confidence, motion index, jolt, a 20 s breathing waveform, learned P(occupied) per half hour, last-24 h occupancy, anomaly score.
- Timeline entries: event, room, severity (none/watch/check_in/alert), floor, explanation with [E#] citations, evidence list (rule/csi/routine/lamp/earlier), what HOTARU said and did, outcome, model or "rules".
- Lamp state: ring mode (path/amber/red/follow…), pan angle, speaking/listening, last line, check-in armed.
- Controls: restart replay, pause/resume, speed, "tap HOTARU's button" (answer the check-in).
- Without a Nebius key the agent runs on rules + templates; the UI must say which.
- Replay never places real calls.

## Brand Commitments

Names: GHOST (the guardian), HOTARU (the lamp, ThenarLabs hardware). No cameras is a core promise. MIT licensed.

## Evidence on Hand

- Synthetic replay and 14 simulated nights of routine (labelled synthetic). No real recorded night yet; no real users, customers, or clinical claims. Do not invent accuracy numbers.
- HOTARU hardware exists (`../hotaru`).

## Product Principles

1. Every claim points at a measurement.
2. The human stays in control: check in before escalating; the model never lowers the rules' floor.
3. No cameras, ever.
4. The loop is the product: sense, reason, act on one screen.

## Accessibility & Inclusion

WCAG AA contrast; severity never conveyed by color alone; reduced-motion respected; works on phone width.
