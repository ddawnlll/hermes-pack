#!/usr/bin/env bash
# ============================================================================
# escalation-gate.sh — T4 / AFK Escalation Gate (issue #31)
# ============================================================================
# Deterministic pre-gate that decides whether a dispute escalates to T4 Human.
# Rules:
#   - human_available + t4_budget > 0  → escalate_to_t4
#   - human_available = false (AFK)    → park + safe-default HOLD
#   - t4_budget <= 0                   → hold (budget exhausted)
# Fail-closed: defaults to HOLD on any error.
# ============================================================================
set -uo pipefail

# Read human availability from status file (JSON) or env var
HUMAN_STATUS_FILE="${HOME}/.hermes/human-status.json"
HUMAN_AVAILABLE="${HERMES_HUMAN_AVAILABLE:-}"
T4_BUDGET="${HERMES_T4_BUDGET:-}"

# If env var not set, try reading from status file
if [ -z "$HUMAN_AVAILABLE" ] && [ -f "$HUMAN_STATUS_FILE" ]; then
  HUMAN_AVAILABLE=$(python3 -c "
import json, sys
try:
    with open('$HUMAN_STATUS_FILE') as f:
        d = json.load(f)
    print('true' if d.get('human_available', False) else 'false')
except Exception:
    print('false')
" 2>/dev/null)
fi

# If env var not set, default to false (fail-closed)
if [ -z "$HUMAN_AVAILABLE" ]; then
  HUMAN_AVAILABLE="false"
fi

# If t4_budget not set, try reading from state.json or default to 0
if [ -z "$T4_BUDGET" ]; then
  T4_BUDGET="0"
fi

# Normalize boolean
if [ "$HUMAN_AVAILABLE" = "true" ] || [ "$HUMAN_AVAILABLE" = "1" ]; then
  HUMAN_AVAILABLE="true"
else
  HUMAN_AVAILABLE="false"
fi

# Deterministic decision
decline_reason=""
action=""

if [ "$HUMAN_AVAILABLE" != "true" ]; then
  action="park"
  decline_reason="human_afk"
elif [ "$(python3 -c "print(float('$T4_BUDGET') > 0)" 2>/dev/null || echo 'False')" != "True" ]; then
  action="hold"
  decline_reason="t4_budget_exhausted"
else
  action="escalate_to_t4"
  decline_reason=""
fi

# Output JSON verdict
cat <<EOF
{"action": "$action", "reason": "$decline_reason", "human_available": $HUMAN_AVAILABLE, "t4_budget": $T4_BUDGET, "safe_default": "HOLD"}
EOF

# Exit codes: 0 = normal gate output (caller decides), 1 = error
if [ -z "$action" ]; then
  echo '{"action": "hold", "reason": "gate_error", "safe_default": "HOLD"}' >&2
  exit 1
fi
exit 0
