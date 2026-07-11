#!/usr/bin/env bash
# Red Team Trigger — dispatches a Red Team kanban task when the Janus forward
# face detects that a hypothesis re-litigates a refuted idea.
#
# Called by the orchestrator (via tick.md phase wiring) when janus-gate.sh
# returns verdict=FAIL from the forward face. Creates a structured Red Team
# task in the kanban board with the failure context so a Red Team agent can
# review and potentially override if new evidence is genuinely different.
#
# Usage:
#   bash red-team-trigger.sh <evidence_bundle_path> <scar_tissue_path> <janus_forward_json>
#
# Args:
#   evidence_bundle_path  Path to the worker's evidence bundle (JSON)
#   scar_tissue_path      Path to scar-tissue records (objections.jsonl)
#   janus_forward_json    JSON string of the Janus forward face output
#
# Output (stdout): {"action":"dispatch_red_team"|"skip","task_details":{...}}
# Exit code: 0=dispatched, 1=skip, 2=error
#
# Conventions follow prereg-lock.sh / prereg-verify.sh patterns.

set -u

PACK_DIR="$(cd "$(dirname "$0")/../../" && pwd)"
LEDGER_DIR="__HERMES_LEDGER_DIR__"
REPO="__HERMES_REPO_DIR__"
KANBAN_DB="$HOME/.hermes/kanban.db"

# ── Parse args ────────────────────────────────────────────────────────────────
if [ $# -lt 3 ]; then
  echo '{"action":"skip","task_details":{},"error":"Usage: red-team-trigger.sh <evidence_bundle_path> <scar_tissue_path> <janus_forward_json>"}'
  exit 2
fi

EVIDENCE_BUNDLE="$1"
SCAR_TISSUE_PATH="$2"
JANUS_FORWARD_JSON="$3"

# ── Validate evidence bundle exists ────────────────────────────────────────────
if [ ! -f "$EVIDENCE_BUNDLE" ]; then
  echo "{\"action\":\"skip\",\"task_details\":{},\"error\":\"Evidence bundle not found at ${EVIDENCE_BUNDLE}\"}"
  exit 2
fi

# ── Parse Janus forward output ─────────────────────────────────────────────────
FORWARD_VERDICT=$(echo "$JANUS_FORWARD_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('verdict',''))" 2>/dev/null || echo "")

# Only trigger on forward face FAIL
if [ "$FORWARD_VERDICT" != "FAIL" ]; then
  echo '{"action":"skip","task_details":{},"message":"Janus forward verdict is not FAIL — no Red Team dispatch needed"}'
  exit 1
fi

# ── Extract scar-tissue match details from Janus output ────────────────────────
SCAR_MATCHES=$(echo "$JANUS_FORWARD_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
matches = d.get('scar_matches', [])
print(json.dumps(matches))
" 2>/dev/null || echo "[]")

SCAR_MATCH_COUNT=$(echo "$SCAR_MATCHES" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
FORWARD_REASON=$(echo "$JANUS_FORWARD_JSON" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo "\"\"")

# ── Extract evidence bundle info ───────────────────────────────────────────────
EVIDENCE_SUMMARY=$(python3 -c "
import json, sys
try:
    with open('${EVIDENCE_BUNDLE}') as f:
        d = json.load(f)
except Exception:
    d = {}
print(json.dumps({
    'hypothesis_id': d.get('hypothesis_id', d.get('hypothesis', d.get('id', 'unknown'))),
    'task_id': d.get('task_id', d.get('task', 'unknown')),
    'metric_name': d.get('metric_name', d.get('metric', d.get('target_metric', 'unknown'))),
    'worker': d.get('worker', d.get('agent', d.get('model', 'unknown')))
}))
" 2>/dev/null || echo '{"hypothesis_id":"unknown","task_id":"unknown","metric_name":"unknown","worker":"unknown"}')

HYPOTHESIS_ID=$(echo "$EVIDENCE_SUMMARY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('hypothesis_id','unknown'))" 2>/dev/null || echo "unknown")
TASK_ID=$(echo "$EVIDENCE_SUMMARY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('task_id','unknown'))" 2>/dev/null || echo "unknown")
METRIC_NAME=$(echo "$EVIDENCE_SUMMARY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('metric_name','unknown'))" 2>/dev/null || echo "unknown")
WORKER=$(echo "$EVIDENCE_SUMMARY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('worker','unknown'))" 2>/dev/null || echo "unknown")

# Build a list of prior objection IDs from the scar-tissue matches
PRIOR_OBJECTION_IDS=$(echo "$SCAR_MATCHES" | python3 -c "
import json, sys
matches = json.load(sys.stdin)
ids = [m.get('id', 'unknown') for m in matches]
print(json.dumps(ids))
" 2>/dev/null || echo "[]")

# ── Generate unique task ID ────────────────────────────────────────────────────
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
RED_TEAM_TASK_ID="RT-${HYPOTHESIS_ID}-${TIMESTAMP}"

# ── Build Red Team task details ────────────────────────────────────────────────
TASK_DETAILS=$(cat <<JSON_DETAILS
{
  "task_id": "${RED_TEAM_TASK_ID}",
  "type": "red_team_review",
  "trigger": "janus_forward_fail",
  "hypothesis_id": "${HYPOTHESIS_ID}",
  "original_task_id": "${TASK_ID}",
  "metric_name": "${METRIC_NAME}",
  "worker": "${WORKER}",
  "evidence_bundle": "${EVIDENCE_BUNDLE}",
  "scar_tissue_path": "${SCAR_TISSUE_PATH}",
  "scar_match_count": ${SCAR_MATCH_COUNT},
  "prior_objection_ids": ${PRIOR_OBJECTION_IDS},
  "forward_verdict": "FAIL",
  "forward_reason": ${FORWARD_REASON},
  "status": "open",
  "priority": "high",
  "description": "Janus forward face detected hypothesis ${HYPOTHESIS_ID} re-litigates refuted idea(s). Red Team must verify whether the new evidence genuinely differs from prior refutations (objections: $(echo "$PRIOR_OBJECTION_IDS" | python3 -c "import json,sys; print(', '.join(json.load(sys.stdin)))" 2>/dev/null || echo "none")). If evidence is genuinely novel, override the Janus FAIL and proceed. If not, confirm the FAIL and archive the hypothesis."
}
JSON_DETAILS
)

# ── Submit to kanban (if available) ────────────────────────────────────────────
KANBAN_RESULT=""
if command -v python3 &>/dev/null; then
  if [ -f "$KANBAN_DB" ] || [ -d "$HOME/.hermes" ]; then
    KANBAN_RESULT=$(python3 -c "
import json, sys, os

kanban_db = '${KANBAN_DB}'
task_details = json.loads('''${TASK_DETAILS}''')

# Try to write to kanban via SQLite if available
try:
    import sqlite3
    conn = sqlite3.connect(kanban_db)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, type TEXT, data TEXT, status TEXT, created_at TEXT)')
    c.execute(
        'INSERT OR REPLACE INTO tasks (id, type, data, status, created_at) VALUES (?, ?, ?, ?, ?)',
        (
            task_details['task_id'],
            task_details['type'],
            json.dumps(task_details),
            task_details['status'],
            '${TIMESTAMP}'
        )
    )
    conn.commit()
    conn.close()
    print(json.dumps({'kanban_status': 'created', 'kanban_id': task_details['task_id']}))
except Exception as e:
    # Fallback: write to a JSON file
    fallback_dir = '${REPO}/${LEDGER_DIR}/redteam'
    os.makedirs(fallback_dir, exist_ok=True)
    task_file = os.path.join(fallback_dir, 'task-${RED_TEAM_TASK_ID}.json')
    with open(task_file, 'w') as f:
        json.dump(task_details, f, indent=2)
    print(json.dumps({'kanban_status': 'fallback_file', 'kanban_id': task_details['task_id'], 'file': task_file}))
" 2>/dev/null)
  else
    KANBAN_RESULT='{"kanban_status":"no_kanban","kanban_id":"'${RED_TEAM_TASK_ID}'","note":"~/.hermes not found — task details recorded but not submitted to kanban"}'
  fi
else
  KANBAN_RESULT='{"kanban_status":"no_python","kanban_id":"'${RED_TEAM_TASK_ID}'","note":"python3 not available — cannot submit to kanban"}'
fi

# ── Output JSON ────────────────────────────────────────────────────────────────
cat <<JSON
{
  "action": "dispatch_red_team",
  "task_details": ${TASK_DETAILS},
  "kanban_result": ${KANBAN_RESULT}
}
JSON

exit 0
