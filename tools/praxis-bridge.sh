#!/usr/bin/env bash
# Praxis Bridge — Hermes Pack ⟶ real Praxis CLI integration
# ===========================================================
# This is the ONLY file in Hephaestus that calls the Praxis Truth Kernel.
# All Praxix gate logic lives in the ddawnlll/praxis submodule.
# Hermes Pack does NOT reimplement any gate logic.
#
# Usage:
#   bash tools/praxis-bridge.sh verify --plan <plan.yaml>      # Run all 6 gates
#   bash tools/praxis-bridge.sh status [--json]                 # Show latest verdict
#   bash tools/praxis-bridge.sh report <run-id>                 # Show audit report
#   bash tools/praxis-bridge.sh init [--plan <path>]            # Create plan spec
#   bash tools/praxis-bridge.sh plan-validate --plan <plan.yaml> # Validate plan
#
# Exit codes: 0=PASS, 1=HOLD, 2=FAIL, 3=error
set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRAXIS_DIR="${SCRIPT_DIR}/praxis"

# Find the praxis CLI — prefer local install, fallback to bun/ts from submodule
find_praxis_cli() {
  # 1. Check if praxis is globally installed
  if command -v praxis &>/dev/null; then
    echo "praxis"
    return 0
  fi

  # 2. Check for bun + local package
  if [ -f "${PRAXIS_DIR}/packages/cli/src/cli.ts" ] && command -v bun &>/dev/null; then
    echo "bun run --cwd ${PRAXIS_DIR}/packages/cli src/cli.ts"
    return 0
  fi

  # 3. Check for node_modules/.bin
  if [ -f "${PRAXIS_DIR}/packages/cli/node_modules/.bin/praxis" ]; then
    echo "${PRAXIS_DIR}/packages/cli/node_modules/.bin/praxis"
    return 0
  fi

  return 1
}

PRAXIS_CMD=$(find_praxis_cli)
if [ $? -ne 0 ]; then
  echo "[praxis-bridge] ERROR: praxis CLI not found."
  echo "[praxis-bridge] Install: cd tools/praxis && bun install"
  echo "[praxis-bridge] Or global: npm install -g @praxis/cli"
  exit 3
fi

COMMAND="${1:-}"
shift 2>/dev/null || true

case "$COMMAND" in
  verify)
    echo "[praxis-bridge] 🔍 Running Praxis Truth Kernel verification..."
    echo "[praxis-bridge] Using: $PRAXIS_CMD"
    $PRAXIS_CMD verify "$@" --json 2>&1
    EXIT_CODE=$?
    case $EXIT_CODE in
      0) echo "[praxis-bridge] ✅ Praxis PASS — all gates passed" ;;
      1) echo "[praxis-bridge] ⚠️  Praxis HOLD — some gates held" ;;
      2) echo "[praxis-bridge] ❌ Praxis FAIL — gates failed" ;;
      *) echo "[praxis-bridge] ❌ Praxis ERROR" ;;
    esac
    exit $EXIT_CODE
    ;;

  init)
    $PRAXIS_CMD init "$@"
    ;;

  plan-validate)
    $PRAXIS_CMD plan validate "$@" --json
    ;;

  plan-lock)
    $PRAXIS_CMD plan lock "$@" --json
    ;;

  status)
    $PRAXIS_CMD status "$@" --json
    ;;

  report)
    $PRAXIS_CMD report show --run-id "${1:-}" --json
    ;;

  repair)
    $PRAXIS_CMD repair show --run-id "${1:-}" --json
    ;;

  ledger)
    $PRAXIS_CMD ledger show "$@"
    ;;

  *)
    echo "Usage: $0 <command> [args]"
    echo "Commands: verify, init, plan-validate, plan-lock, status, report, repair, ledger"
    exit 3
    ;;
esac
