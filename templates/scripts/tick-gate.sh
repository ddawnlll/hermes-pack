#!/usr/bin/env bash
# Pre-run gate for the orchestrator tick.
# Emits {"wakeAgent": false} to skip the LLM entirely when there is nothing
# to do. This is the PRE-TICK gate — it checks whether to wake the orchestrator.
# Praxis (evidence gate) runs AFTER the worker produces output.
set -u
REPO="__HERMES_REPO_DIR__"
LEDGER_DIR="__HERMES_LEDGER_DIR__"
CTRL="$REPO/$LEDGER_DIR/control.yaml"
STATE_DIR="$HOME/.hermes/scripts/.hermes-state"
mkdir -p "$STATE_DIR"

# 1) Hard gate on control.yaml mode
if [ ! -f "$CTRL" ]; then
  echo '{"wakeAgent": true, "context": {"warning": "control.yaml missing"}}'
  exit 0
fi
mode=$(grep -E '^mode:' "$CTRL" | awk '{print $2}')
if [ "$mode" != "running" ]; then
  last="$STATE_DIR/last-paused-wake"
  now=$(date +%s)
  prev=$(cat "$last" 2>/dev/null || echo 0)
  if [ $((now - prev)) -lt 21600 ]; then
    echo '{"wakeAgent": false}'
  else
    echo "$now" > "$last"
    echo "{\"wakeAgent\": true, \"context\": {\"mode\": \"$mode\", \"note\": \"heartbeat while not running\"}}"
  fi
  exit 0
fi

# 2) Activity gate: wake if the board db, runs/, or control.yaml changed
#    since the last wake, else skip this tick.
last="$STATE_DIR/last-activity-wake"
prev=$(cat "$last" 2>/dev/null || echo 0)
newest=0
for f in "$HOME/.hermes/kanban.db" "$CTRL"; do
  [ -f "$f" ] && m=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f") && [ "$m" -gt "$newest" ] && newest=$m
done
runs_newest=$(find "$REPO/$LEDGER_DIR/runs" -type f -newer "$last" 2>/dev/null | head -1)
if [ "$newest" -le "$prev" ] && [ -z "$runs_newest" ]; then
  now=$(date +%s)
  if [ $((now - prev)) -lt 10800 ]; then
    echo '{"wakeAgent": false}'
    exit 0
  fi
fi
date +%s > "$last"
echo '{"wakeAgent": true}'
