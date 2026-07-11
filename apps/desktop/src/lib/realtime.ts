/**
 * apps/desktop/src/lib/realtime.ts
 *
 * CP-6 (#94) — Cockpit-side client for the local realtime transport.
 *
 * Connects to ws://127.0.0.1:4567 (the watcher) and exposes a typed event
 * stream. The watcher (apps/desktop/scripts/watch-events.ts) tails the
 * events.jsonl file and broadcasts each new line over WebSocket.
 *
 * This is the v0.6 baseline realtime transport. Supabase Realtime is
 * explicitly NOT a dependency; if it is added later, the wire format
 * here (JSON-per-line, one event per line) is the contract.
 */

export type RealtimeEventKind =
  | "candidate_transition"
  | "intent_applied"
  | "kill"
  | "pause"
  | "freeze"
  | "rollback"
  | "tick";

export interface RealtimeEvent {
  kind: RealtimeEventKind;
  tick_id?: number;
  candidate_id?: string;
  payload?: Record<string, unknown>;
  at: string; // ISO-8601
}

export type RealtimeHandler = (e: RealtimeEvent) => void;

const DEFAULT_WS_URL = "ws://127.0.0.1:4567";
const RECONNECT_BASE_MS = 250;
const RECONNECT_MAX_MS = 5_000;

export interface RealtimeClient {
  close(): void;
}

export function connectRealtime(
  onEvent: RealtimeHandler,
  opts: { url?: string } = {}
): RealtimeClient {
  const url = opts.url ?? DEFAULT_WS_URL;
  let ws: WebSocket | null = null;
  let attempt = 0;
  let closed = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const open = () => {
    if (closed) return;
    ws = new WebSocket(url);
    ws.onmessage = (ev) => {
      const data = typeof ev.data === "string" ? ev.data : "";
      if (!data) return;
      try {
        const obj = JSON.parse(data);
        if (
          obj &&
          typeof obj === "object" &&
          "kind" in obj &&
          "at" in obj
        ) {
          onEvent(obj as RealtimeEvent);
        }
      } catch {
        // Malformed line — skip silently. The watcher guarantees one
        // JSON event per line; if we cannot parse, the producer is
        // emitting garbage. The cockpit logs this elsewhere.
      }
    };
    ws.onopen = () => {
      attempt = 0;
    };
    ws.onclose = () => {
      ws = null;
      if (closed) return;
      attempt++;
      const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempt, RECONNECT_MAX_MS);
      reconnectTimer = setTimeout(open, delay);
    };
    ws.onerror = () => {
      // onclose will fire; reconnect happens there.
    };
  };

  open();

  return {
    close() {
      closed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (ws) {
        ws.close();
        ws = null;
      }
    },
  };
}
