export type Severity = "none" | "watch" | "check_in" | "alert";

export interface RoomView {
  label: string;
  pan: number | null;
  sleep: boolean;
  sensor: boolean;
  present: boolean;
  state: "moving" | "breathing" | "still" | "empty" | "no sensor" | "waiting";
  bpm?: number | null;
  confidence?: number | null;
  motion?: number | null;
  jolt?: number | null;
  trace?: number[];
  since_min?: number | null;
  watching?: boolean;
  flags?: string[];
  anomaly?: number;
  routine_p?: number | null;
}

export interface Evidence {
  id: string;
  source: "rule" | "csi" | "routine" | "lamp" | "earlier";
  room: string;
  text: string;
}

export interface LampStep {
  op: string;
  [k: string]: unknown;
}

export interface Capture {
  id: number;
  t: number;
  clock: string;
  event: string;
  room: string;
  facts: Record<string, unknown>;
  floor: Severity;
  severity: Severity;
  explain: string;
  cites: string[];
  evidence: Evidence[];
  say: string;
  family: string;
  by: string;
  lamp: LampStep[];
  outcome: string;
}

export interface LampState {
  eye: string;
  bright: number | null;
  pan: number;
  action: string;
  level: number;
  speaking: string;
  said: string;
  listening: boolean;
  checkin: boolean;
  heard: string;
  updated: number;
}

export interface Snapshot {
  mode: "replay" | "live";
  now: number;
  clock: string;
  home: {
    name: string;
    person: string;
    family: string;
    plan: { w: number; h: number; lamp: [number, number]; lamp_room: string };
    doors: [number, number, "h" | "v"][];
    rooms: Record<string, { label: string; plan: [number, number, number, number] | null; sensor: boolean }>;
  };
  rooms: Record<string, RoomView>;
  followed: string | null;
  routine: {
    bin_minutes: number;
    days: number;
    now_bin: number;
    rooms: Record<string, { baseline: number[]; occupied_days: number[]; days: number[]; today: (number | null)[] }>;
  } | null;
  timeline: Capture[];
  lamp: {
    kind: "virtual" | "hotaru" | null;
    connected: boolean;
    busy: boolean;
    state: LampState | null;
    recent: ({ clock: string } & LampStep)[];
  };
  model: { online: boolean; reason: string | null; log: string | null };
  log: { clock: string; line: string }[];
  replay?: {
    pos: number;
    duration: number;
    scale: number;
    speed: number;
    paused: boolean;
    done: boolean;
    synthetic: boolean;
    start: number;
    end: number;
    markers: { t: number; label: string; clock: string }[];
    jump_to?: number | null;
  };
}
