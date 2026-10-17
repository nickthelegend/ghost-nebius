import type { Snapshot } from "../types";
import { channel } from "../util";

/** The learned routine as a mask test: REF = P(occupied) per half hour, learned with no labels;
 * LIVE = the last 24 hours. Marks flag where today broke the mask. */
export function Mask({ snap }: { snap: Snapshot }) {
  const R = snap.routine;
  if (!R) return <p className="dim pad">No routine yet: GHOST needs a few days of presence before it knows what normal is.</p>;
  const bins = R.rooms[Object.keys(R.rooms)[0]]?.baseline.length ?? 48;
  const order = Array.from({ length: bins }, (_, k) => (R.now_bin + 1 + k) % bins); // oldest -> now
  const W = 2, H = 13;
  const hours = order
    .map((b, i) => ({ i, h: (b * R.bin_minutes) / 60 }))
    .filter(({ h }) => Number.isInteger(h) && h % 6 === 0);
  return (
    <div className="mask">
      <p className="mask-note">Learned from {R.days} days of presence alone, no labels. <span className="key-ref">REF</span> how often each room is occupied in each half hour; <span className="key-live">LIVE</span> the last 24 h; <span className="key-viol">marks</span> where today left the learned pattern.</p>
      {Object.entries(R.rooms).map(([room, m]) => {
        const c = channel(room);
        const v = snap.rooms[room];
        let ref = `M0 ${H}`;
        order.forEach((b, i) => { const y = H - m.baseline[b] * (H - 1); ref += ` L${i * W} ${y} L${(i + 1) * W} ${y}`; });
        ref += ` L${bins * W} ${H} Z`;
        return (
          <div className="mask-row" key={room} style={{ ["--c" as string]: c.color }}>
            <div className="mask-id">
              <span className="trace-ch">CH{c.ch}</span>
              <span>{v?.label ?? room}</span>
            </div>
            <svg viewBox={`0 -2 ${bins * W} ${H + 2}`} preserveAspectRatio="none" className="mask-svg" role="img"
              aria-label={`${v?.label ?? room}: learned occupancy versus the last 24 hours`}>
              {[0.25, 0.5, 0.75].map((f) => <line key={f} x1={0} x2={bins * W} y1={H * f} y2={H * f} className="mask-grat" />)}
              <path d={ref} className="mask-ref" />
              {order.map((b, i) => {
                const t = m.today[b];
                if (t == null) return null;
                const viol = (t > 0 && m.baseline[b] < 0.15) || (t === 0 && m.baseline[b] > 0.85);
                return (
                  <g key={i}>
                    {t > 0 && <rect x={i * W + 0.35} width={W - 0.7} y={H - t * (H - 1)} height={t * (H - 1)} className="mask-live" />}
                    {viol && <rect x={i * W + 0.5} y={-1.6} width={1} height={1} className="mask-viol" transform={`rotate(45 ${i * W + 1} -1.1)`} />}
                  </g>
                );
              })}
              <line x1={bins * W - 0.3} x2={bins * W - 0.3} y1={-2} y2={H} className="mask-now" />
            </svg>
            <div className="mask-read">
              <span>P now <b>{v?.routine_p != null ? v.routine_p.toFixed(2) : "—"}</b></span>
              <span className={(v?.anomaly ?? 0) >= 0.5 ? "hot" : ""}>Anomaly <b>{v?.anomaly != null ? v.anomaly.toFixed(2) : "—"}</b></span>
            </div>
          </div>
        );
      })}
      <div className="mask-axis" aria-hidden="true">
        <span />
        <div>
          {hours.map(({ i, h }) => <span key={i} style={{ left: `${(i / bins) * 100}%` }}>{String(h).padStart(2, "0")}:00</span>)}
          <span className="mask-axis-now" style={{ left: "100%" }}>now</span>
        </div>
        <span />
      </div>
    </div>
  );
}
