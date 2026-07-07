#!/usr/bin/env bash
# ============================================================================
# Money Radar adapter setup — stub for future implementation
# Args: <repo-dir> <adapter-name> <dry-run> <hermes-root> <pack-dir> <adapter-dir>
# ============================================================================
set -euo pipefail

REPO_DIR="$1"
ADAPTER="$2"
DRY_RUN="$3"
HERMES_ROOT="$4"
PACK_DIR="$5"
ADAPTER_DIR="$6"

say()  { printf '\033[1;32m[money-radar]\033[0m %s\n' "$*"; }
dry()  { printf '\033[1;34m[money-radar] DRY-RUN:\033[0m %s\n' "$*"; }

BOARD_NAME="money-radar"
DELIVERY="local"

# Kanban board only (profiles and crons will be defined when implemented)
if [ "$DRY_RUN" = "true" ]; then
  dry "hermes kanban boards create $BOARD_NAME (if missing)"
else
  if hermes kanban boards list 2>/dev/null | grep -q "$BOARD_NAME"; then
    say "kanban board '$BOARD_NAME' exists"
  else
    hermes kanban boards create "$BOARD_NAME" \
      --name "Money Radar" \
      --description "Opportunity discovery board" \
      --switch
    say "kanban board '$BOARD_NAME' created"
  fi
fi

say "Money Radar stub setup complete"
say "TODO: Add profiles, cron jobs, and pipelines when money-radar repo is created"
