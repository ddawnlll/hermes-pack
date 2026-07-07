#!/usr/bin/env bash
# Praxis Verification Gateway
# ============================
# Runs all enabled checks against a worker's evidence bundle and produces
# a gate_result.json verdict. Fail-closed: any error check = FAIL.
#
# Usage:
#   bash praxis-verify.sh <run_id> [--evidence <path>] [--schema <path>] [--config <path>]
#
# Output: writes gate_result.json to <ledger>/evidence/<run_id>/gate_result.json
set -u
set -o pipefail

RUN_ID="${1:-}"
EVIDENCE_BUNDLE="${2:-}"
SCHEMA_DIR="${3:-}"
LEDGER_DIR="${4:-}"

# ---- Resolve paths ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="${REPO_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo ".")}"
LEDGER_DIR="${LEDGER_DIR:-${REPO_DIR}/.alphaforge/orchestrator}"
EVIDENCE_DIR="${LEDGER_DIR}/evidence/${RUN_ID}"
SCHEMA_DIR="${SCHEMA_DIR:-${SCRIPT_DIR}/schemas}"
CHECKS_DIR="${SCRIPT_DIR}/checks"

mkdir -p "$EVIDENCE_DIR"

# Default paths if not provided
EVIDENCE_BUNDLE="${EVIDENCE_BUNDLE:-${EVIDENCE_DIR}/evidence_bundle.json}"
EVIDENCE_SCHEMA="${SCHEMA_DIR}/evidence_bundle.schema.json"
RESULT_FILE="${EVIDENCE_DIR}/gate_result.json"

# ---- Control flags ----
FAILED_CHECKS=()
PASSED_CHECKS=()
WARN_CHECKS=()
BLOCKING=true  # fail-closed by default

echo "[praxis] Verifying run: $RUN_ID"
echo "[praxis] Evidence bundle: $EVIDENCE_BUNDLE"
echo "[praxis] LEDGER: $LEDGER_DIR"

# ---- Pre-checks ----
if [ ! -f "$EVIDENCE_BUNDLE" ]; then
  NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  cat > "$RESULT_FILE" <<ENDJSON
{
  "run_id": "$RUN_ID",
  "status": "FAIL",
  "gate": "T0",
  "checked_at": "$NOW",
  "checks_passed": [],
  "checks_failed": [{"check": "evidence_missing", "message": "Evidence bundle not found: $EVIDENCE_BUNDLE", "severity": "error"}],
  "next_action": "reject_without_llm"
}
ENDJSON
  cat "$RESULT_FILE"
  exit 1
fi

# ---- Run all checks ----
run_check() {
  local check_name="$1"
  local cmd="$2"
  echo "[praxis]   running: $check_name"
  local output
  output=$($cmd 2>&1)
  local exit_code=$?
  local status
  status=$(echo "$output" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','FAIL'))" 2>/dev/null || echo "FAIL")

  case "$status" in
    PASS)
      PASSED_CHECKS+=("$(echo "$output")")
      echo "[praxis]   ✓ $check_name PASS"
      ;;
    WARN)
      WARN_CHECKS+=("$(echo "$output")")
      echo "[praxis]   ⚠ $check_name WARN"
      ;;
    FAIL|ERROR)
      FAILED_CHECKS+=("$(echo "$output")")
      echo "[praxis]   ✗ $check_name FAIL"
      ;;
  esac
  return $exit_code
}

# 1. Control mode check
run_check "control_mode" "bash ${CHECKS_DIR}/check_control.sh ${REPO_DIR} ${LEDGER_DIR}"

# 2. Schema validation
run_check "evidence_schema" "python3 ${CHECKS_DIR}/check_schema.py ${EVIDENCE_BUNDLE} ${EVIDENCE_SCHEMA}"

# 3. Forbidden paths
FORBIDDEN_CONFIG="${LEDGER_DIR}/control.yaml"
run_check "forbidden_paths" "python3 ${CHECKS_DIR}/check_paths.py ${EVIDENCE_BUNDLE} ${FORBIDDEN_CONFIG}"

# 4. Memory write check
run_check "memory_write" "python3 ${CHECKS_DIR}/check_memory.py ${EVIDENCE_BUNDLE}"

# 5. Data lineage
run_check "data_lineage" "python3 ${CHECKS_DIR}/check_lineage.py ${EVIDENCE_BUNDLE}"

# 6. Branch pushed (skip if no remote configured)
if git remote -v 2>/dev/null | grep -q origin; then
  run_check "branch_pushed" "python3 ${CHECKS_DIR}/check_branch.py ${REPO_DIR} ${EVIDENCE_BUNDLE}"
fi

# 7. Metrics sanity (conditional on metrics existing)
METRICS_EXIST=$(python3 -c "import json; b=json.load(open('${EVIDENCE_BUNDLE}')); print('yes' if b.get('metrics') else 'no')" 2>/dev/null || echo "no")
if [ "$METRICS_EXIST" = "yes" ]; then
  run_check "metrics_sanity" "python3 ${CHECKS_DIR}/check_metrics.py ${EVIDENCE_BUNDLE}"
fi

# 8. Negative control (if risk level available)
RISK_LEVEL=$(python3 -c "
import json,sys
try:
  task_path='${LEDGER_DIR}/task_contracts/current.yaml'
  import yaml
  with open(task_path) as f: task=yaml.safe_load(f)
  print(task.get('risk_level','low'))
except: print('low')
" 2>/dev/null || echo "low")
run_check "negative_control" "python3 ${CHECKS_DIR}/check_negative_control.py ${EVIDENCE_BUNDLE} ${RISK_LEVEL}"

# 9. Budget check
run_check "budget" "python3 ${CHECKS_DIR}/check_budget.py ${EVIDENCE_BUNDLE}"

# ---- Determine verdict ----
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TOTAL_CHECKS=$((${#PASSED_CHECKS[@]} + ${#FAILED_CHECKS[@]} + ${#WARN_CHECKS[@]}))

if [ ${#FAILED_CHECKS[@]} -gt 0 ]; then
  STATUS="FAIL"
  NEXT_ACTION="reject_without_llm"
elif [ ${#WARN_CHECKS[@]} -gt 0 ] && [ ${#PASSED_CHECKS[@]} -eq 0 ]; then
  STATUS="BLOCKED"
  NEXT_ACTION="human_review"
else
  STATUS="PASS"
  NEXT_ACTION="proceed_t1"
fi

# ---- Compute evidence summary ----
SUMMARY=$(python3 -c "
import json
bundle = json.load(open('${EVIDENCE_BUNDLE}'))
claims = bundle.get('claims',[])
commands = bundle.get('commands',[])
diff = bundle.get('diff',{})
print(json.dumps({
  'total_claims': len(claims),
  'claims_with_evidence': sum(1 for c in claims if c.get('evidence')),
  'claims_without_evidence': sum(1 for c in claims if not c.get('evidence')),
  'files_changed': len(diff.get('changed_files',[])),
  'forbidden_touches': len(diff.get('forbidden_files_touched',[])),
  'tests_run': len(commands),
  'tests_passed': sum(1 for c in commands if c.get('exit_code')==0),
  'tests_failed': sum(1 for c in commands if c.get('exit_code',-1)!=0),
}))
")

# ---- Write gate_result.json ----
MEMORY_CANDIDATES="[]"
if [ "$STATUS" = "PASS" ]; then
  MEMORY_CANDIDATES=$(python3 -c "
import json
bundle = json.load(open('${EVIDENCE_BUNDLE}'))
candidates = []
for c in bundle.get('claims',[]):
  if c.get('confidence') in ('high','medium') and c.get('evidence'):
    candidates.append({'fact': c['claim'], 'source': c['evidence'][0] if c['evidence'] else '', 'confidence': 1.0 if c.get('confidence')=='high' else 0.7})
print(json.dumps(candidates[:5]))
")
fi

cat > "$RESULT_FILE" <<ENDJSON
{
  "run_id": "$RUN_ID",
  "status": "$STATUS",
  "gate": "T0",
  "checked_at": "$NOW",
  "checks_total": $TOTAL_CHECKS,
  "checks_passed": $(printf '%s\n' "${PASSED_CHECKS[@]}" | jq -s '.' 2>/dev/null || echo "[]"),
  "checks_failed": $(printf '%s\n' "${FAILED_CHECKS[@]}" | jq -s '.' 2>/dev/null || echo "[]"),
  "evidence_summary": $SUMMARY,
  "next_action": "$NEXT_ACTION",
  "memory_write_candidates": $MEMORY_CANDIDATES
}
ENDJSON

echo ""
echo "[praxis] ═══════════════════════════════════════════"
echo "[praxis]   Verdict: $STATUS"
echo "[praxis]   Checks:  ${#PASSED_CHECKS[@]} passed, ${#FAILED_CHECKS[@]} failed, ${#WARN_CHECKS[@]} warnings"
echo "[praxis]   Action:  $NEXT_ACTION"
echo "[praxis]   Result:  $RESULT_FILE"
echo "[praxis] ═══════════════════════════════════════════"

if [ "$STATUS" = "FAIL" ]; then
  exit 1
fi
exit 0
