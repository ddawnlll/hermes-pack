#!/usr/bin/env -S node --no-warnings
/**
 * apps/desktop/scripts/watch-events.ts
 *
 * CP-6 (#94) — Local realtime transport (events.jsonl watcher).
 *
 * Tails an events.jsonl file (append-only, one event per line) and pushes
 * each new line over a local WebSocket. This is the v0.6 baseline realtime
 * transport for the cockpit; Supabase Realtime is explicitly NOT a
 * dependency.
 *
 * The watcher is intentionally minimal: it opens the file, seeks to the
 * end, and polls for new bytes at a fixed interval. A more sophisticated
 * fs.watch / inotify implementation is left for a follow-up.
 *
 * Usage:
 *   watch-events.ts --events <path-to-events.jsonl> --ws-port <port>
 *   watch-events.ts --help
 *
 * Default --ws-port: 4567 (must match the WS port in apps/desktop/src/lib/realtime.ts).
 */

import { WebSocketServer, WebSocket } from "ws";
import * as fs from "node:fs";
import * as path from "node:path";

interface Args {
  events: string;
  wsPort: number;
  pollMs: number;
}

function parseArgs(argv: string[]): Args {
  const out: Args = { events: "", wsPort: 4567, pollMs: 250 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--events") {
      out.events = argv[++i];
    } else if (a === "--ws-port") {
      out.wsPort = parseInt(argv[++i], 10);
    } else if (a === "--poll-ms") {
      out.pollMs = parseInt(argv[++i], 10);
    } else if (a === "--help" || a === "-h") {
      printHelp();
      process.exit(0);
    }
  }
  if (!out.events) {
    // Default: the canonical events.jsonl under templates/. The caller
    // can override with --events.
    out.events = path.resolve(
      process.cwd(),
      "templates",
      "scripts",
      "events.jsonl"
    );
  }
  return out;
}

function printHelp(): void {
  console.log(`usage: watch-events.ts [--events <path>] [--ws-port <port>] [--poll-ms <ms>]

Tails an events.jsonl file and pushes new lines over a local WebSocket.
Default: --events templates/scripts/events.jsonl --ws-port 4567 --poll-ms 250.`);
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));

  if (!fs.existsSync(args.events)) {
    // Create an empty file so we can tail it. The first write by another
    // process will then be observed.
    fs.mkdirSync(path.dirname(args.events), { recursive: true });
    fs.writeFileSync(args.events, "");
    console.log(`[watch-events] created empty ${args.events}`);
  }

  const wss = new WebSocketServer({ port: args.wsPort, host: "127.0.0.1" });
  const clients = new Set<WebSocket>();
  wss.on("connection", (ws) => {
    clients.add(ws);
    ws.on("close", () => clients.delete(ws));
    ws.on("error", () => clients.delete(ws));
    console.log(`[watch-events] client connected; ${clients.size} total`);
  });
  console.log(`[watch-events] WS server listening on ws://127.0.0.1:${args.wsPort}`);

  // Open the file, seek to end, poll for new bytes.
  const fd = fs.openSync(args.events, "r");
  let cursor = fs.fstatSync(fd).size;
  let buf = "";
  const tick = setInterval(() => {
    const stat = fs.fstatSync(fd);
    if (stat.size <= cursor) {
      return;
    }
    const readLen = stat.size - cursor;
    const chunk = Buffer.alloc(readLen);
    fs.readSync(fd, chunk, 0, readLen, cursor);
    cursor = stat.size;
    buf += chunk.toString("utf-8");
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl);
      buf = buf.slice(nl + 1);
      if (line.length === 0) {
        continue;
      }
      // Broadcast to all connected clients.
      for (const ws of clients) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(line);
        }
      }
    }
  }, args.pollMs);

  const shutdown = () => {
    clearInterval(tick);
    fs.closeSync(fd);
    wss.close();
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main();
