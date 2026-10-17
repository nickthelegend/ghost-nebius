import { useEffect, useState } from "react";
import { Gauge, RotateCcw } from "lucide-react";
import type { Snapshot } from "../types";
import { EVENT_LABEL, SEV_LABEL } from "../util";

/** Spread labelled marks over two lanes so neighbours don't print over each other. */
function lanes(xs: number[], gap = 9, n = 2): { lane: number; label: boolean }[] {
  const last = Array(n).fill(-1e9);
  return xs.map((x) => {
    const lane = last.findIndex((l) => x - l >= gap);
    if (lane >= 0) last[lane] = x;
    return { lane: Math.max(0, lane), label: lane >= 0 };
  });
}

function useNarrow(q = "(max-width: 860px)") {
  const [m, setM] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [q]);
  return m;
}

export function Acquisition({ snap, act, onPick }: { snap: Snapshot; act: (p: string) => void; onPick: (id: number) => void }) {
  const r = snap.replay;
  const narrow = useNarrow();
  if (!r) {
    return (
      <section className="acq acq-live" aria-label="Acquisition">
        <span className="led led-good" aria-hidden="true" /> Live: acquiring from the boards. Captures appear as GHOST triggers.
      </section>
    );
  }
  const span = r.end - r.start;
  const pct = (t: number) => Math.min(100, Math.max(0, ((t - r.start) / span) * 100));
  const x = (t: number) => `${pct(t)}%`;
  const gap = narrow ? 26 : 9;
  const truthLanes = lanes(r.markers.map((m) => pct(r.start + m.t * r.scale)), gap, narrow ? 3 : 2);
  const caps = snap.timeline.filter((c) => c.event !== "answered");
  const capLanes = lanes(caps.map((c) => pct(c.t)), gap, narrow ? 4 : 3);
  const end = (t: number) => (pct(t) > (narrow ? 70 : 86) ? "at-end" : "");
  const head = r.start + r.pos * r.scale;
  const running = !r.paused && !r.done;
  return (
    <section className="acq" aria-label="Replay of the recorded night">
      <div className="acq-keys">
        <button
          className={`key key-run ${running ? "is-run" : "is-stop"}`}
          onClick={() => act(r.done ? "replay/restart" : r.paused ? "replay/resume" : "replay/pause")}
          aria-label={running ? "Stop the replay" : r.done ? "Run the night again" : "Run the replay"}
        >
          <span className="key-window" aria-hidden="true" />
          <span>Run/Stop</span>
          <span className="sr-only">{running ? "(running)" : r.done ? "(finished)" : "(stopped)"}</span>
        </button>
        <button className="key" onClick={() => act("replay/restart")} aria-label="Restart the night from 02:50">
          <RotateCcw size={15} />
          <span>Restart</span>
        </button>
        <div className="speed" role="group" aria-label="Replay speed">
          <Gauge size={15} aria-hidden="true" />
          {[1, 2, 4].map((s) => (
            <button key={s} className={`key key-s ${r.speed === s ? "is-on" : ""}`} aria-pressed={r.speed === s} onClick={() => act(`replay/speed?x=${s}`)}>
              {s}×
            </button>
          ))}
        </div>
      </div>
      <div className="acq-track">
        <div className="acq-row acq-truth" aria-label="What really happened (GHOST never sees this)">
          <span className="acq-row-label">Truth</span>
          <div className={`acq-lane lanes-${1 + Math.max(0, ...truthLanes.map((l) => l.lane))}`}>
            {r.markers.map((m, i) => (
              <span key={m.t} className={`acq-mark truth lane-${truthLanes[i].lane} ${end(r.start + m.t * r.scale)}`} style={{ left: x(r.start + m.t * r.scale) }} title={m.label}>
                <i aria-hidden="true" />
                {truthLanes[i].label && <span>{m.label.split(",")[0]}</span>}
              </span>
            ))}
          </div>
        </div>
        <div className="acq-screen" aria-hidden="true">
          <div className="acq-fill" style={{ width: x(head) }} />
          <div className="acq-head" style={{ left: x(head) }} />
          {snap.timeline.map((c) => (
            <span key={c.id} className={`acq-tick sev-${c.severity}`} style={{ left: x(c.t) }} />
          ))}
        </div>
        <div className="acq-row acq-ghost" aria-label="What GHOST triggered on">
          <span className="acq-row-label">GHOST</span>
          <div className={`acq-lane lanes-${1 + Math.max(0, ...capLanes.map((l) => l.lane))}`}>
            {caps.map((c, i) => (
              <button
                key={c.id}
                className={`acq-mark acq-cap sev-${c.severity} lane-${capLanes[i].lane} ${capLanes[i].label ? "" : "no-label"} ${end(c.t)}`}
                style={{ left: x(c.t) }}
                onClick={() => onPick(c.id)}
                title={`${c.clock} ${EVENT_LABEL[c.event] ?? c.event}: ${SEV_LABEL[c.severity]}`}
              >
                <i aria-hidden="true" />
                <span>{EVENT_LABEL[c.event] ?? c.event}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="acq-scale" aria-hidden="true">
          <span>{new Date(r.start * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
          <span>{new Date(r.end * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
        </div>
      </div>
    </section>
  );
}
