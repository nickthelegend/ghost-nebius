---
name: GHOST
description: A camera-less home guardian rendered as a bench measuring instrument; light chassis, recessed scope screens, four channel colours.
colors:
  chassis: "#d5d6d0"
  chassis-2: "#cacbc4"
  chassis-3: "#bfc1b9"
  plate: "#e3e4de"
  seam: "#b3b5ad"
  seam-2: "#9ea198"
  ink: "#1a1c1b"
  ink-2: "#41443f"
  ink-3: "#5c5f59"
  key: "#ecede8"
  key-2: "#e2e3dd"
  screen: "#0a0e0d"
  screen-2: "#111715"
  screen-3: "#18201d"
  bezel: "#262a28"
  grat: "rgba(170, 205, 188, 0.1)"
  grat-2: "rgba(170, 205, 188, 0.16)"
  scr-ink: "#dde7e1"
  scr-ink-2: "#9bada3"
  scr-ink-3: "#6f8077"
  ch1: "#f3d33b"
  ch2: "#39d0e3"
  ch3: "#ec66d6"
  ch4: "#66d474"
  sev-none: "#9bada3"
  sev-watch: "#ffe3ad"
  sev-check: "#ff9d2e"
  sev-alert: "#ff4d40"
  eye-path: "#ffe3ad"
  eye-follow: "#9fd3ff"
  run: "#33b45a"
  stop: "#e0473a"
  focus-chassis: "#0f7f95"
typography:
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.04em"
  headline:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "23px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "0.02em"
  readout:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.15
    fontFeature: "tnum"
  title:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.16em"
  body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  body-caption:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "12.5px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.12em"
  label-micro:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "10.5px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.12em"
rounded:
  chip: "3px"
  tag: "4px"
  row: "5px"
  inset: "6px"
  key: "7px"
  panel: "10px"
  led: "50%"
spacing:
  hair: "2px"
  xs: "4px"
  sm: "7px"
  md: "10px"
  lg: "14px"
  xl: "18px"
  chassis-x: "22px"
components:
  key:
    backgroundColor: "{colors.key}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.key}"
    padding: "0 13px"
    height: "36px"
  key-small:
    backgroundColor: "{colors.key}"
    textColor: "{colors.ink}"
    rounded: "{rounded.key}"
    padding: "0 10px"
    height: "30px"
  key-on:
    backgroundColor: "#1e2220"
    textColor: "#ffffff"
    rounded: "{rounded.key}"
  key-disabled:
    backgroundColor: "{colors.chassis-2}"
    textColor: "{colors.ink-3}"
  screen:
    backgroundColor: "{colors.screen}"
    textColor: "{colors.scr-ink}"
    rounded: "{rounded.panel}"
  brand-plate:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "12px 16px"
  acquisition-strip:
    backgroundColor: "{colors.chassis-2}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.panel}"
    padding: "10px 14px"
  channel-tag:
    textColor: "{colors.screen}"
    typography: "{typography.label}"
    rounded: "{rounded.chip}"
    padding: "3px 5px 2px"
  severity-lamp-off:
    backgroundColor: "#0d1311"
    textColor: "{colors.scr-ink-3}"
    rounded: "{rounded.row}"
    padding: "6px 4px"
  severity-lamp-watch:
    backgroundColor: "{colors.sev-watch}"
    textColor: "#1d1606"
  severity-lamp-check-in:
    backgroundColor: "{colors.sev-check}"
    textColor: "#231200"
  severity-lamp-alert:
    backgroundColor: "{colors.sev-alert}"
    textColor: "#ffffff"
  cite:
    backgroundColor: "#12201c"
    textColor: "{colors.ch2}"
    rounded: "{rounded.tag}"
    padding: "0 5px"
    height: "19px"
  cite-on:
    backgroundColor: "{colors.ch2}"
    textColor: "{colors.screen}"
---

# Design System: GHOST

## Overview

**Creative North Star: "The Instrument Front Panel"**

GHOST is drawn as a bench measuring instrument for a home: a warm light-grey chassis carrying silk-screened condensed legends, raised grey softkeys, a lit RUN/STOP key and indicator LEDs, with every measurement shown inside recessed near-black screens behind a dark bezel. Inside the screens the world is an oscilloscope: graticules, one channel colour per room (CH1 bedroom, CH2 bathroom, CH3 kitchen, CH4 living room), traces that move at the measured rate, and a trigger panel whose captures cite their evidence.

The two materials never mix roles. The chassis is for identity, controls, labels and status; the screens are for data. Density is high and deliberate, like a real front panel: small condensed uppercase legends, tabular numbers everywhere, and the large readouts reserved for the few values that matter (scene clock, breathing rate, capture title). The build rejects the category's dark card-grid monitoring dashboard: there are no free-floating cards, only screens mounted in a chassis.

**Key Characteristics:**
- Light chassis outside, near-black recessed screens inside; nothing else.
- Four fixed scope channel colours, each bound to one room, used on every surface that names that room.
- A separate severity scale (watch / check-in / alert) that is never confused with channel colour and never conveyed by colour alone.
- Condensed uppercase legends with wide tracking; tabular numerals globally.
- Physical depth: raised keys, recessed screens, glass sheen, lamp windows.

## Colors

A neutral warm-grey hardware palette carrying two independent signal vocabularies: scope channel colours (which room) and severity lamps (how serious).

### Primary
- **Bench Chassis Grey** (chassis): the page itself and the instrument body; its siblings (chassis-2 for the recessed acquisition strip and disabled keys, chassis-3 reserve) step it down for wells.
- **Scope Black** (screen): every data display; screen-2 for the trigger state band and capture list footer, screen-3 for spoken-line and voice wells; bezel is the 6px frame around each screen.

### Secondary: scope channels
- **CH1 Trace Yellow** (ch1): bedroom.
- **CH2 Trace Cyan** (ch2): bathroom. Also the system's interactive accent inside screens: citation chips, the acquisition playhead and fill, the focus ring on screen, listening state, and the logo trace.
- **CH3 Trace Magenta** (ch3): kitchen.
- **CH4 Trace Green** (ch4): living room.

### Tertiary: severity and lamps
- **Watch Pale Amber** (sev-watch): lowest severity lamp and ticks. On the light chassis it is too pale, so watch markers on the acquisition strip use a deep ochre (#7d5f17) instead.
- **Check-in Orange** (sev-check): middle severity; also "hot" readouts (motion, jolt, anomaly over threshold), routine-anomaly rings on the plan, and the trigger flash.
- **Alert Red** (sev-alert): top severity, violation marks on the routine mask, "To family" label. Its pulse dips to #b8281e.
- **Clear Grey** (sev-none): no-severity rows.
- **HOTARU ring colours**: eye-path (warm path light, also quoted speech) and eye-follow (cool breathing-follow blue, also Wi-Fi evidence source); amber and red ring states reuse sev-check and sev-alert.
- **RUN green / STOP red** (run, stop): only inside the RUN/STOP lamp window and LED gradients.

### Neutral
- **Ink ramp** (ink, ink-2, ink-3): text on the chassis: legends, secondary values, disabled.
- **Screen ink ramp** (scr-ink, scr-ink-2, scr-ink-3): text in screens: primary, secondary, dim legends. Pure white is reserved for capture titles, the "now" line and the followed-room corner brackets.
- **Graticule** (grat, grat-2): 10–16% green-grey grid lines in the plan, traces and mask.
- **Seams** (seam, seam-2): 1px borders on plate, strip and keys.

### Named Rules
**The Channel Ownership Rule.** A room's channel colour appears wherever that room is named (plan outline, trace, CH tag, mask row, dial dot, capture room label). No other element may use CH1–CH4 hues, with the one sanctioned exception that CH2 cyan is the in-screen interaction accent.

**The Two Scales Rule.** Channel colour says *where*; severity colour says *how serious*. A severity is always paired with its word (WATCH, CHECK-IN, ALERT) or its position in the three-lamp bank.

**The Materials Rule.** Chassis colours never appear inside a screen and screen colours never become a page background. Data lives behind glass.

## Typography

**Display / Label Font:** Barlow Condensed (with Arial Narrow), weights 500/600/700, self-hosted via @fontsource.
**Body Font:** Barlow (with system-ui), weights 400/500/600.
**Mono:** ui-monospace only for inline `code` in the boot message.

**Character:** Condensed, widely tracked uppercase legends read as silk-screen printing on hardware; Barlow body keeps explanations and evidence readable at small sizes. `font-variant-numeric: tabular-nums` is set on body so every readout holds its column.

### Hierarchy
- **Display** (600, 32px, 1): the scene clock in its own small screen on the brand plate. The wordmark GHOST is 700 26px at 0.2em tracking.
- **Headline** (600, 23px, 1.1): capture title in the trigger screen, white.
- **Readout** (600, 24px, 1.15): primary numeric values (breathing rate) in the channel colour; secondary readouts 600 19px (HOTARU ring, bearing, doing).
- **Title** (700, 15px, 0.16em, uppercase): module legends ("PLAN", "TRIGGER") on the chassis above each screen, followed by a 500 13.5px sentence-case sub-legend in ink-2.
- **Body** (400, 15px/1.5): default; capture explanation text is 16px/1.55 capped at 64ch; evidence, logs, notes and command lines 14–14.5px.
- **Label** (600, 12.5px, 0.12–0.14em, uppercase): lamp names, severity badges, room names, step chains, key text (13.5px, 0.1em).
- **Label micro** (600, 12–12.5px, 0.12em, uppercase): readout `dt` legends, axis scales, evidence source.

**The Projection Floor.** Nothing a viewer must read is under 12px (labels) or 14px (sentences), because the dashboard is filmed and projected. Plan SVG text is sized in screen pixels (~13–14px) from the plan's rendered scale, not in plan units; when the plan is small, room names drop the CH prefix and rely on the room colour.

### Named Rules
**The Silk-Screen Rule.** Every legend, key, lamp and axis label is Barlow Condensed uppercase with 0.06–0.2em tracking; running sentences (captions, evidence, notes) are Barlow sentence case. Never set a paragraph in the condensed face or a legend in the body face.

## Layout

- **Chassis:** a single centred column, max 1840px, padding 18px 22px 28px, 14px gap between stacked rows. Order: brand plate, acquisition strip, bench, footer.
- **Brand plate:** three-column grid (mark | centred SENSE/REASON/ACT lamps | clock screen), 22px gap.
- **Acquisition strip:** keys at left, then a track of TRUTH lane / 14px timeline screen / GHOST lane / time scale, with a 64px label column. Mark labels are spread over 2–4 lanes so neighbours never overprint; labels near the right edge flip to grow leftward.
- **Bench:** two independent column stacks (at ≥1600px Plan and Breathing sit side by side inside the sensing stack so the whole loop fits one 1080p view), `minmax(0, 1.5fr)` sensing (Plan, Breathing, then Routine, Log) and `minmax(360px, 1fr)` decision (Trigger, HOTARU) spanning both rows. Each module is a legend above a screen with a 7px gap.
- **Inside screens:** 12–14px padding; row grids share a fixed label column (96px) so CH tags align across Breathing and Routine; readouts sit in a fixed right column (200px traces, 140px mask).
- **Responsive:** at ≤1100px the plate lamps drop to a second row and the acquisition strip stacks. At ≤860px the bench becomes one column reordered Trigger, Plan, Breathing, HOTARU, Routine, Log; chassis padding 12px; label column 66px; one trace readout hidden; evidence shows only cited items behind a "Show all evidence" key and loses its scroll fade; plan SVG text scales up. At ≤420px the clock screen spans the full plate width.

## Elevation & Depth

Depth is physical and bidirectional: controls and plates are raised, data is recessed. There is no floating card shadow.

### Shadow Vocabulary
- **Raised key** (`0 1px 0 rgba(255,255,255,.9) inset, 0 2px 3px rgba(30,34,30,.22)`): softkeys at rest; pressed drops to `0 1px 1px` and translates 1px down.
- **Plate** (`0 1px 0 rgba(255,255,255,.75) inset, 0 1px 3px rgba(40,44,38,.12)`): brand plate.
- **Recessed well** (`inset 0 1px 2px rgba(30,34,30,.12)`): acquisition strip on the chassis.
- **Mounted screen** (`0 1px 0 rgba(255,255,255,.7), 0 3px 8px rgba(30,34,30,.22), inset 0 2px 10px rgba(0,0,0,.7)`) plus a 6px bezel and a 160° 4.5% white glass sheen overlay.
- **Small screen inset** (`inset 0 2px 5px rgba(0,0,0,.6)`): clock and timeline screens.
- **LED / lamp window** (`inset 0 1px 2px rgba(0,0,0,.45–.5)`, lit with a radial-gradient highlight at 35% 32%).

### Named Rules
**The Glass Rule.** Anything showing data sits behind a recessed screen; anything you press stands proud of the chassis.

## Shapes

Gently rounded hardware: panels and screens 10px, inset wells 6px, keys 7px, rows and lamps 5px, badges and cite chips 4px, channel tags 3px, LEDs and HOTARU eye dots fully round. Timeline marks are 8px rounded squares for GHOST captures and hollow 1.5px rings for ground truth; routine violations are 45°-rotated squares. Hairline dividers inside screens are 1px near-black-green.

## Components

### Softkeys
- **Shape:** 7px radius, 1px seam-2 border, vertical gradient key → key-2, 36px tall (30px small).
- **Text:** condensed 600 13.5px uppercase at 0.1em; optional 15px Lucide icon at 7px gap.
- **States:** hover lightens the top of the gradient (#f5f6f2); active presses 1px down; selected (`is-on`, e.g. 4×) inverts to a black key with white legend; disabled flattens to chassis-2 with ink-3 text (inside a screen: #151c19 with scr-ink-3).
- **RUN/STOP:** carries a 12px lamp window: green radial glow while running, red while stopped.
- **HOTARU tap key:** full-width 42px, sentence case 15px; when a check-in is armed it turns amber (#ffd27f → #ffb547) and pulses a 4px halo.

### Severity lamp bank
Three equal lamps (WATCH, CHECK-IN, ALERT) on screen-2. Unlit lamps are dark with dim legends; the current severity and everything below it light in their colour; the ALERT lamp pulses only when it is the current state. Beneath it, a status line: bold condensed state word plus a plain sentence.

### Capture readout
Number (#05), white headline, room label in its channel colour, time right-aligned; a filled or outlined severity badge with the provenance ("Rules + template" or "Nemotron · model"); the explanation with inline citation chips (E1…) in CH2 cyan that fill on hover/focus and highlight the matching evidence row; an OUTCOME line; quoted speech in a screen-3 well in path-light amber; evidence rows (id | source | text) where cited ids turn cyan.

### Trace row
Channel tag (CH n on its colour, screen-black text) and room name; a canvas trace in the channel colour at 1.7px over a 10-division graticule; readouts (breathing large in channel colour, CONF / MOTION / JOLT micro-labelled). A room that is not breathing draws its trace at 42% opacity.

### Plan (XY) screen
Rooms as channel-coloured outlines on a 5-unit graticule; present rooms fill to 16% and brighten their wall; breathing rooms pulse at the measured breath period; the followed room gets white corner brackets; HOTARU is a ring with a dashed bearing ray and 13% cone in its eye colour, turning over 1.1s.

### Sense → reason → act strip
Every capture opens with three joined cells (SENSE: the channel tag and the one measurement that fired; REASON: rules or Nemotron, the severity and how many evidence items it cites; ACT: what HOTARU did). The strip wears the capture's severity: a 1px border and keys in that colour over a 6% tint, cells divided by 1px seams with a small chevron joint. On phones the cells stack and the joint points down.

### The chain highlight
When a capture fires, for 3.6s the Plan, Breathing, Trigger and HOTARU screens take a 3px ring in the capture's severity colour, their legends gain a matching square, the room's wall turns that colour and its floor pulses twice, and the room's trace row is outlined and tinted. It is the only cross-module animation.

### Armed panel
Before any capture the Trigger screen is not empty: an "Armed" headline, one row per sensed room (channel tag, state, AS USUAL in CH4 green or UNUSUAL in amber against the learned routine), the rules it is waiting for with their severity dots, and on a replay a full-width "Jump to 03:02" key. HOTARU's ring starts in follow mode, so its panel reads "Breathing with bedroom" rather than idle.

### Brand plate, LEDs, acquisition strip, routine mask, HOTARU dial
LEDs are 10px domed circles (green good, amber warn, grey off) with condensed label and Barlow value. The acquisition timeline is a cyan-filled scope strip with a 2px CH2 playhead and severity ticks. The routine mask draws learned occupancy as a 20% channel-colour area, today as solid channel bars, violations as red diamonds above, and "now" as a white line. The HOTARU dial is a 180° arc with 30° ticks, room dots in channel colour, and a needle and ring in the current eye colour.

### Motion
One easing, `cubic-bezier(0.16, 1, 0.3, 1)`: keys 120ms, row/cite highlights 150ms, lamps 200ms, room presence 600ms, trigger flash ring 700ms on a new capture, HOTARU bearing and needle 1.1s. Loops exist only where they mean something: breath pulse at the real rate, alert lamp 1.6s, listening 1.2s, armed tap key 1.4s. `prefers-reduced-motion` removes all animation and the trace draws without its scroll lag.

## Do's and Don'ts

### Do:
- **Do** mount every new data view as a legend-over-screen module with the 6px bezel, inset shadow and glass sheen.
- **Do** colour a room by its channel (CH1 #f3d33b, CH2 #39d0e3, CH3 #ec66d6, CH4 #66d474) on every surface that names it.
- **Do** pair every severity colour with its word or lamp position.
- **Do** set legends in Barlow Condensed uppercase with tracking, numbers tabular, and use the large readout size only for the one value each module exists to show.
- **Do** keep controls as raised softkeys on the chassis; selected state inverts to a black key.
- **Do** tie looping motion to a measured or live state, and honour reduced motion.

### Don't:
- **Don't** build a dark page of floating cards; the page is the light chassis.
- **Don't** use a channel hue for severity, decoration or a non-room meaning (CH2 cyan as the in-screen interaction accent is the only exception).
- **Don't** put chassis greys inside a screen, or use screen blacks as a chassis surface (small display windows, the logo mark and the selected-key inversion are the only dark elements on the chassis).
- **Don't** set running prose in the condensed face or legends in sentence-case body type.
- **Don't** introduce a second easing curve or decorative ambient animation.
