import { useEffect, useRef } from "react";
import type { RoomView } from "../types";
import { channel, reducedMotion } from "../util";

const PER_SECOND = 5; // trace samples per second (the hub decimates the 20 Hz waveform)

function TraceRow({ name, room, speed, linked }: { name: string; room: RoomView; speed: number; linked: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const data = useRef<{ trace: number[]; at: number }>({ trace: [], at: 0 });
  const live = useRef({ alive: room.state === "breathing", speed });
  live.current = { alive: room.state === "breathing", speed };

  useEffect(() => {
    const t = room.trace ?? [];
    const prev = data.current.trace;
    if (t.length !== prev.length || t.some((v, i) => v !== prev[i])) data.current = { trace: t, at: performance.now() };
  }, [room.trace]);

  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    const color = getComputedStyle(cv).getPropertyValue("--c").trim() || "#9cf";
    const grat = getComputedStyle(cv).getPropertyValue("--grat-2").trim();
    let raf = 0;
    const still = reducedMotion();
    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = cv.clientWidth, h = cv.clientHeight;
      if (cv.width !== Math.round(w * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = grat;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 1; i < 10; i++) { const x = Math.round((w * i) / 10) + 0.5; ctx.moveTo(x, 0); ctx.lineTo(x, h); }
      ctx.moveTo(0, Math.round(h / 2) + 0.5); ctx.lineTo(w, Math.round(h / 2) + 0.5);
      ctx.stroke();
      const { trace, at } = data.current;
      const n = 20 * PER_SECOND;
      if (trace.length > 1) {
        const lag = still ? 0 : Math.max(0, 1 - ((performance.now() - at) / 1000) * live.current.speed) * PER_SECOND;
        const dx = w / (n - 1);
        const x0 = w - (trace.length - 1) * dx + lag * dx;
        ctx.save();
        ctx.beginPath(); ctx.rect(0, 0, w, h); ctx.clip();
        ctx.globalAlpha = live.current.alive ? 1 : 0.42;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.7;
        ctx.lineJoin = "round";
        ctx.beginPath();
        trace.forEach((v, i) => {
          const x = x0 + i * dx, y = h / 2 - v * (h * 0.4);
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        });
        ctx.stroke();
        ctx.restore();
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, []);

  const c = channel(name);
  const motion = room.motion ?? 0;
  return (
    <div className={`trace trace-${room.state.replace(" ", "-")} ${linked ? "is-linked" : ""}`} style={{ ["--c" as string]: c.color }}>
      <div className="trace-id">
        <span className="trace-ch">CH{c.ch}</span>
        <span className="trace-room">{room.label}</span>
      </div>
      <canvas ref={ref} className="trace-cv" aria-hidden="true" />
      <dl className="trace-read">
        <div className="trace-big">
          <dt className="sr-only">Breathing</dt>
          <dd>{room.bpm ? <>{room.bpm.toFixed(1)}<small> /min</small></> : <span className="dim">{room.state === "moving" ? "moving" : "—"}</span>}</dd>
        </div>
        <div>
          <dt>Conf</dt>
          <dd>{room.confidence != null ? room.confidence.toFixed(2) : "—"}</dd>
        </div>
        <div className={motion >= 3 ? "hot" : ""}>
          <dt>Motion</dt>
          <dd>{room.motion != null ? `${motion >= 10 ? motion.toFixed(0) : motion.toFixed(1)}×` : "—"}</dd>
        </div>
        <div className={(room.jolt ?? 0) >= 600 ? "hot" : ""}>
          <dt>Jolt</dt>
          <dd>{room.jolt ?? "—"}</dd>
        </div>
      </dl>
    </div>
  );
}

export function Traces({ rooms, speed, linkedRoom = null }: { rooms: Record<string, RoomView>; speed: number; linkedRoom?: string | null }) {
  const sensed = Object.entries(rooms).filter(([, r]) => r.sensor !== false && r.state !== "no sensor");
  return (
    <div className="traces" aria-label="Breathing waveform per room, last 20 seconds">
      {sensed.map(([n, r]) => <TraceRow key={n} name={n} room={r} speed={speed} linked={linkedRoom === n} />)}
      <p className="traces-scale" aria-hidden="true"><span>−20 s</span><span>2 s/div</span><span>now</span></p>
    </div>
  );
}
