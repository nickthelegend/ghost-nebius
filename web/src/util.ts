import type { Severity } from "./types";

export const CHANNELS: Record<string, { ch: number; color: string }> = {
  bedroom: { ch: 1, color: "var(--ch1)" },
  bathroom: { ch: 2, color: "var(--ch2)" },
  kitchen: { ch: 3, color: "var(--ch3)" },
  living: { ch: 4, color: "var(--ch4)" },
};

export const channel = (room: string) => CHANNELS[room] ?? { ch: 0, color: "var(--scr-ink-2)" };

export const SEV_LABEL: Record<Severity, string> = { none: "Clear", watch: "Watch", check_in: "Check-in", alert: "Alert" };
export const SEV_RANK: Record<Severity, number> = { none: 0, watch: 1, check_in: 2, alert: 3 };

export const EVENT_LABEL: Record<string, string> = {
  got_up: "Got up",
  moved: "Moved rooms",
  fall_suspected: "Possible fall",
  long_stay: "Long stay",
  too_still: "Too still",
  breath_lost: "Breathing lost",
  no_answer: "No answer",
  answered: "Answered",
};

export const EYE: Record<string, { label: string; color: string }> = {
  off: { label: "Off", color: "#2b302e" },
  path: { label: "Path light", color: "var(--eye-path)" },
  amber: { label: "Amber", color: "var(--sev-check)" },
  red: { label: "Red", color: "var(--sev-alert)" },
  follow: { label: "Breathing", color: "var(--eye-follow)" },
  breathe: { label: "Breathing", color: "var(--eye-follow)" },
  listen: { label: "Listening", color: "var(--eye-follow)" },
  think: { label: "Thinking", color: "var(--eye-follow)" },
  lamp: { label: "Lamp", color: "var(--eye-path)" },
  mood: { label: "Mood", color: "var(--eye-follow)" },
};

export const eye = (mode: string | undefined) => EYE[mode ?? "off"] ?? { label: mode ?? "Off", color: "var(--eye-follow)" };

export function stepText(s: { op: string; [k: string]: unknown }): string {
  switch (s.op) {
    case "eye":
      return `ring ${eye(String(s.mode)).label.toLowerCase()}`;
    case "look":
      return `turn to ${s.pan}°`;
    case "ask":
      return "ask and listen";
    case "say":
      return "speak";
    case "call":
      return "call family";
    case "action":
      return `${s.name}`;
    case "listen":
      return `listen ${Math.round(Number(s.ms) / 1000)} s`;
    case "checkin":
      return s.on ? "arm button" : "disarm button";
    default:
      return s.op;
  }
}

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
