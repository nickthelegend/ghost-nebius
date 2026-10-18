import { useEffect, useRef, useState } from "react";
import type { Snapshot } from "../types";
import { channel, eye } from "../util";

const STATE: Record<string, string> = {
  moving: "Moving",
  breathing: "Breathing",
  still: "Still, no breath seen",
  empty: "Empty",
  "no sensor": "No sensor",
  waiting: "Waiting",
};

/** The flat as an XY plot: rooms light with presence, pulse at the measured breathing rate,
 * and HOTARU's bearing swings toward where GHOST is looking. */
export function PlanScreen({ snap, linkedRoom = null }: { snap: Snapshot; linkedRoom?: string | null }) {
  const { plan, rooms: geo, doors } = snap.home;
  const lamp = snap.lamp.state;
  const [lx, ly] = plan.lamp;
  const e = eye(lamp?.eye);
  // Text is sized in screen pixels, not plan units: ~13 px whatever the plan's rendered width.
  const ref = useRef<SVGSVGElement>(null);
  const [px, setPx] = useState(0.2); // plan units per screen pixel
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      // the drawing is letterboxed when the plan is height-capped: use the tighter axis
      if (el.clientWidth && el.clientHeight) setPx(Math.max((plan.w + 4) / el.clientWidth, (plan.h + 4) / el.clientHeight));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [plan.w, plan.h]);
  const tight = px > 0.24; // small plan: room colour alone names the channel
  const fs = { ["--fs-name" as string]: `${Math.min(13 * px, 4.3)}px`, ["--fs-state" as string]: `${Math.min(14 * px, 4.6)}px`, ["--fs-lamp" as string]: `${Math.min(12.5 * px, 4)}px`, ["--lh" as string]: `${Math.min(17 * px, 5.6)}` };
  return (
    <figure className="plan" aria-label="Floor plan with live presence" style={fs}>
      <svg ref={ref} viewBox={`-2 -2 ${plan.w + 4} ${plan.h + 4}`} role="img" aria-labelledby="plan-desc">
        <desc id="plan-desc">
          {Object.entries(snap.rooms)
            .map(([, r]) => `${r.label}: ${STATE[r.state] ?? r.state}${r.bpm ? `, ${r.bpm} breaths per minute` : ""}`)
            .join(". ")}
        </desc>
        <defs>
          <pattern id="grat" width="5" height="5" patternUnits="userSpaceOnUse">
            <path d="M5 0H0V5" fill="none" stroke="var(--grat)" strokeWidth="0.15" />
          </pattern>
        </defs>
        <rect x="-2" y="-2" width={plan.w + 4} height={plan.h + 4} fill="url(#grat)" />
        {Object.entries(geo).map(([name, g]) => {
          if (!g.plan) return null;
          const [x, y, w, h] = g.plan;
          const r = snap.rooms[name];
          const c = channel(name);
          const sensed = g.sensor !== false;
          const followed = snap.followed === name;
          const breath = r?.state === "breathing" && r.bpm ? 60 / r.bpm : 0;
          return (
            <g key={name} className={`room ${r?.present ? "is-present" : ""} ${followed ? "is-followed" : ""} ${linkedRoom === name ? "is-linked" : ""}`} style={{ ["--c" as string]: sensed ? c.color : "var(--scr-ink-3)" }}>
              <rect className="room-floor" x={x} y={y} width={w} height={h} />
              {breath > 0 && <rect className="room-breath" x={x} y={y} width={w} height={h} style={{ animationDuration: `${breath}s` }} />}
              <rect className="room-wall" x={x} y={y} width={w} height={h} />
              {r?.anomaly != null && r.present && r.anomaly >= 0.2 && (
                <circle className="room-anom" cx={x + w - 3.4} cy={y + 8.4} r={0.9 + r.anomaly * 1.6}>
                  <title>{`Routine anomaly ${r.anomaly.toFixed(2)}`}</title>
                </circle>
              )}
              {followed && (
                <path
                  className="room-follow"
                  d={`M${x + 1} ${y + 4}V${y + 1}H${x + 4} M${x + w - 4} ${y + 1}H${x + w - 1}V${y + 4} M${x + w - 1} ${y + h - 4}V${y + h - 1}H${x + w - 4} M${x + 4} ${y + h - 1}H${x + 1}V${y + h - 4}`}
                />
              )}
            </g>
          );
        })}
        {doors?.map(([dx, dy, o], i) => (
          <line key={i} className="door" x1={o === "v" ? dx : dx - 2.6} y1={o === "v" ? dy - 2.6 : dy} x2={o === "v" ? dx : dx + 2.6} y2={o === "v" ? dy + 2.6 : dy} />
        ))}
        {Object.entries(geo).map(([name, g]) => {
          if (!g.plan) return null;
          const [x, y, , h] = g.plan;
          const r = snap.rooms[name];
          const c = channel(name);
          const sensed = g.sensor !== false;
          const stay = r?.present && r.since_min != null && r.since_min >= 1 ? `${Math.round(r.since_min)} min here` : "";
          return (
            <g key={name} className={`room-labels ${r?.present ? "is-present" : ""}`} style={{ ["--c" as string]: sensed ? c.color : "var(--scr-ink-3)" }}>
              <text className="room-name" x={x + 1.8} y={y + 1.6 + Math.min(13 * px, 4.3)}>
                {sensed && !tight ? `CH${c.ch} ${g.label}` : g.label}
              </text>
              {sensed && (
                <text className="room-state" x={x + 1.8} y={y + h - 2}>
                  {stay && <tspan x={x + 1.8} dy={-Math.min(17 * px, 5.6)}>{stay}</tspan>}
                  <tspan x={x + 1.8} dy={stay ? Math.min(17 * px, 5.6) : 0}>
                    {r?.state === "breathing" && r.bpm ? `${r.bpm.toFixed(1)} br/min` : STATE[r?.state ?? "waiting"]}
                  </tspan>
                </text>
              )}
            </g>
          );
        })}
        <g className="hotaru" style={{ ["--eye" as string]: e.color }}>
          <g className="hotaru-bearing" style={{ transform: `rotate(${lamp?.pan ?? 0}deg)`, transformOrigin: `${lx}px ${ly}px` }}>
            <path className="hotaru-cone" d={`M${lx} ${ly} L${lx - 6} ${ly - 22} A23 23 0 0 1 ${lx + 6} ${ly - 22} Z`} />
            <line className="hotaru-ray" x1={lx} y1={ly} x2={lx} y2={ly - 22} />
          </g>
          <circle className="hotaru-ring" cx={lx} cy={ly} r="2.6" />
          <circle className="hotaru-core" cx={lx} cy={ly} r="1.2" />
          <text className="hotaru-label" x={lx + 3.6} y={ly + 1.2 + Math.min(12.5 * px, 4)}>
            HOTARU {lamp?.speaking ? "· speaking" : lamp?.listening ? "· listening" : ""}
          </text>
        </g>
      </svg>
    </figure>
  );
}
