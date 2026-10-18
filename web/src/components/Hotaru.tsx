import { Hand, Mic, Volume2 } from "lucide-react";
import type { Snapshot } from "../types";
import { channel, eye, stepText } from "../util";

/** HOTARU's output: ring colour, where it's turned, what it's saying, and its button. */
export function Hotaru({ snap, act }: { snap: Snapshot; act: (p: string) => void }) {
  const l = snap.lamp;
  const s = l.state;
  const e = eye(s?.eye);
  const pan = s?.pan ?? 0;
  const rooms = Object.entries(snap.rooms).filter(([, r]) => r.pan != null);
  const canTap = l.kind === "virtual" && !!s?.checkin;
  const P = (deg: number, r: number) => {
    const a = ((deg - 90) * Math.PI) / 180;
    return [50 + r * Math.cos(a), 54 + r * Math.sin(a)];
  };
  return (
    <div className="hotaru-mod">
      <div className="dial-wrap">
        <svg viewBox="-14 2 128 60" className="dial" role="img" aria-label={`HOTARU turned to ${pan} degrees, ring ${e.label}`}>
          <path d={`M${P(-90, 40).join(" ")} A40 40 0 0 1 ${P(90, 40).join(" ")}`} className="dial-arc" />
          {[-90, -60, -30, 0, 30, 60, 90].map((d) => {
            const [x1, y1] = P(d, 40), [x2, y2] = P(d, 36);
            return <line key={d} x1={x1} y1={y1} x2={x2} y2={y2} className="dial-tick" />;
          })}
          {rooms.map(([n, r]) => {
            const side = r.pan! <= -45 ? "end" : r.pan! >= 45 ? "start" : "middle";
            const [x, y] = P(r.pan!, side === "middle" ? 46 : 44);
            const [tx, ty] = P(r.pan!, 40);
            return (
              <g key={n} style={{ ["--c" as string]: channel(n).color }}>
                <circle cx={tx} cy={ty} r="1.6" className="dial-room" />
                <text x={side === "end" ? x - 1 : side === "start" ? x + 1 : x} y={side === "middle" ? y : y + 1.4} className="dial-label" textAnchor={side}>{r.label.split(" ")[0]}</text>
              </g>
            );
          })}
          <g className="dial-needle" style={{ transform: `rotate(${pan}deg)`, transformOrigin: "50px 54px", ["--eye" as string]: e.color }}>
            <line x1="50" y1="54" x2="50" y2="18" />
          </g>
          <circle cx="50" cy="54" r="6.5" className="dial-ring" style={{ ["--eye" as string]: e.color }} />
          <circle cx="50" cy="54" r="3" className="dial-hub" />
        </svg>
        <dl className="hotaru-read">
          <div><dt>Ring</dt><dd><span className="eye-dot" style={{ background: e.color }} aria-hidden="true" />{e.label}</dd></div>
          <div><dt>Turned</dt><dd>{pan > 0 ? "+" : ""}{pan}°</dd></div>
          <div><dt>Doing</dt><dd>{s?.speaking ? "Speaking" : s?.listening ? "Listening" : s?.checkin ? "Waiting for a tap" : s?.action ? s.action : s?.eye === "follow" ? `Breathing with ${snap.followed ? snap.rooms[snap.followed]?.label.toLowerCase() ?? "the room" : "the room"}` : "Standing by"}</dd></div>
        </dl>
      </div>
      <div className={`voice ${s?.speaking ? "is-speaking" : ""} ${s?.listening ? "is-listening" : ""}`}>
        {s?.listening ? <Mic size={16} aria-hidden="true" /> : <Volume2 size={16} aria-hidden="true" />}
        <p>
          {s?.said ? <>“{s.said}”</> : <span className="dim">Quiet. HOTARU speaks only when something needs a person.</span>}
          {s?.heard && <span className="voice-heard">Heard: {s.heard}</span>}
        </p>
      </div>
      <button className="key key-tap" disabled={!canTap} onClick={() => act("lamp/tap")}>
        <Hand size={16} aria-hidden="true" />
        <span>{canTap ? "Tap HOTARU's button: I'm OK" : l.kind === "virtual" ? "HOTARU's button (arms on a check-in)" : "Tap the real HOTARU's button"}</span>
      </button>
      <ol className="cmd-log" aria-label="Commands sent to HOTARU">
        {l.recent.slice(-6).reverse().map((c, i) => (
          <li key={i}><time>{c.clock}</time><span>{stepText(c)}</span>{c.op === "say" && <em>“{String(c.text).slice(0, 48)}{String(c.text).length > 48 ? "…" : ""}”</em>}</li>
        ))}
        {!l.recent.length && <li className="dim">No commands yet: HOTARU follows the breathing until something happens.</li>}
      </ol>
    </div>
  );
}
