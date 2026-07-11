#!/usr/bin/env bash
# Adaptive Ratchet — Red Team bar adjustment based on pass/block ratio
set -euo pipefail

LEDGER_DIR="${1:?Usage: ratchet-update.sh <ledger_dir>}"
RATCHET_FILE="${LEDGER_DIR}/ratchet.json"
OBJECTIONS_FILE="${LEDGER_DIR}/redteam/objections.jsonl"
HISTORY_WINDOW=20

mkdir -p "$(dirname "$RATCHET_FILE")"

# Initialize ratchet.json if missing
if [ ! -f "$RATCHET_FILE" ]; then
  printf '{"schema_version":1,"level":0,"blocking_ratio":0.0,"window_size":20,"history":[],"last_updated":null}\n' > "$RATCHET_FILE"
  echo '{"action":"init","level":0}'
  exit 0
fi

# No objections file → skip
if [ ! -f "$OBJECTIONS_FILE" ] || [ ! -s "$OBJECTIONS_FILE" ]; then
  echo '{"action":"skip","reason":"no objections history"}'
  exit 0
fi

# Compute blocking ratio
TOTAL=$(tail -n "$HISTORY_WINDOW" "$OBJECTIONS_FILE" | wc -l | tr -d ' ')
if [ "$TOTAL" -eq 0 ]; then
  echo '{"action":"skip","reason":"empty objections window"}'
  exit 0
fi

BLOCKING=$(tail -n "$HISTORY_WINDOW" "$OBJECTIONS_FILE" | grep -c '"verdict":"BLOCK"' || true)
RATIO=$(echo "scale=2; $BLOCKING / $TOTAL" | bc 2>/dev/null || echo "0.00")

# Apply ratchet logic via Python
python3 -c "
import json, sys
from datetime import datetime, timezone

ratchet_file = sys.argv[1]
ratio = float(sys.argv[2])
total = int(sys.argv[3])
blocking = int(sys.argv[4])

with open(ratchet_file) as f:
    ratchet = json.load(f)

old_level = ratchet.get('level', 0)
action = 'maintain'

if ratio < 0.20:
    ratchet['level'] = min(ratchet['level'] + 1, 5)
    action = 'tighten'
elif ratio > 0.80:
    ratchet['level'] = max(ratchet['level'] - 1, -3)
    action = 'loosen'

ratchet['blocking_ratio'] = ratio
ratchet['window_size'] = total
ratchet['last_updated'] = datetime.now(timezone.utc).isoformat()

ratchet['history'].append({
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'blocking': blocking, 'total': total, 'ratio': ratio,
    'old_level': old_level, 'new_level': ratchet['level'], 'action': action
})
ratchet['history'] = ratchet['history'][-50:]

with open(ratchet_file, 'w') as f:
    json.dump(ratchet, f, indent=2)

import json as j
print(j.dumps({'action': action, 'old_level': old_level, 'new_level': ratchet['level'], 'blocking_ratio': ratio, 'blocking': blocking, 'total': total}))
" "$RATCHET_FILE" "$RATIO" "$TOTAL" "$BLOCKING"
