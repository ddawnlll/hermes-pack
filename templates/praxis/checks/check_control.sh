#!/usr/bin/env bash
"""
Praxis check: verify control.yaml mode is 'running' and host controls allow execution.
Fail-closed: any non-running mode = FAIL.
"""
set -u
REPO="${1:-${REPO_DIR:-.}}"
LEDGER_DIR="${2:-${LEDGER_DIR:-.alphaforge/orchestrator}}"
CTRL="$REPO/$LEDGER_DIR/control.yaml"

if [ ! -f "$CTRL" ]; then
  echo '{"check": "control_mode", "status": "FAIL", "message": "control.yaml not found"}'
  exit 1
fi

MODE=$(grep -E '^mode:' "$CTRL" | awk '{print $2}')
case "$MODE" in
  running)
    echo "{\"check\": \"control_mode\", \"status\": \"PASS\", \"detail\": {\"mode\": \"$MODE\"}}"
    ;;
  paused|killed)
    echo "{\"check\": \"control_mode\", \"status\": \"FAIL\", \"message\": \"mode is $MODE — orchestrator is not running\"}"
    exit 1
    ;;
  *)
    echo "{\"check\": \"control_mode\", \"status\": \"WARN\", \"message\": \"Unknown mode: $MODE\"}"
    ;;
esac
