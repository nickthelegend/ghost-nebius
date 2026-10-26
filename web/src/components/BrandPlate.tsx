import type { Snapshot } from "../types";
import type { Link } from "../useGhost";

function Lamp({ on, tone, label, value }: { on: boolean; tone: "good" | "warn" | "off"; label: string; value: string }) {
  return (
    <div className="plate-lamp">
      <span className={`led led-${on ? tone : "off"}`} aria-hidden="true" />
      <span className="plate-lamp-label">{label}</span>
      <span className="plate-lamp-value">{value}</span>
    </div>
  );
}

export function BrandPlate({ snap, link }: { snap: Snapshot | null; link: Link }) {
  const sensed = snap ? Object.values(snap.rooms).filter((r) => r.sensor !== false && r.state !== "waiting").length : 0;
  const model = snap?.model;
  const lamp = snap?.lamp;
  const reason = model?.online ? (model.reason ?? "").replace(/^nvidia\//, "") : "Setup required: NEBIUS_API_KEY";
  const act = !lamp ? "—" : !lamp.connected ? "Waiting for HOTARU" : lamp.kind === "virtual" ? "Virtual HOTARU" : "HOTARU connected";
  return (
    <header className="plate">
      <div className="plate-mark">
        <svg viewBox="0 0 40 40" aria-hidden="true" className="plate-logo">
          <rect x="1" y="1" width="38" height="38" rx="7" fill="var(--screen)" />
          <path d="M6 23c3.4 0 3.4-9 6.8-9s3.4 13 6.8 13 3.4-16 6.8-16 3.4 11 6.8 11" fill="none" stroke="var(--ch2)" strokeWidth="2.6" strokeLinecap="round" />
        </svg>
        <div>
          <h1 className="plate-name">GHOST</h1>
          <p className="plate-model">CSI-4 home guardian · Wi-Fi sensing · no cameras</p>
        </div>
      </div>
      <div className="plate-lamps" role="list" aria-label="System status">
        <Lamp on={sensed > 0} tone="good" label="Sense" value={sensed ? `${sensed} channels` : "No signal"} />
        <Lamp on tone={model?.online ? "good" : "warn"} label="Reason" value={reason} />
        <Lamp on={!!lamp?.connected} tone="good" label="Act" value={act} />
      </div>
      <div className="plate-clock">
        <span className="plate-clock-time" aria-label="Scene time">{snap?.clock ?? "--:--:--"}</span>
        <span className="plate-clock-note">
          {link === "lost" ? "Hub link lost · retrying" : !snap ? "Connecting to the hub" : snap.mode === "replay"
            ? `Replay · scene time ×${snap.replay?.scale ?? 1}${snap.replay?.synthetic ? " · synthetic night" : ""}`
            : "Live boards"}
        </span>
      </div>
    </header>
  );
}
