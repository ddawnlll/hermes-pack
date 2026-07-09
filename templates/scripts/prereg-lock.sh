#!/usr/bin/env bash
# Pre-registration lock — anti-p-hacking gate.
# Called at dispatch time BEFORE the worker runs. Creates a signed lock file
# recording the metric the worker promises to report. After the worker finishes,
# prereg-verify.sh checks that the reported metric matches the locked value.
#
# Usage:
#   bash prereg-lock.sh <task_id> <hypothesis_id> <metric_name> <direction> <threshold>
#
# Example:
#   bash prereg-lock.sh "T42" "H7" "accuracy" ">=" "0.85"
#
# Output (stdout): {"verdict":"PASS","lock_file_path":"...","sha256":"...","message":"..."}
# Exit code: 0 on success, 1 on error

set -u

PACK_DIR="$(cd "$(dirname "$0")/../../" && pwd)"
LEDGER_DIR="__HERMES_LEDGER_DIR__"
REPO="__HERMES_REPO_DIR__"

PREREG_DIR="$REPO/$LEDGER_DIR/prereg"
mkdir -p "$PREREG_DIR"

# ── Parse args ────────────────────────────────────────────────────────────────
if [ $# -lt 5 ]; then
  echo '{"verdict":"FAIL","error":"Usage: prereg-lock.sh <task_id> <hypothesis_id> <metric_name> <direction> <threshold>"}'
  exit 1
fi

TASK_ID="$1"
HYPOTHESIS_ID="$2"
METRIC_NAME="$3"
DIRECTION="$4"
THRESHOLD="$5"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Validate direction
if [ "$DIRECTION" != ">=" ] && [ "$DIRECTION" != "<=" ] && [ "$DIRECTION" != ">" ] && [ "$DIRECTION" != "<" ] && [ "$DIRECTION" != "==" ] && [ "$DIRECTION" != "!=" ]; then
  echo "{\"verdict\":\"FAIL\",\"error\":\"Invalid direction '${DIRECTION}'. Must be one of: >=, <=, >, <, ==, !=\"}"
  exit 1
fi

# ── Build lock content ─────────────────────────────────────────────────────────
LOCK_FILE="${PREREG_DIR}/${TASK_ID}.lock"
LOCK_CONTENT="hypothesis_id=${HYPOTHESIS_ID}
metric_name=${METRIC_NAME}
direction=${DIRECTION}
threshold=${THRESHOLD}
timestamp=${TIMESTAMP}
task_id=${TASK_ID}"

# ── Write lock file ────────────────────────────────────────────────────────────
printf '%s\n' "$LOCK_CONTENT" > "$LOCK_FILE"

# ── Compute SHA-256 hash over canonical content ────────────────────────────────
SHA256=$(printf '%s' "$LOCK_CONTENT" | sha256sum | cut -d' ' -f1)

# Append hash to lock file for tamper detection
echo "sha256=${SHA256}" >> "$LOCK_FILE"

# ── Output JSON ────────────────────────────────────────────────────────────────
cat <<JSON
{"verdict":"PASS","lock_file_path":"${LOCK_FILE}","sha256":"${SHA256}","message":"Pre-registration locked for ${HYPOTHESIS_ID} metric ${METRIC_NAME}${DIRECTION}${THRESHOLD}"}
JSON
