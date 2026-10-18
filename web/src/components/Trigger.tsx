import { Fragment, useEffect, useState } from "react";
import type { Capture, Severity, Snapshot } from "../types";
import { EVENT_LABEL, SEV_LABEL, SEV_RANK, channel, senseLine, stepText } from "../util";
import { FastForward } from "lucide-react";

const SOURCE: Record<string, string> = { rule: "Rule", csi: "Wi-Fi", routine: "Routine", lamp: "HOTARU", earlier: "Earlier" };
const LEVELS: Severity[] = ["watch", "check_in", "alert"];

/** The loop's current state: the last capture's severity, unless the person answered. */
export function loopState(t: Capture[]): { sev: Severity; note: string } {
  const last = t[t.length - 1];
  if (!last) return { sev: "none", note: "Armed: watching every room" };
  if (last.event === "answered") return { sev: "none", note: `Stood down: answered by ${String(last.facts.how ?? "them")}` };
  return { sev: last.severity, note: `${EVENT_LABEL[last.event] ?? last.event}, ${snapRoom(last.room)}` };
}
const snapRoom = (r: string) => (r === "living" ? "living room" : r);

function Caption({ c, hover, setHover }: { c: Capture; hover: string | null; setHover: (s: string | null) => void }) {
  const parts = c.explain.split(/(\[E\d+\])/g);
  return (
    <p className="cap-text">
      {parts.map((p, i) => {
        const m = p.match(/^\[(E\d+)\]$/);
        if (!m) return <Fragment key={i}>{p}</Fragment>;
        return (
          <button
            key={i}
            className={`cite ${hover === m[1] ? "is-on" : ""}`}
            onMouseEnter={() => setHover(m[1])}
            onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(m[1])}
            onBlur={() => setHover(null)}
            onClick={() => document.getElementById(`ev-${c.id}-${m[1]}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" })}
            aria-label={`Evidence ${m[1]}`}
          >
            {m[1]}
          </button>
        );
      })}
    </p>
  );
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

export function CaptureDetail({ c }: { c: Capture }) {
  const [hover, setHover] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const narrow = useNarrow();
  const fold = narrow && !all && c.evidence.some((e) => !c.cites.includes(e.id));
  const shown = fold ? c.evidence.filter((e) => c.cites.includes(e.id)) : c.evidence;
  const raised = SEV_RANK[c.severity] > SEV_RANK[c.floor];
  const by = c.by.startsWith("rules") ? (c.by === "rules" ? "Rules + template (no model call)" : "Rules (model error)") : `Nemotron · ${c.by.replace(/^nvidia\//, "")}`;
  const ask = c.lamp.find((s) => s.op === "ask");
  return (
    <article className={`cap sev-${c.severity}`} aria-live="polite">
      <header className="cap-head">
        <span className="cap-no">#{String(c.id).padStart(2, "0")}</span>
        <h3 className="cap-title">{EVENT_LABEL[c.event] ?? c.event}</h3>
        <span className="cap-room" style={{ ["--c" as string]: channel(c.room).color }}>{snapRoom(c.room)}</span>
        <time className="cap-time">{c.clock}</time>
      </header>
      <div className="cap-sev">
        <span className={`sev-badge sev-${c.severity}`}>{SEV_LABEL[c.severity]}</span>
        <span className="cap-by">
          {raised ? `raised from ${SEV_LABEL[c.floor].toLowerCase()} · ` : c.floor !== "none" ? `rule floor ${SEV_LABEL[c.floor].toLowerCase()} · ` : ""}
          {by}
        </span>
      </div>
      <ol className={`loop sev-${c.severity}`} aria-label="Sense, reason, act">
        <li className="loop-cell">
          <span className="loop-k">Sense</span>
          <span className="loop-v"><span className="loop-ch" style={{ ["--c" as string]: channel(c.room).color }}>{channel(c.room).ch ? `CH${channel(c.room).ch}` : "HOTARU"}</span>{senseLine(c.event, c.facts)}</span>
        </li>
        <li className="loop-cell">
          <span className="loop-k">Reason</span>
          <span className="loop-v">{c.by.startsWith("rules") ? "Rules" : "Nemotron"} → {SEV_LABEL[c.severity].toLowerCase()} · cites {c.cites.length} of {c.evidence.length}</span>
        </li>
        <li className="loop-cell">
          <span className="loop-k">Act</span>
          <span className="loop-v">{c.lamp.length ? c.lamp.filter((s) => s.op !== "call").map(stepText).slice(0, 3).join(" · ") + (c.lamp.some((s) => s.op === "call") ? " · call family" : "") : "log only"}</span>
        </li>
      </ol>
      <Caption c={c} hover={hover} setHover={setHover} />
      {c.outcome && <p className="cap-outcome"><span>Outcome</span> {c.outcome}</p>}
      {(ask || c.say) && <blockquote className="cap-say">“{String(ask?.text ?? c.say)}”</blockquote>}
      {c.family && <p className="cap-family"><b>To family:</b> {c.family}</p>}
      <ol className="evidence" aria-label="Evidence">
        {shown.map((e) => (
          <li
            key={e.id}
            id={`ev-${c.id}-${e.id}`}
            className={`ev ev-${e.source} ${c.cites.includes(e.id) ? "is-cited" : ""} ${hover === e.id ? "is-on" : ""}`}
            onMouseEnter={() => setHover(e.id)}
            onMouseLeave={() => setHover(null)}
          >
            <span className="ev-id">{e.id}</span>
            <span className="ev-src">{SOURCE[e.source] ?? e.source}</span>
            <span className="ev-text">{e.text}</span>
          </li>
        ))}
      </ol>
      {narrow && c.evidence.length > shown.length && (
        <button className="key key-s ev-more" onClick={() => setAll(true)}>Show all evidence ({c.evidence.length})</button>
      )}
    </article>
  );
}

const RULES: { sev: Severity; when: string; then: string }[] = [
  { sev: "watch", when: "Gets up at night", then: "path light, HOTARU follows" },
  { sev: "watch", when: "A jolt, then stillness", then: "watch closely" },
  { sev: "check_in", when: "Stays far longer than the learned routine", then: "HOTARU asks" },
  { sev: "alert", when: "Nobody answers", then: "call family" },
];

function Armed({ snap, act }: { snap: Snapshot; act: (p: string) => void }) {
  const rooms = Object.entries(snap.rooms).filter(([, r]) => r.sensor !== false && r.state !== "no sensor");
  const jump = snap.replay?.jump_to;
  const odd = rooms.filter(([, r]) => r.routine_p != null && (r.present ? r.routine_p < 0.5 : r.routine_p >= 0.5)).length;
  return (
    <div className="armed">
      <h3 className="cap-title">Armed</h3>
      <p className="armed-lead">
        Watching {rooms.length} rooms through the walls.{" "}
        {odd ? `${odd} ${odd === 1 ? "room differs" : "rooms differ"} from the routine it learned; no rule has fired.` : "Everything matches the routine it learned."}
      </p>
      <ul className="armed-rooms">
        {rooms.map(([n, r]) => {
          const usual = r.routine_p == null ? null : r.present ? r.routine_p >= 0.5 : r.routine_p < 0.5;
          return (
            <li key={n} style={{ ["--c" as string]: channel(n).color }}>
              <span className="trace-ch">CH{channel(n).ch}</span>
              <span className="armed-room">{r.label}</span>
              <span className="armed-state">{r.state === "breathing" && r.bpm ? `breathing ${r.bpm.toFixed(1)}/min` : r.state === "empty" ? "empty" : r.state}</span>
              <span className={`armed-usual ${usual === false ? "is-odd" : ""}`}>{usual == null ? "" : usual ? "as usual" : "unusual"}</span>
            </li>
          );
        })}
      </ul>
      <h4 className="silk armed-h">Waiting for</h4>
      <ul className="armed-rules">
        {RULES.map((r) => (
          <li key={r.when}><span className={`cap-row-dot sev-dot-${r.sev}`} aria-hidden="true" /><span>{r.when}</span><span className="armed-then">{r.then}</span></li>
        ))}
      </ul>
      {jump != null && snap.replay && snap.replay.pos < jump && (
        <button className="key key-jump" onClick={() => act("replay/jump")}>
          <FastForward size={16} aria-hidden="true" />
          <span>Jump to {new Date((snap.replay.start + jump * snap.replay.scale) * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}, just before he gets up</span>
        </button>
      )}
    </div>
  );
}

export function Trigger({ snap, pinned, setPinned, act }: { snap: Snapshot; pinned: number | null; setPinned: (n: number | null) => void; act: (p: string) => void }) {
  const t = snap.timeline;
  const state = loopState(t);
  const shown = (pinned != null ? t.find((c) => c.id === pinned) : undefined) ?? t[t.length - 1];
  return (
    <div className="trigger">
      <div className={`trig-state sev-${state.sev}`} role="status">
        <div className="trig-lamps" aria-hidden="true">
          {LEVELS.map((l) => (
            <span key={l} className={`trig-lamp lamp-${l} ${SEV_RANK[state.sev] >= SEV_RANK[l] ? "is-lit" : ""} ${state.sev === l ? "is-now" : ""}`}>
              {SEV_LABEL[l]}
            </span>
          ))}
        </div>
        <p className="trig-note"><b>{state.sev === "none" ? "Clear" : SEV_LABEL[state.sev]}</b> {state.note}</p>
      </div>
      {shown ? (
        <>
          {pinned != null && shown.id !== t[t.length - 1]?.id && (
            <button className="key key-s back-latest" onClick={() => setPinned(null)}>Back to the latest capture</button>
          )}
          <CaptureDetail c={shown} />
        </>
      ) : (
        <Armed snap={snap} act={act} />
      )}
      {t.length > 1 && (
        <div className="cap-list">
          <h3 className="silk">Captures</h3>
          <ol>
            {[...t].reverse().map((c) => (
              <li key={c.id}>
                <button className={`cap-row sev-${c.severity} ${shown?.id === c.id ? "is-on" : ""}`} onClick={() => setPinned(c.id === t[t.length - 1].id ? null : c.id)} aria-current={shown?.id === c.id}>
                  <time>{c.clock.slice(0, 5)}</time>
                  <span className="cap-row-dot" aria-hidden="true" />
                  <span className="cap-row-ev">{EVENT_LABEL[c.event] ?? c.event}</span>
                  <span className="cap-row-room">{snapRoom(c.room)}</span>
                  <span className="cap-row-sev">{SEV_LABEL[c.severity]}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
