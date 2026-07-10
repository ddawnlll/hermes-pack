#!/usr/bin/env bash
# reflector-dispatch.sh — Dispatch Reflector on plateau/idle
#
# Checks feature flags and state before dispatching the Reflector agent.
# In shadow mode, collects proposals without mutating canonical beliefs.
#
# Exit codes:
#   0 = Reflector should run
#   1 = Reflector should NOT run (idle/disabled/no trigger)
#   2 = Error

set -u
REPO="__HERMES_REPO_DIR__"
LEDGER_DIR="__HERMES_LEDGER_DIR__"
STATE_FILE="$REPO/$LEDGER_DIR/state.json"
BELIEFS_FILE="$REPO/$LEDGER_DIR/beliefs.yaml"
REFLECTOR_PROPOSALS="$REPO/$LEDGER_DIR/reflector_proposals.yaml"

# ── 1) Check feature flag ──────────────────────────────────────────────
if [ ! -f "$STATE_FILE" ]; then
  echo '{"wakeReflector": false, "reason": "state.json missing"}'
  exit 1
fi

reflector_mode=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    s = json.load(f)
features = s.get('features', {})
print(features.get('reflector', 'shadow'))
" 2>/dev/null)

if [ "$reflector_mode" = "disabled" ]; then
  echo "{\"wakeReflector\": false, \"reason\": \"reflector=disabled\", \"mode\": \"$reflector_mode\"}"
  exit 1
fi

# Active mode requires valid readiness artifact
if [ "$reflector_mode" = "active" ]; then
  READINESS_FILE="$REPO/$LEDGER_DIR/reflector/readiness.json"
  if [ ! -f "$READINESS_FILE" ]; then
    echo '{"wakeReflector": false, "reason": "reflector=active but no readiness artifact. Run readiness-check.py first."}'
    exit 1
  fi
  python3 -c "
import json
with open('$READINESS_FILE') as f:
    d = json.load(f)
if not d.get('all_checks_pass'):
    print('checks_failed')
    exit(1)
ts = d.get('timestamp', '')
if ts:
    from datetime import datetime
    t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    age = (datetime.utcnow() - t.replace(tzinfo=None)).total_seconds()
    if age > 86400:
        print('expired')
        exit(1)
print('valid')
" 2>&1 | grep -q valid || {
    echo '{"wakeReflector": false, "reason": "reflector=active but readiness expired or failed. Re-run readiness-check.py."}'
    exit 1
  }
fi

# ── 2) Check state phase ───────────────────────────────────────────────
phase=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    s = json.load(f)
print(s.get('phase', 'idle'))
" 2>/dev/null)

if [ "$phase" != "idle" ] && [ "$phase" != "consolidate" ]; then
  echo "{\"wakeReflector\": false, \"reason\": \"phase=$phase (needs idle/consolidate)\"}"
  exit 1
fi

# ── 3) Check no workers running ────────────────────────────────────────
workers=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    s = json.load(f)
w = s.get('worker_status', {})
running = [k for k,v in w.items() if v == 'running']
print(','.join(running) if running else 'none')
" 2>/dev/null)

if [ "$workers" != "none" ]; then
  echo "{\"wakeReflector\": false, \"reason\": \"workers running: $workers\"}"
  exit 1
fi

# ── 4) Check plateau trigger ───────────────────────────────────────────
stagnation=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    s = json.load(f)
print(s.get('stagnation', 0))
" 2>/dev/null)

echo "{\"wakeReflector\": true, \"mode\": \"$reflector_mode\", \"phase\": \"$phase\", \"stagnation\": $stagnation}"
exit 0
