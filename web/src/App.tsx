import { useEffect, useRef, useState } from "react";
import { Acquisition } from "./components/Acquisition";
import { BrandPlate } from "./components/BrandPlate";
import { Hotaru } from "./components/Hotaru";
import { Mask } from "./components/Mask";
import { PlanScreen } from "./components/PlanScreen";
import { Traces } from "./components/Traces";
import { Trigger } from "./components/Trigger";
import { useGhost } from "./useGhost";

function Module({ label, sub, className = "", children }: { label: string; sub?: string; className?: string; children: React.ReactNode }) {
  return (
    <section className={`mod ${className}`} aria-label={label}>
      <h2 className="silk">{label}{sub && <span className="silk-sub">{sub}</span>}</h2>
      <div className="screen">{children}</div>
    </section>
  );
}

export default function App() {
  const { snap, link, error, act } = useGhost();
  const [pinned, setPinned] = useState<number | null>(null);
  const lastCount = useRef(-1);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (!snap) return;
    const n = snap.timeline.length;
    if (n < lastCount.current) setPinned(null); // the night restarted
    if (n > lastCount.current && lastCount.current >= 0 && snap) {
      setFlash(true);
      const t = window.setTimeout(() => setFlash(false), 700);
      lastCount.current = n;
      return () => window.clearTimeout(t);
    }
    lastCount.current = n;
  }, [snap?.timeline.length, !!snap]);

  return (
    <div className="chassis">
      <BrandPlate snap={snap} link={link} />
      {!snap ? (
        <div className="boot screen">
          <p><b>{link === "lost" ? "Lost the hub." : "Connecting to the GHOST hub…"}</b></p>
          <p className="dim">The dashboard reads <code>/api/stream</code> from <code>python -m hub.server</code>. Start it, then this page fills in on its own.</p>
        </div>
      ) : (
        <>
          <Acquisition snap={snap} act={act} onPick={(id) => setPinned(id)} />
          {error && <p className="err" role="alert">{error}</p>}
          <main className="bench">
            <div className="bench-col bench-main">
            <Module label="Plan" sub="XY · presence by Wi-Fi, through walls" className="m-plan">
              <PlanScreen snap={snap} />
            </Module>
            <Module label="Breathing" sub="CH1–CH4 · 20 s" className="m-traces">
              <Traces rooms={snap.rooms} speed={snap.replay?.speed ?? 1} />
            </Module>
            </div>
            <div className="bench-col bench-side">
            <Module label="Trigger" sub={snap.model.online ? "captures · Nemotron explains, citing evidence" : "captures · rules + templates explain, citing evidence"} className={`m-trigger ${flash ? "is-flash" : ""}`}>
              <Trigger snap={snap} pinned={pinned} setPinned={setPinned} />
            </Module>
            <Module label="HOTARU" sub={snap.lamp.kind === "virtual" ? "output · virtual lamp" : "output · robot lamp"} className="m-hotaru">
              <Hotaru snap={snap} act={act} />
            </Module>

            </div>
            <div className="bench-col bench-main bench-tail">
            <Module label="Routine" sub="mask test · learned vs last 24 h" className="m-mask">
              <Mask snap={snap} />
            </Module>
            {snap.log.length > 0 && (
              <Module label="Log" sub={snap.model.log ? `Nemotron · ${snap.model.log.replace(/^nvidia\//, "")}` : "rules"} className="m-log">
                <ol className="log">
                  {snap.log.slice(-6).reverse().map((l, i) => <li key={i}><time>{l.clock}</time> {l.line}</li>)}
                </ol>
              </Module>
            )}
            </div>
          </main>
          <footer className="foot">
            <span>MIT · ESP32 Wi-Fi CSI → Nemotron on Nebius Token Factory → HOTARU</span>
            {snap.replay?.synthetic && <span>The bundled night and its 14-day routine are synthesized from the channel model until a real night is recorded.</span>}
          </footer>
        </>
      )}
    </div>
  );
}
