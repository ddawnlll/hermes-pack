#!/usr/bin/env bash
# Pre-registration verify — $0 evidence gate.
# Called at verify time (before T1). Reads the prereg lock file created at
# dispatch time and compares the reported metric/threshold from evidence
# with the locked values. A mismatch means the worker changed its metric
# after seeing results (p-hacking) → FAIL.
#
# Usage:
#   bash prereg-verify.sh <task_id> <reported_metric_name> <reported_direction> <reported_threshold>
#
# The script reads <ledger>/prereg/<task_id>.lock and compares.
#
# Output (stdout): {"verdict":"PASS"|"FAIL","expected":{"metric_name":"...","direction":"...","threshold":"..."},"reported":{"metric_name":"...","direction":"...","threshold":"..."},"error":"..."}
# Exit code: 0=PASS, 1=FAIL, 2=error

set -u

PACK_DIR="$(cd "$(dirname "$0")/../../" && pwd)"
LEDGER_DIR="__HERMES_LEDGER_DIR__"
REPO="__HERMES_REPO_DIR__"

PREREG_DIR="$REPO/$LEDGER_DIR/prereg"

# ── Parse args ────────────────────────────────────────────────────────────────
if [ $# -lt 4 ]; then
  echo '{"verdict":"FAIL","expected":{},"reported":{},"error":"Usage: prereg-verify.sh <task_id> <reported_metric_name> <reported_direction> <reported_threshold>"}'
  exit 2
fi

TASK_ID="$1"
REPORTED_METRIC="$2"
REPORTED_DIRECTION="$3"
REPORTED_THRESHOLD="$4"

# ── Read lock file ─────────────────────────────────────────────────────────────
LOCK_FILE="${PREREG_DIR}/${TASK_ID}.lock"
if [ ! -f "$LOCK_FILE" ]; then
  echo "{\"verdict\":\"FAIL\",\"expected\":{},\"reported\":{\"metric_name\":\"${REPORTED_METRIC}\",\"direction\":\"${REPORTED_DIRECTION}\",\"threshold\":\"${REPORTED_THRESHOLD}\"},\"error\":\"Lock file not found at ${LOCK_FILE}. Was prereg-lock.sh run at dispatch time?\"}"
  exit 1
fi

# Source the lock file to get variables
HYPOTHESIS_ID=""
EXPECTED_METRIC=""
EXPECTED_DIRECTION=""
EXPECTED_THRESHOLD=""
LOCK_TIMESTAMP=""
LOCK_TASK_ID=""
LOCK_SHA256=""

while IFS='=' read -r key value; do
  case "$key" in
    hypothesis_id) HYPOTHESIS_ID="$value" ;;
    metric_name) EXPECTED_METRIC="$value" ;;
    direction) EXPECTED_DIRECTION="$value" ;;
    threshold) EXPECTED_THRESHOLD="$value" ;;
    timestamp) LOCK_TIMESTAMP="$value" ;;
    task_id) LOCK_TASK_ID="$value" ;;
    sha256) LOCK_SHA256="$value" ;;
  esac
done < "$LOCK_FILE"

# ── Verify tamper detection: recompute hash over content before sha256= line ───
CANONICAL=$(grep -v '^sha256=' "$LOCK_FILE" | head -6)
COMPUTED_SHA256=$(printf '%s' "$CANONICAL" | sha256sum | cut -d' ' -f1)

if [ "$COMPUTED_SHA256" != "$LOCK_SHA256" ]; then
  echo "{\"verdict\":\"FAIL\",\"expected\":{\"metric_name\":\"${EXPECTED_METRIC}\",\"direction\":\"${EXPECTED_DIRECTION}\",\"threshold\":\"${EXPECTED_THRESHOLD}\"},\"reported\":{\"metric_name\":\"${REPORTED_METRIC}\",\"direction\":\"${REPORTED_DIRECTION}\",\"threshold\":\"${REPORTED_THRESHOLD}\"},\"error\":\"LOCK FILE TAMPERED: computed sha256=${COMPUTED_SHA256} does not match recorded ${LOCK_SHA256}\"}"
  exit 1
fi

# ── Build expected JSON ────────────────────────────────────────────────────────
build_json_str() {
  local val="$1"
  # Escape quotes in the value
  val="${val//\"/\\\"}"
  printf '%s' "$val"
}

EXPECTED_JSON="{\"metric_name\":\"$(build_json_str "$EXPECTED_METRIC")\",\"direction\":\"$(build_json_str "$EXPECTED_DIRECTION")\",\"threshold\":\"$(build_json_str "$EXPECTED_THRESHOLD")\"}"
REPORTED_JSON="{\"metric_name\":\"$(build_json_str "$REPORTED_METRIC")\",\"direction\":\"$(build_json_str "$REPORTED_DIRECTION")\",\"threshold\":\"$(build_json_str "$REPORTED_THRESHOLD")\"}"

# ── Compare ────────────────────────────────────────────────────────────────────
MISMATCHES=""
if [ "$EXPECTED_METRIC" != "$REPORTED_METRIC" ]; then
  MISMATCHES="${MISMATCHES}metric_name "
fi
if [ "$EXPECTED_DIRECTION" != "$REPORTED_DIRECTION" ]; then
  MISMATCHES="${MISMATCHES}direction "
fi
if [ "$EXPECTED_THRESHOLD" != "$REPORTED_THRESHOLD" ]; then
  MISMATCHES="${MISMATCHES}threshold "
fi

if [ -n "$MISMATCHES" ]; then
  cat <<JSON
{"verdict":"FAIL","expected":${EXPECTED_JSON},"reported":${REPORTED_JSON},"error":"Pre-registration mismatch on fields: ${MISMATCHES}"}
JSON
  exit 1
fi

# ── PASS ───────────────────────────────────────────────────────────────────────
cat <<JSON
{"verdict":"PASS","expected":${EXPECTED_JSON},"reported":${REPORTED_JSON},"error":""}
JSON
exit 0
