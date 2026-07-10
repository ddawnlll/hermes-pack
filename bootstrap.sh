#!/usr/bin/env bash
# ============================================================================
# Hermes Orchestrator Pack — generic bootstrap
# Idempotent: safe to re-run after editing templates or adapters.
# Usage:
#   bash bootstrap.sh --help
#   bash bootstrap.sh --dry-run <repo-dir> --adapter <name>
#   bash bootstrap.sh <repo-dir> --adapter <name>
# ============================================================================
set -euo pipefail

# ----------------------------- defaults -------------------------------------
DRY_RUN=false
ADAPTER=""
REPO_DIR=""
HERMES_HOME="${HERMES_HOME:-}"  # auto-detected from Hermes if not set
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_ROOT=""  # detected at runtime from `hermes profile show default`
HERMES_SCRIPTS="$HOME/.hermes/scripts"  # cron --script looks here

# ----------------------------- built-in defaults ----------------------------
DF_PROJECT_NAME="HermesProject"
DF_OBJECTIVE="Improve the project through evidence-backed iteration."
DF_BOARD_NAME="hermes-board"
DF_BOARD_DESC="Hermes orchestration board"
DF_PROFILE_ORCH="orchestrator"
DF_PROFILE_WORKER_PREFIX="worker"
DF_WORKER_COUNT=2
DF_TICK_NAME="orchestrator-tick"
DF_TICK_SCHEDULE="every 1h"
DF_DELIVERY="local"
DF_ORCH_PROVIDER="anthropic"
DF_ORCH_MODEL="__NEEDS_LOCAL_VERIFICATION__"
DF_WORKER_PROVIDER="openrouter"
DF_WORKER_MODEL="__NEEDS_LOCAL_VERIFICATION__"
DF_LEDGER_DIR=".orchestrator"
DF_ALLOWED='  - src/'
DF_FORBIDDEN='  - vendor/'
DF_SETUP_MODE="orchestrator"   # orchestrator | custom
DF_MERGE="pr_only"
DF_MAX_PARALLEL=3
DF_MAX_SPEND=25

# Challenger / Arbiter defaults
DF_CHALLENGER_MODEL="openrouter/mistralai/mistral-small"
DF_CHALLENGER_CHAIN_0="mistralai/mistral-small"
DF_CHALLENGER_CHAIN_1="ollama/llama3"
DF_CHALLENGER_CHAIN_2=""
DF_ARBITER_MODEL="anthropic/claude-sonnet-4-20250514"
DF_ARBITER_CHAIN_0="claude-sonnet-4-20250514"
DF_ARBITER_CHAIN_1="deepseek/deepseek-chat"
DF_ARBITER_CHAIN_2="ollama/llama3"
DF_PROFILE_CHALLENGER="challenger"
DF_PROFILE_ARBITER="arbiter"

# Reflector defaults
DF_REFLECTOR_MODEL="openrouter/deepseek/deepseek-chat"
DF_REFLECTOR_CHAIN_0="deepseek/deepseek-chat"
DF_REFLECTOR_CHAIN_1="ollama/llama3"
DF_REFLECTOR_CHAIN_2=""
DF_PROFILE_REFLECTOR="reflector"

# ----------------------------- helpers --------------------------------------
say()  { printf '\033[1;32m[hermes-setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[hermes-setup] WARN:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[hermes-setup] FATAL:\033[0m %s\n' "$*"; exit 1; }
dry()  { printf '\033[1;34m[hermes-setup] DRY-RUN:\033[0m %s\n' "$*"; }

detect_hermes_root() {
  # Determine the Hermes runtime directory (where profiles/ config.yaml live)
  # by parsing `hermes profile show default`.
  local path_line
  path_line=$(hermes profile show default 2>/dev/null | grep 'Path:' | head -1 | sed 's/.*Path:\s*//' | tr -d '\r')
  if [ -n "$path_line" ] && [ -d "$path_line" ]; then
    echo "$path_line"
  elif [ -n "$HERMES_HOME" ] && [ -d "$HERMES_HOME/profiles" ]; then
    echo "$HERMES_HOME"
  else
    # Fallback: check common locations
    for candidate in "$HOME/.hermes" "/c/Users/$USER/AppData/Local/hermes" "$HOME/AppData/Local/hermes"; do
      [ -d "$candidate/profiles" ] && { echo "$candidate"; return; }
    done
    echo ""
  fi
}

extract_str() {
  local file="$1" key="$2" default="$3"
  local val
  val=$(grep -E "^\\s+${key}:\\s+" "$file" 2>/dev/null | head -1 | sed "s/.*${key}:\\s*//" | sed 's/^"//;s/"$//' | sed "s/^'//;s/'$//")
  echo "${val:-$default}"
}

extract_yaml_list() {
  local file="$1" key="$2"
  awk -v k="$key" '
    $0 ~ "^  " k ":" { found=1; next }
    found && /^  [a-z]/ { found=0 }
    found && /^    - / {
      sub(/^    /, "  ")
      print
    }
  ' "$file" 2>/dev/null
}

load_adapter() {
  local name="$1"
  local dir="$HERE/adapters/$name"
  local file="$dir/project.yaml"
  [ -d "$dir" ] || die "Adapter '$name' not found at $dir"
  [ -f "$file" ] || die "Adapter '$name' has no project.yaml (expected: $file)"
  say "loaded adapter: $name ($file)"

  PROJECT_NAME=$(extract_str "$file" "name" "$DF_PROJECT_NAME")
  OBJECTIVE=$(extract_str "$file" "objective" "$DF_OBJECTIVE")
  BOARD_NAME=$(extract_str "$file" "board_name" "$DF_BOARD_NAME")
  BOARD_DESC=$(extract_str "$file" "board_desc" "$DF_BOARD_DESC")
  PROFILE_ORCH=$(extract_str "$file" "profile_orchestrator" "$DF_PROFILE_ORCH")
  PROFILE_WORKER_PREFIX=$(extract_str "$file" "profile_worker_prefix" "$DF_PROFILE_WORKER_PREFIX")
  WORKER_COUNT=$(extract_str "$file" "worker_count" "$DF_WORKER_COUNT")
  TICK_NAME=$(extract_str "$file" "tick_name" "$DF_TICK_NAME")
  TICK_SCHEDULE=$(extract_str "$file" "tick_schedule" "$DF_TICK_SCHEDULE")
  DELIVERY=$(extract_str "$file" "delivery" "$DF_DELIVERY")
  ORCH_PROVIDER=$(extract_str "$file" "orchestrator" "$DF_ORCH_PROVIDER")
  ORCH_MODEL=$(extract_str "$file" "orchestrator_model" "$DF_ORCH_MODEL")
  WORKER_PROVIDER=$(extract_str "$file" "worker" "$DF_WORKER_PROVIDER")
  WORKER_MODEL=$(extract_str "$file" "worker_model" "$DF_WORKER_MODEL")
  LEDGER_DIR=$(extract_str "$file" "ledger" "$DF_LEDGER_DIR")
  SETUP_MODE=$(extract_str "$file" "setup_mode" "$DF_SETUP_MODE")
  MERGE=$(extract_str "$file" "merge_policy" "$DF_MERGE")
  MAX_PARALLEL=$(extract_str "$file" "max_parallel_workers" "$DF_MAX_PARALLEL")
  MAX_SPEND=$(extract_str "$file" "max_llm_spend_per_day_usd" "$DF_MAX_SPEND")

  # ── Challenger / Arbiter extraction ───────────────────────────────────────
  CHALLENGER_MODEL=$(extract_str "$file" "challenger_model" "$DF_CHALLENGER_MODEL")
  # If challenger field exists (separate provider), use it; else infer from model
  local chal_prov
  chal_prov=$(extract_str "$file" "challenger" "")
  if [ -n "$chal_prov" ]; then
    CHALLENGER_PROVIDER="$chal_prov"
  else
    CHALLENGER_PROVIDER="${CHALLENGER_MODEL%%/*}"
  fi
  ARBITER_MODEL=$(extract_str "$file" "arbiter_model" "$DF_ARBITER_MODEL")
  local arb_prov
  arb_prov=$(extract_str "$file" "arbiter" "")
  if [ -n "$arb_prov" ]; then
    ARBITER_PROVIDER="$arb_prov"
  else
    ARBITER_PROVIDER="${ARBITER_MODEL%%/*}"
  fi
  PROFILE_CHALLENGER=$(extract_str "$file" "profile_challenger" "$DF_PROFILE_CHALLENGER")
  PROFILE_ARBITER=$(extract_str "$file" "profile_arbiter" "$DF_PROFILE_ARBITER")

  # ── Chain extraction (for litellm-config.yaml) ────────────────────────────
  compute_chain_vars() {
    local prefix="$1"  # e.g. CHALLENGER or ARBITER
    local raw_chain
    raw_chain=$(extract_yaml_list "$file" "${prefix,,}_chain" 2>/dev/null || echo "")
    if [ -z "$raw_chain" ]; then
      # Use defaults, injected via eval
      return
    fi
    # Parse chain items into numbered variables
    local i=0
    while IFS= read -r line; do
      local item
      item=$(echo "$line" | sed 's/^  - //;s/^[[:space:]]*//;s/[[:space:]]*$//' | tr -d '"')
      [ -n "$item" ] && eval "${prefix}_CHAIN_${i}=\"$item\""
      i=$((i + 1))
    done <<< "$raw_chain"
    # Fill remaining slots with empty string
    while [ $i -lt 3 ]; do
      eval "${prefix}_CHAIN_${i}=\"\""
      i=$((i + 1))
    done
  }
  compute_chain_vars "CHALLENGER"
  compute_chain_vars "ARBITER"

  # ── Reflector extraction ─────────────────────────────────────────────
  REFLECTOR_MODEL=$(extract_str "$file" "reflector_model" "$DF_REFLECTOR_MODEL")
  local ref_prov
  ref_prov=$(extract_str "$file" "reflector" "")
  if [ -n "$ref_prov" ]; then
    REFLECTOR_PROVIDER="$ref_prov"
  else
    REFLECTOR_PROVIDER="${REFLECTOR_MODEL%%/*}"
  fi
  PROFILE_REFLECTOR=$(extract_str "$file" "profile_reflector" "$DF_PROFILE_REFLECTOR")

  local allowed
  allowed=$(extract_yaml_list "$file" "allowed")
  ALLOWED_YAML="${allowed:-$DF_ALLOWED}"
  local forbidden
  forbidden=$(extract_yaml_list "$file" "forbidden")
  FORBIDDEN_YAML="${forbidden:-$DF_FORBIDDEN}"

  # Allow env override on model/provider
  ORCH_PROVIDER="${HERMES_ORCH_PROVIDER:-$ORCH_PROVIDER}"
  ORCH_MODEL="${HERMES_ORCH_MODEL:-$ORCH_MODEL}"
  WORKER_PROVIDER="${HERMES_WORKER_PROVIDER:-$WORKER_PROVIDER}"
  WORKER_MODEL="${HERMES_WORKER_MODEL:-$WORKER_MODEL}"
}

# ----------------------------- arg parse ------------------------------------
POSITIONAL=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --adapter) ADAPTER="$2"; shift 2 ;;
    --help|-h)
      echo "Hermes Orchestrator Pack — bootstrap"
      echo ""
      echo "Usage:"
      echo "  bash bootstrap.sh [--dry-run] [--adapter <name>] <repo-dir>"
      echo ""
      echo "Options:"
      echo "  --dry-run         Print actions without executing them"
      echo "  --adapter <name>  Use project adapter from adapters/<name>/"
      echo "  --help, -h        Show this help"
      echo ""
      echo "Setup modes (defined in adapter's project.yaml):"
      echo "  orchestrator  Creates 1 orchestrator + N worker profiles, 1 cron tick, hypotheses ledger"
      echo "  custom        Runs adapter's setup.sh for custom profiles/crons/kanban"
      echo ""
      echo "Environment variables (override adapter config):"
      echo "  HERMES_ORCH_PROVIDER   e.g. anthropic"
      echo "  HERMES_ORCH_MODEL      e.g. claude-opus-4"
      echo "  HERMES_WORKER_PROVIDER e.g. openrouter"
      echo "  HERMES_WORKER_MODEL    e.g. deepseek/deepseek-v4-flash"
      echo ""
      echo "Available adapters:"
      ls "$HERE/adapters/" 2>/dev/null || echo "  (none installed)"
      echo ""
      echo "Examples:"
      echo "  bash bootstrap.sh --dry-run /path/to/repo --adapter v7-alphaforge"
      echo "  bash bootstrap.sh /path/to/repo --adapter v7-alphaforge"
      echo "  bash bootstrap.sh /path/to/repo --adapter designforge"
      exit 0
      ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done
REPO_DIR="${POSITIONAL[0]:-}"

[ -n "$REPO_DIR" ] && [ -d "$REPO_DIR" ] || die "Usage: bash bootstrap.sh [--dry-run] [--adapter <name>] <repo-dir>"
REPO_DIR="$(cd "$REPO_DIR" && pwd)"

# ----------------------------- load adapter ---------------------------------
if [ -n "$ADAPTER" ]; then
  load_adapter "$ADAPTER"
else
  PROJECT_NAME="$DF_PROJECT_NAME"
  OBJECTIVE="$DF_OBJECTIVE"
  BOARD_NAME="$DF_BOARD_NAME"
  BOARD_DESC="$DF_BOARD_DESC"
  PROFILE_ORCH="$DF_PROFILE_ORCH"
  PROFILE_WORKER_PREFIX="$DF_PROFILE_WORKER_PREFIX"
  WORKER_COUNT="$DF_WORKER_COUNT"
  TICK_NAME="$DF_TICK_NAME"
  TICK_SCHEDULE="$DF_TICK_SCHEDULE"
  DELIVERY="$DF_DELIVERY"
  ORCH_PROVIDER="${HERMES_ORCH_PROVIDER:-$DF_ORCH_PROVIDER}"
  ORCH_MODEL="${HERMES_ORCH_MODEL:-$DF_ORCH_MODEL}"
  WORKER_PROVIDER="${HERMES_WORKER_PROVIDER:-$DF_WORKER_PROVIDER}"
  WORKER_MODEL="${HERMES_WORKER_MODEL:-$DF_WORKER_MODEL}"
  SETUP_MODE="$DF_SETUP_MODE"
  LEDGER_DIR="$DF_LEDGER_DIR"
  ALLOWED_YAML="$DF_ALLOWED"
  FORBIDDEN_YAML="$DF_FORBIDDEN"
  MERGE="$DF_MERGE"
  MAX_PARALLEL="$DF_MAX_PARALLEL"
  MAX_SPEND="$DF_MAX_SPEND"
  CHALLENGER_MODEL="$DF_CHALLENGER_MODEL"
  CHALLENGER_PROVIDER="${CHALLENGER_MODEL%%/*}"
  ARBITER_MODEL="$DF_ARBITER_MODEL"
  ARBITER_PROVIDER="${ARBITER_MODEL%%/*}"
  PROFILE_CHALLENGER="$DF_PROFILE_CHALLENGER"
  PROFILE_ARBITER="$DF_PROFILE_ARBITER"
  CHALLENGER_CHAIN_0="$DF_CHALLENGER_CHAIN_0"
  CHALLENGER_CHAIN_1="$DF_CHALLENGER_CHAIN_1"
  CHALLENGER_CHAIN_2="$DF_CHALLENGER_CHAIN_2"
  ARBITER_CHAIN_0="$DF_ARBITER_CHAIN_0"
  ARBITER_CHAIN_1="$DF_ARBITER_CHAIN_1"
  ARBITER_CHAIN_2="$DF_ARBITER_CHAIN_2"
  REFLECTOR_MODEL="$DF_REFLECTOR_MODEL"
  REFLECTOR_PROVIDER="${REFLECTOR_MODEL%%/*}"
  PROFILE_REFLECTOR="$DF_PROFILE_REFLECTOR"
  REFLECTOR_CHAIN_0="$DF_REFLECTOR_CHAIN_0"
  REFLECTOR_CHAIN_1="$DF_REFLECTOR_CHAIN_1"
  REFLECTOR_CHAIN_2="$DF_REFLECTOR_CHAIN_2"
fi

say "project: $PROJECT_NAME"
say "repo:    $REPO_DIR"
say "ledger:  $LEDGER_DIR"
say "adapter: ${ADAPTER:-default}"
$DRY_RUN && dry "mode: dry-run (no files will be written, no Hermes calls)"

# ----------------------------- template substitution ------------------------
sub() {
  # Single-line sed substitutions (safe for all single-line vars)
  local tmp
  tmp=$(sed -e "s|__HERMES_PROJECT_NAME__|$PROJECT_NAME|g" \
      -e "s|__HERMES_OBJECTIVE__|$OBJECTIVE|g" \
      -e "s|__HERMES_BOARD_NAME__|$BOARD_NAME|g" \
      -e "s|__HERMES_BOARD_DESC__|$BOARD_DESC|g" \
      -e "s|__HERMES_PROFILE_ORCHESTRATOR__|$PROFILE_ORCH|g" \
      -e "s|__HERMES_PROFILE_WORKER_PREFIX__|$PROFILE_WORKER_PREFIX|g" \
      -e "s|__HERMES_WORKER_COUNT__|$WORKER_COUNT|g" \
      -e "s|__HERMES_TICK_NAME__|$TICK_NAME|g" \
      -e "s|__HERMES_TICK_SCHEDULE__|$TICK_SCHEDULE|g" \
      -e "s|__HERMES_DELIVERY__|$DELIVERY|g" \
      -e "s|__HERMES_ORCH_PROVIDER__|$ORCH_PROVIDER|g" \
      -e "s|__HERMES_ORCH_MODEL__|$ORCH_MODEL|g" \
      -e "s|__HERMES_WORKER_PROVIDER__|$WORKER_PROVIDER|g" \
      -e "s|__HERMES_WORKER_MODEL__|$WORKER_MODEL|g" \
      -e "s|__HERMES_LEDGER_DIR__|$LEDGER_DIR|g" \
      -e "s|__HERMES_MERGE_POLICY__|$MERGE|g" \
      -e "s|__HERMES_MAX_PARALLEL_WORKERS__|$MAX_PARALLEL|g" \
      -e "s|__HERMES_MAX_SPEND_PER_DAY__|$MAX_SPEND|g" \
      -e "s|__HERMES_REPO_DIR__|$REPO_DIR|g" \
      -e "s|__HERMES_CHALLENGER_PROVIDER__|${CHALLENGER_PROVIDER:-openrouter}|g" \
      -e "s|__HERMES_CHALLENGER_MODEL__|${CHALLENGER_MODEL:-mistralai/mistral-small}|g" \
      -e "s|__HERMES_CHALLENGER_CHAIN_0__|${CHALLENGER_CHAIN_0:-mistralai/mistral-small}|g" \
      -e "s|__HERMES_CHALLENGER_CHAIN_1__|${CHALLENGER_CHAIN_1:-ollama/llama3}|g" \
      -e "s|__HERMES_CHALLENGER_CHAIN_2__|${CHALLENGER_CHAIN_2:-}|g" \
      -e "s|__HERMES_ARBITER_PROVIDER__|${ARBITER_PROVIDER:-anthropic}|g" \
      -e "s|__HERMES_ARBITER_MODEL__|${ARBITER_MODEL:-claude-sonnet-4-20250514}|g" \
      -e "s|__HERMES_ARBITER_CHAIN_0__|${ARBITER_CHAIN_0:-claude-sonnet-4-20250514}|g" \
      -e "s|__HERMES_ARBITER_CHAIN_1__|${ARBITER_CHAIN_1:-deepseek/deepseek-chat}|g" \
      -e "s|__HERMES_ARBITER_CHAIN_2__|${ARBITER_CHAIN_2:-ollama/llama3}|g" \
      -e "s|__HERMES_REFLECTOR_PROVIDER__|${REFLECTOR_PROVIDER:-openrouter}|g" \
      -e "s|__HERMES_REFLECTOR_MODEL__|${REFLECTOR_MODEL:-deepseek/deepseek-chat}|g" \
      -e "s|__HERMES_REFLECTOR_CHAIN_0__|${REFLECTOR_CHAIN_0:-deepseek/deepseek-chat}|g" \
      -e "s|__HERMES_REFLECTOR_CHAIN_1__|${REFLECTOR_CHAIN_1:-ollama/llama3}|g" \
      -e "s|__HERMES_REFLECTOR_CHAIN_2__|${REFLECTOR_CHAIN_2:-}|g" \
      -e "s|__HERMES_PROFILE_REFLECTOR__|${PROFILE_REFLECTOR:-reflector}|g" \
      "$1")
  # Multi-line YAML lists: use awk for the two remaining vars
  echo "$tmp" | awk -v a="$ALLOWED_YAML" -v f="$FORBIDDEN_YAML" '
    /__HERMES_ALLOWED_PATHS_YAML__/ && !done_a {
      print a
      done_a=1
      next
    }
    /__HERMES_FORBIDDEN_PATHS_YAML__/ && !done_f {
      print f
      done_f=1
      next
    }
    { print }
  '
}

# ----------------------------- preflight (real mode) ------------------------
if ! $DRY_RUN; then
  command -v hermes >/dev/null 2>&1 || die "hermes not found on PATH. Install it first: https://github.com/NousResearch/hermes-agent"
  say "hermes: $(hermes --version 2>/dev/null || echo 'version unknown')"

  # Detect Hermes root (where profiles/ config.yaml SOUL.md live)
  HERMES_ROOT=$(detect_hermes_root)
  if [ -z "$HERMES_ROOT" ]; then
    die "Could not detect Hermes home directory. Try setting HERMES_HOME env var."
  fi
  say "hermes root: $HERMES_ROOT"

  # Check env secrets in Hermes root
  if [ ! -f "$HERMES_ROOT/.env" ]; then
    cp "$HERE/env.example" "$HERMES_ROOT/.env"
    chmod 600 "$HERMES_ROOT/.env"
    warn "Created $HERMES_ROOT/.env from template — EDIT IT and add real API keys, then re-run."
    exit 0
  fi
  grep -q 'REPLACE_ME' "$HERMES_ROOT/.env" && die "$HERMES_ROOT/.env still contains REPLACE_ME placeholders. Fill in keys first."

  # Ensure profiles directory exists
  mkdir -p "$HERMES_ROOT/profiles"
fi

# ----------------------------- setup mode dispatch --------------------------
if [ "$SETUP_MODE" = "custom" ]; then
  # Custom setup: delegate to adapter's setup.sh
  ADAPTER_DIR="$HERE/adapters/${ADAPTER:-default}"
  adapter_setup="$ADAPTER_DIR/setup.sh"
  if [ -f "$adapter_setup" ]; then
    say "custom setup mode — running adapter: $ADAPTER"
    bash "$adapter_setup" "$REPO_DIR" "$ADAPTER" "$DRY_RUN" "$HERMES_ROOT" "$HERE" "$ADAPTER_DIR"
  else
    warn "setup_mode=custom but $adapter_setup not found — skipping project-specific setup"
  fi
  # Ledger + AGENTS.md (common to both modes)
  LEDGER="$REPO_DIR/$LEDGER_DIR"
  if $DRY_RUN; then
    dry "mkdir -p $LEDGER/{data,reports}"
    if [ -n "$ADAPTER" ]; then
      adapter_agents="$HERE/adapters/$ADAPTER/AGENTS.adapter.md"
      [ -f "$adapter_agents" ] && dry "cp $adapter_agents $REPO_DIR/AGENTS.md (only if missing)"
    fi
  else
    mkdir -p "$LEDGER"/{data,reports}
    if [ -n "$ADAPTER" ]; then
      adapter_agents="$HERE/adapters/$ADAPTER/AGENTS.adapter.md"
      if [ -f "$adapter_agents" ] && [ ! -f "$REPO_DIR/AGENTS.md" ]; then
        cp "$adapter_agents" "$REPO_DIR/AGENTS.md"
        say "AGENTS.md copied from adapter"
      fi
    fi
    say "ledger ready: $LEDGER"
  fi
else
  # ----------------------------- orchestrator mode: profiles -----------------
  install_profile() {
    local name="$1" config_tpl="$2" soul_tpl="$3"
    local dir="$HERMES_ROOT/profiles/$name"
    if $DRY_RUN; then
      dry "install profile '$name':"
      dry "  hermes profile create $name (if missing)"
      dry "  sub $config_tpl > $dir/config.yaml"
      dry "  cp $soul_tpl $dir/SOUL.md"
      return
    fi
    if [ ! -d "$dir" ]; then
      hermes profile create "$name" --description "Hermes profile: $name" 2>&1 || {
        warn "hermes profile create $name failed — creating directory manually"
        mkdir -p "$dir"
      }
    fi
    mkdir -p "$dir"
    sub "$HERE/$config_tpl" > "$dir/config.yaml"
    sub "$HERE/$soul_tpl" > "$dir/SOUL.md"
    say "profile installed: $name"
  }

  install_profile "$PROFILE_ORCH" "templates/config.orchestrator.yaml" "templates/SOUL.orchestrator.md"
  for i in $(seq 1 "$WORKER_COUNT"); do
    install_profile "${PROFILE_WORKER_PREFIX}-${i}" "templates/config.worker.yaml" "templates/SOUL.worker.md"
  done
  install_profile "$PROFILE_CHALLENGER" "templates/config.challenger.yaml" "templates/SOUL.challenger.md"
  install_profile "$PROFILE_ARBITER" "templates/config.arbiter.yaml" "templates/SOUL.arbiter.md"
  install_profile "$PROFILE_REFLECTOR" "templates/config.reflector.yaml" "templates/SOUL.reflector.md"
  say "reflector profile: $PROFILE_REFLECTOR (shadow mode by default, active only after containment verified)"

  # ----------------------------- gate script ----------------------------------
  if $DRY_RUN; then
    dry "mkdir -p $HERMES_SCRIPTS"
    dry "sub templates/scripts/tick-gate.sh > $HERMES_SCRIPTS/${TICK_NAME}-gate.sh"
    dry "chmod +x $HERMES_SCRIPTS/${TICK_NAME}-gate.sh"
    dry "cp templates/scripts/self-grade-diff.py $HERMES_SCRIPTS/self-grade-diff.py"
    dry "chmod +x $HERMES_SCRIPTS/self-grade-diff.py"
    dry "cp templates/scripts/prereg-lock.py $HERMES_SCRIPTS/prereg-lock.py"
    dry "chmod +x $HERMES_SCRIPTS/prereg-lock.py"
  else
    mkdir -p "$HERMES_SCRIPTS"
    sub "$HERE/templates/scripts/tick-gate.sh" > "$HERMES_SCRIPTS/${TICK_NAME}-gate.sh"
    chmod +x "$HERMES_SCRIPTS/${TICK_NAME}-gate.sh"
    say "gate script installed: $HERMES_SCRIPTS/${TICK_NAME}-gate.sh"
    # ── Deterministic gate scripts (templated) ─────────────────
    for script in self-grade-diff.py prereg-lock.py; do
      src="$HERE/templates/scripts/$script"
      [ -f "$src" ] || die "Required script missing: $src"
      sub "$src" > "$HERMES_SCRIPTS/$script"
      chmod +x "$HERMES_SCRIPTS/$script"
      say "gate script installed: $HERMES_SCRIPTS/$script"
    done
    # ── v0.5 runtime scripts (templated — substituted for placeholders) ──
    for script in blame-propagation.py provenance-track.py feature-flags.py \
                  containment-engine.py reflector-dispatch.sh \
                  analogy-channel.py dream-channel.py whisper-channel.py \
                  calibration-channel.py channel-budget.py channel-dispatch.py \
                  readiness-check.py tick-journal.py tick-runtime.py; do
      src="$HERE/templates/scripts/$script"
      [ -f "$src" ] || die "Required v0.5 script missing: $src"
      sub "$src" > "$HERMES_SCRIPTS/$script"
      chmod +x "$HERMES_SCRIPTS/$script" 2>/dev/null || true
    done
    say "v0.5 runtime scripts installed (with template substitution)"
  fi

  # ----------------------------- repo ledger ----------------------------------
  LEDGER="$REPO_DIR/$LEDGER_DIR"
  if $DRY_RUN; then
    dry "mkdir -p $LEDGER/{hypotheses,runs,reports,challenger,arbiter,locks}"
    dry "mkdir -p $LEDGER/{beliefs,provenance,reflector}"
    dry "mkdir -p $LEDGER/{whispers,analogies,dreams}"
    dry "sub templates/control.yaml > $LEDGER/control.yaml (only if missing)"
    dry "sub templates/state.json > $LEDGER/state.json (only if missing)"
    if [ -n "$ADAPTER" ]; then
      adapter_hyp="$HERE/adapters/$ADAPTER/hypotheses.seed.yaml"
      [ -f "$adapter_hyp" ] && dry "cp $adapter_hyp $LEDGER/hypotheses/ (seed hypotheses)"
      adapter_agents="$HERE/adapters/$ADAPTER/AGENTS.adapter.md"
      [ -f "$adapter_agents" ] && dry "cp $adapter_agents $REPO_DIR/AGENTS.md (only if missing)"
    else
      dry "sub templates/AGENTS.md > $REPO_DIR/AGENTS.md (only if missing)"
    fi
  else
    mkdir -p "$LEDGER"/{hypotheses,runs,reports,challenger,arbiter,locks}
    mkdir -p "$LEDGER"/{beliefs,provenance,reflector}
    mkdir -p "$LEDGER"/{whispers,analogies,dreams}
    if [ ! -f "$LEDGER/control.yaml" ]; then
      sub "$HERE/templates/control.yaml" > "$LEDGER/control.yaml"
    fi
    if [ ! -f "$LEDGER/state.json" ]; then
      sub "$HERE/templates/state.json" > "$LEDGER/state.json"
      say "state.json created (v2 with v0.5 defaults)"
    fi
    if [ ! -f "$LEDGER/beliefs.yaml" ]; then
      sub "$HERE/templates/beliefs.yaml" > "$LEDGER/beliefs.yaml"
      say "beliefs.yaml created (empty v0.5 workspace)"
    fi
    if [ -n "$ADAPTER" ]; then
      adapter_hyp="$HERE/adapters/$ADAPTER/hypotheses.seed.yaml"
      if [ -f "$adapter_hyp" ] && [ ! -f "$LEDGER/hypotheses/seed.yaml" ]; then
        cp "$adapter_hyp" "$LEDGER/hypotheses/seed.yaml"
        say "seed hypotheses: $LEDGER/hypotheses/seed.yaml"
      fi
      adapter_agents="$HERE/adapters/$ADAPTER/AGENTS.adapter.md"
      if [ -f "$adapter_agents" ] && [ ! -f "$REPO_DIR/AGENTS.md" ]; then
        cp "$adapter_agents" "$REPO_DIR/AGENTS.md"
        say "AGENTS.md copied from adapter"
      fi
    else
      if [ ! -f "$REPO_DIR/AGENTS.md" ]; then
        sub "$HERE/templates/AGENTS.md" > "$REPO_DIR/AGENTS.md"
      fi
    fi
    say "ledger ready: $LEDGER"
  fi

  # ----------------------------- Hermes runtime (real mode only) --------------
  if ! $DRY_RUN; then
    # Gateway
    if hermes cron status >/dev/null 2>&1; then
      say "gateway already responding"
    else
      say "installing gateway service"
      hermes gateway install || die "gateway install failed"
    fi

    # Kanban board
    if hermes kanban boards list 2>/dev/null | grep -q "$BOARD_NAME"; then
      say "kanban board '$BOARD_NAME' exists"
    else
      hermes kanban boards create "$BOARD_NAME" \
        --name "$PROJECT_NAME" \
        --description "$BOARD_DESC" \
        --switch
      say "kanban board '$BOARD_NAME' created and set current"
    fi

    # Cron tick
    tick_prompt=$(sub "$HERE/templates/prompts/tick.md")
    if hermes cron list 2>/dev/null | grep -q "$TICK_NAME"; then
      say "cron job '$TICK_NAME' exists — updating"
      hermes cron edit "$TICK_NAME" --schedule "$TICK_SCHEDULE" \
        --prompt "$tick_prompt" || warn "cron edit failed — update manually"
    else
      hermes cron create "$TICK_SCHEDULE" "$tick_prompt" \
        --name "$TICK_NAME" \
        --workdir "$REPO_DIR" \
        --script "${TICK_NAME}-gate.sh" \
        --deliver "$DELIVERY" \
        || die "cron create failed. Check 'hermes cron create --help' for flags."
      say "cron job '$TICK_NAME' created ($TICK_SCHEDULE)"
    fi

    # Verification
    say "--- verification ---"
    hermes cron status || warn "cron status failed"
    hermes cron list 2>/dev/null | grep "$TICK_NAME" || warn "tick job not visible"
    hermes kanban boards show || true
  fi
fi

# ----------------------------- registry update --------------------------------
HEPHAESTUS_DIR="${HEPHAESTUS_DIR:-$HOME/.hephaestus}"
REGISTRY_FILE="$HEPHAESTUS_DIR/registry.yaml"
REGISTRY_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")

BUILD_PROFILES="[$PROFILE_ORCH,"
for i in $(seq 1 $WORKER_COUNT); do BUILD_PROFILES="$BUILD_PROFILES ${PROFILE_WORKER_PREFIX}-${i},"; done
BUILD_PROFILES="$BUILD_PROFILES $PROFILE_CHALLENGER, $PROFILE_ARBITER, $PROFILE_REFLECTOR]"

if $DRY_RUN; then
  dry "update registry at $REGISTRY_FILE"
  dry "  register: $PROJECT_NAME ($REPO_DIR)"
  dry "  profiles: $BUILD_PROFILES"
else
  mkdir -p "$HEPHAESTUS_DIR"

  # Use a single Python heredoc — clean, no nested quoting
  python3 << PYEOF 2>&1
import json, os, yaml

# Read values from environment (safe — no shell quoting issues)
project = "$PROJECT_NAME"
adapter = "${ADAPTER:-default}"
repo = "$REPO_DIR"
ledger = "$LEDGER_DIR"
board = "$BOARD_NAME"
tick = "$TICK_NAME"
ts = "$REGISTRY_TIMESTAMP"

# Build profile list from env
profile_names = $BUILD_PROFILES

registry_file = "$REGISTRY_FILE"

# Load existing or create new
if os.path.exists(registry_file):
    with open(registry_file, encoding='utf-8') as f:
        content = f.read()
    registry = yaml.safe_load(content) or {'schema_version': 1, 'projects': []}
    if not isinstance(registry, dict) or 'projects' not in registry:
        registry = {'schema_version': 1, 'projects': []}
    # Find existing entry by repo
    existing_registered_at = ts
    for p in registry['projects']:
        if p.get('repo') == repo:
            existing_registered_at = p.get('registered_at', ts)
            break
    # Remove old entry (idempotent)
    registry['projects'] = [p for p in registry['projects'] if p.get('repo') != repo]
else:
    registry = {'schema_version': 1, 'projects': []}
    existing_registered_at = ts

# Add new entry
entry = {
    'name': project,
    'adapter': adapter,
    'repo': repo,
    'ledger': ledger,
    'board': board,
    'tick': tick,
    'profiles': profile_names,
    'status': 'active',
    'goal_status': 'none',
    'registered_at': existing_registered_at,
    'updated_at': ts,
}
registry['projects'].append(entry)

with open(registry_file, 'w', encoding='utf-8') as f:
    yaml.dump(registry, f, indent=2, default_flow_style=False, allow_unicode=True)

if os.path.exists(registry_file):
    print(f'Registry updated for {project}')
else:
    print(f'Registry created at {registry_file}')
PYEOF
  say "registry: $PROJECT_NAME -> $REGISTRY_FILE"
fi

# ----------------------------- summary --------------------------------------
echo ""
say "========== $PROJECT_NAME — Hermes Orchestrator Pack =========="
say "repo:       $REPO_DIR"
say "ledger:     $LEDGER_DIR/"
if [ "$SETUP_MODE" = "custom" ]; then
  say "setup:      custom (adapter: ${ADAPTER:-default})"
else
  say "mode:       orchestrator"
  say "profiles:   $PROFILE_ORCH, ${PROFILE_WORKER_PREFIX}-1..${WORKER_COUNT}, $PROFILE_CHALLENGER, $PROFILE_ARBITER, $PROFILE_REFLECTOR"
  say "tick:       $TICK_NAME ($TICK_SCHEDULE)"
fi
say "board:      $BOARD_NAME"
if $DRY_RUN; then
  echo ""
  dry "Dry-run complete. No files were written."
  dry "Run without --dry-run to execute the bootstrap."
  echo ""
  echo "To verify files would be created correctly:"
  echo "  find \"$LEDGER\" -type f 2>/dev/null | sort"
  echo ""
  echo "Next step after dry-run looks good:"
  echo "  bash bootstrap.sh \"$REPO_DIR\" --adapter ${ADAPTER:-<name>}"
else
  echo ""
  echo "Next steps:"
  echo "  1. Review $LEDGER/control.yaml  (mode is 'paused' by default)"
  echo "  2. Fill AGENTS.md with real boundaries + runner commands"
  echo "  3. Dry-run one tick:        hermes cron run $TICK_NAME"
  echo "  4. When ready, set          mode: running  in control.yaml"
  echo "  5. Pause:                   hermes cron pause $TICK_NAME"
  echo "  6. Resume:                  hermes cron resume $TICK_NAME"
  say "done."
fi
