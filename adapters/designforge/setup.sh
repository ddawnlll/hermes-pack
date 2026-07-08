#!/usr/bin/env bash
# ============================================================================
# DesignForge adapter setup — called by Hephaestus bootstrap.sh
# Args: <repo-dir> <adapter-name> <dry-run> <hermes-root> <pack-dir> <adapter-dir>
# ============================================================================
set -euo pipefail

REPO_DIR="$1"
ADAPTER="$2"
DRY_RUN="$3"        # "true" or "false"
HERMES_ROOT="$4"
PACK_DIR="$5"
ADAPTER_DIR="$6"

say()  { printf '\033[1;32m[designforge]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[designforge] WARN:\033[0m %s\n' "$*"; }
dry()  { printf '\033[1;34m[designforge] DRY-RUN:\033[0m %s\n' "$*"; }

PROFILE_DESIGNER="designforge-designer"
PROFILE_JUDGE="designforge-judge"
BOARD_NAME="designforge"
DELIVERY="local"

# ---- Profiles ----
install_profile() {
  local name="$1" config_tpl="$2" soul_file="$3"
  local dir="$HERMES_ROOT/profiles/$name"
  local soul_src="$ADAPTER_DIR/$soul_file"
  if [ "$DRY_RUN" = "true" ]; then
    dry "install profile '$name':"
    dry "  hermes profile create $name (if missing)"
    dry "  cp $config_tpl $dir/config.yaml"
    dry "  cp $soul_src $dir/SOUL.md"
    return
  fi
  if [ ! -d "$dir" ]; then
    hermes profile create "$name" --description "DesignForge profile: $name" 2>&1 || {
      warn "hermes profile create $name failed — creating directory manually"
      mkdir -p "$dir"
    }
  fi
  mkdir -p "$dir"
  cp "$PACK_DIR/templates/config.orchestrator.yaml" "$dir/config.yaml" 2>/dev/null || true
  cp "$soul_src" "$dir/SOUL.md"
  say "profile installed: $name"
}

install_profile "$PROFILE_DESIGNER" "templates/config.orchestrator.yaml" "SOUL.designer.md"
install_profile "$PROFILE_JUDGE" "templates/config.orchestrator.yaml" "SOUL.design-judge.md"

# ---- Kanban board ----
if [ "$DRY_RUN" = "true" ]; then
  dry "hermes kanban boards create $BOARD_NAME (if missing)"
else
  if hermes kanban boards list 2>/dev/null | grep -q "$BOARD_NAME"; then
    say "kanban board '$BOARD_NAME' exists"
  else
    hermes kanban boards create "$BOARD_NAME" \
      --name "DesignForge" \
      --description "DesignForge orchestration & outreach pipeline" \
      --switch
    say "kanban board '$BOARD_NAME' created and set current"
  fi
fi

# ---- Cron jobs ----
create_cron() {
  local name="$1" schedule="$2" prompt_file="$3" script_name="$4"
  local prompt_path="$ADAPTER_DIR/$prompt_file"
  if [ ! -f "$prompt_path" ]; then
    warn "prompt not found: $prompt_path — skipping cron '$name'"
    return
  fi
  local prompt
  prompt=$(cat "$prompt_path")
  if [ "$DRY_RUN" = "true" ]; then
    dry "hermes cron create '$schedule' '$name' --workdir $REPO_DIR --deliver $DELIVERY"
    return
  fi
  if hermes cron list 2>/dev/null | grep -q "$name"; then
    say "cron job '$name' exists — updating"
    hermes cron edit "$name" --schedule "$schedule" --prompt "$prompt" 2>/dev/null || \
      warn "cron edit failed for $name — update manually"
  else
    hermes cron create "$schedule" "$prompt" \
      --name "$name" \
      --workdir "$REPO_DIR" \
      --deliver "$DELIVERY" || warn "cron create failed for $name"
    say "cron job '$name' created ($schedule)"
  fi
}

create_cron "designforge-lead-discovery" "0 9 * * *" "prompts/lead-discovery.md" ""
create_cron "designforge-draft-create" "0 10 * * *" "prompts/draft-create.md" ""
create_cron "designforge-reply-monitor" "0 */2 * * 1-5" "prompts/reply-monitor.md" ""

# ---- Gateway ----
if [ "$DRY_RUN" != "true" ]; then
  if ! hermes cron status >/dev/null 2>&1; then
    say "installing gateway service"
    hermes gateway install 2>/dev/null || warn "gateway install failed (may already be installed)"
  fi
fi

say "DesignForge setup complete"
echo ""
say "Next steps:"
say "  1. Verify profiles: hermes profile list | grep designforge"
say "  2. Verify crons:    hermes cron list"
say "  3. Check kanban:    hermes kanban boards show"
echo ""
