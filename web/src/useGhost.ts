import { useCallback, useEffect, useRef, useState } from "react";
import type { Snapshot } from "./types";

export type Link = "connecting" | "live" | "lost";

/** The hub's snapshot stream (server-sent events), with a polling fallback. */
export function useGhost() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [link, setLink] = useState<Link>("connecting");
  const [error, setError] = useState<string | null>(null);
  const received = useRef(0);

  useEffect(() => {
    let es: EventSource | null = null;
    let timer: number | undefined;
    let closed = false;
    if (new URLSearchParams(location.search).has("once")) {
      // one frozen snapshot, no stream: for screenshots and print
      fetch("api/state").then((r) => r.json()).then((j) => { setSnap(j); setLink("live"); }).catch(() => setLink("lost"));
      return;
    }
    const open = () => {
      es = new EventSource("api/stream");
      es.onmessage = (m) => {
        received.current = performance.now();
        setSnap(JSON.parse(m.data));
        setLink("live");
      };
      es.onerror = () => {
        es?.close();
        if (closed) return;
        setLink(received.current ? "lost" : "connecting");
        timer = window.setTimeout(open, 1500);
      };
    };
    open();
    return () => {
      closed = true;
      es?.close();
      window.clearTimeout(timer);
    };
  }, []);

  const act = useCallback(async (path: string) => {
    setError(null);
    try {
      const r = await fetch(`api/${path}`, { method: "POST" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        setError(j.error || `The hub refused ${path} (${r.status}).`);
      }
    } catch {
      setError("The hub didn't answer. Is python -m hub.server still running?");
    }
  }, []);

  return { snap, link, error, act, received };
}
