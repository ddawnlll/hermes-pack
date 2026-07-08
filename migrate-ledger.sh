#!/usr/bin/env bash
# ============================================================================
# migrate-ledger.sh — v1 → v2 Ledger Migration
# ============================================================================
# Converts a v1 Hermes state.json to the v2 unified schema format.
# v1 had incompatible field names vs desktop: this migration normalizes them.
#
# Usage:
#   bash migrate-ledger.sh <path/to/state.json> [--dry-run] [--backup]
#
# Example:
#   bash migrate-ledger.sh .alphaforge/orchestrator/state.json --backup
# ============================================================================
set -euo pipefail

STATE_FILE="${1:-}"
DRY_RUN=false
BACKUP=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --backup) BACKUP=true ;;
  esac
done

if [ -z "$STATE_FILE" ] || [ ! -f "$STATE_FILE" ]; then
  echo "Usage: bash migrate-ledger.sh <path/to/state.json> [--dry-run] [--backup]"
  echo "ERROR: State file not found: $STATE_FILE"
  exit 1
fi

echo "[migrate-ledger] Migrating: $STATE_FILE"

# Read v1 state
V1=$(cat "$STATE_FILE")

# Detect schema version
SCHEMA_VER=$(echo "$V1" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('schema_version', 0))" 2>/dev/null || echo "0")

if [ "$SCHEMA_VER" -ge 1 ] 2>/dev/null; then
  echo "[migrate-ledger] Already at schema_version=$SCHEMA_VER — no migration needed"
  exit 0
fi

echo "[migrate-ledger] Detected v1 schema — migrating to v2..."

# Build v2 state with field mapping
V2=$(python3 -c "
import json, sys

v1 = json.load(open('$STATE_FILE'))

v2 = {
    'schema_version': 1,
    'tick': v1.get('tick', v1.get('current_tick', 0)),
    'worker_status': v1.get('worker_status', v1.get('active_branches', {})),
    'spend_today_usd': v1.get('spend_today_usd', v1.get('total_budget_spent', 0)),
    'budget_usd': v1.get('budget_usd', v1.get('max_llm_spend_per_day_usd', 25)),
    'last_tick_at': v1.get('last_tick_at', None),
    'board': v1.get('board', ''),
    'gates': v1.get('gates', {'T0': 0, 'T1': 0, 'T2': 0, 'T3': 0, 'T4': 0}),
    'goal_status': v1.get('goal_status', 'none')
}

print(json.dumps(v2, indent=2))
")

if [ "$DRY_RUN" = true ]; then
  echo "[migrate-ledger] DRY-RUN — would write:"
  echo "$V2"
  echo "[migrate-ledger] DRY-RUN complete. Pass --backup and remove --dry-run to apply."
  exit 0
fi

if [ "$BACKUP" = true ]; then
  BACKUP_FILE="${STATE_FILE}.v1.backup"
  cp "$STATE_FILE" "$BACKUP_FILE"
  echo "[migrate-ledger] Backup saved: $BACKUP_FILE"
fi

echo "$V2" > "$STATE_FILE"
echo "[migrate-ledger] ✅ Migration complete: $STATE_FILE"
echo "[migrate-ledger] schema_version=1, tick=$(echo "$V2" | python3 -c "import json,sys; print(json.load(sys.stdin)['tick'])")"

# Verify v2 is valid JSON
python3 -c "import json; json.load(open('$STATE_FILE'))" && echo "[migrate-ledger] ✅ Valid JSON"
