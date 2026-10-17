import { Fragment, useEffect, useState } from "react";
import type { Capture, Severity, Snapshot } from "../types";
import { EVENT_LABEL, SEV_LABEL, SEV_RANK, channel, stepText } from "../util";

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
      <Caption c={c} hover={hover} setHover={setHover} />
      {c.lamp.length > 0 && (
        <ol className="cap-steps" aria-label="What HOTARU did">
          {c.lamp.map((s, i) => <li key={i}>{stepText(s)}</li>)}
          {c.outcome && <li className="cap-outcome">{c.outcome}</li>}
        </ol>
      )}
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

export function Trigger({ snap, pinned, setPinned }: { snap: Snapshot; pinned: number | null; setPinned: (n: number | null) => void }) {
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
        <div className="cap-empty">
          <p><b>No captures yet.</b> GHOST triggers when a rule fires: getting up at night, a jolt then stillness, a stay far longer than the routine it learned, breathing lost, or a check-in nobody answers.</p>
          <p>Each capture lands here with Nemotron's explanation, every claim cited to the measurement behind it.</p>
        </div>
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
