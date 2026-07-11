#!/usr/bin/env bash
# Pre-run gate for the orchestrator tick.
# Emits {"wakeAgent": false} to skip the LLM entirely when there is nothing
# to do. This is the PRE-TICK gate — it checks whether to wake the orchestrator.
# Praxis (evidence gate) runs AFTER the worker produces output.
#
# Schema validation: When mode=running, validates state.json against
# state.schema.json. If invalid, emits wakeAgent:false + error context.
set -u
REPO="__HERMES_REPO_DIR__"
LEDGER_DIR="__HERMES_LEDGER_DIR__"
PACK_DIR="$(cd "$(dirname "$0")/../../" && pwd)"  # hephaestus root (resolved from ~/.hermes/scripts/)
CTRL="$REPO/$LEDGER_DIR/control.yaml"
STATE_FILE="$REPO/$LEDGER_DIR/state.json"
STATE_DIR="$HOME/.hermes/scripts/.hermes-state"
SCHEMA_DIR="${PACK_DIR}/schema"
mkdir -p "$STATE_DIR"

# ── Schema validation helper ──────────────────────────────────────────────────
validate_json_schema() {
  # Validates a JSON file against a JSON Schema using python3 (stdlib only).
  # Args: $1 = json file, $2 = schema file
  # Returns: 0 if valid, 1 if invalid
  local json_file="$1"
  local schema_file="$2"

  if [ ! -f "$json_file" ]; then
    return 0  # no file = nothing to validate
  fi
  if [ ! -f "$schema_file" ]; then
    return 0  # no schema = can't validate, skip
  fi

  python -c "
import json, sys
try:
    with open('$json_file') as f:
        data = json.load(f)
    with open('$schema_file') as f:
        schema = json.load(f)

    # Minimal JSON Schema validation (draft-07 subset)
    # Checks: required properties, type, enum, minimum, additionalProperties
    errors = []

    def validate(obj, sch, path=''):
        if not isinstance(sch, dict):
            return
        # required check
        if 'required' in sch and isinstance(obj, dict):
            for req in sch['required']:
                if req not in obj:
                    errors.append(f\"{path}: missing required field '{req}'\")

        if isinstance(obj, dict):
            # additionalProperties check
            if sch.get('additionalProperties') == False and 'properties' in sch:
                allowed = set(sch['properties'].keys())
                for k in obj:
                    if k not in allowed:
                        errors.append(f\"{path}: unexpected field '{k}'\")
            # property-by-property validation
            for key, prop_schema in sch.get('properties', {}).items():
                if key in obj:
                    val = obj[key]
                    prop_path = f\"{path}.{key}\" if path else key
                    validate_type(val, prop_schema, prop_path)
                    validate_enum(val, prop_schema, prop_path)
                    validate_min(val, prop_schema, prop_path)

        elif isinstance(obj, list) and 'items' in sch:
            for i, item in enumerate(obj):
                validate(item, sch['items'], f'{path}[{i}]')

    def validate_type(val, sch, path):
        if 'type' not in sch:
            return
        expected = sch['type']
        if expected == 'integer':
            if not isinstance(val, int) or isinstance(val, bool):
                errors.append(f\"{path}: expected integer, got {type(val).__name__}\")
        elif expected == 'number':
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                errors.append(f\"{path}: expected number, got {type(val).__name__}\")
        elif expected == 'string':
            if not isinstance(val, str):
                errors.append(f\"{path}: expected string, got {type(val).__name__}\")
        elif expected == 'boolean':
            if not isinstance(val, bool):
                errors.append(f\"{path}: expected boolean, got {type(val).__name__}\")
        elif expected == 'array':
            if not isinstance(val, list):
                errors.append(f\"{path}: expected array, got {type(val).__name__}\")
        elif expected == 'object':
            if not isinstance(val, dict):
                errors.append(f\"{path}: expected object, got {type(val).__name__}\")
        elif expected.startswith('['):
            # Union type like ["string", "null"]
            union_types = [t.strip() for t in expected.strip('[]').split(',')]
            matches = False
            for ut in union_types:
                ut = ut.strip().strip('\"').strip(\"'\")
                if ut == 'null' and val is None:
                    matches = True; break
                elif ut == 'string' and isinstance(val, str):
                    matches = True; break
                elif ut == 'number' and isinstance(val, (int, float)):
                    matches = True; break
                elif ut == 'integer' and isinstance(val, int):
                    matches = True; break
            if not matches:
                errors.append(f\"{path}: expected one of [{expected}], got {type(val).__name__}\")

    def validate_enum(val, sch, path):
        if 'enum' in sch and val not in sch['enum']:
            errors.append(f\"{path}: expected one of {sch['enum']}, got '{val}'\")

    def validate_min(val, sch, path):
        if 'minimum' in sch and isinstance(val, (int, float)):
            if val < sch['minimum']:
                errors.append(f\"{path}: minimum {sch['minimum']}, got {val}\")

    validate(data, schema)
    if errors:
        print('Schema validation FAILED:', file=sys.stderr)
        for e in errors:
            print(f'  - {e}', file=sys.stderr)
        sys.exit(1)
    else:
        print('Schema validation PASSED')
except json.JSONDecodeError as e:
    print(f'JSON parse error: {e}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Validation error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1
  return $?
}

# ── 1) Hard gate on control.yaml mode ─────────────────────────────────────────
if [ ! -f "$CTRL" ]; then
  echo '{"wakeAgent": true, "context": {"warning": "control.yaml missing"}}'
  exit 0
fi
mode=$(grep -E '^mode:' "$CTRL" | awk '{print $2}')
if [ "$mode" != "running" ]; then
  last="$STATE_DIR/last-paused-wake"
  now=$(date +%s)
  prev=$(cat "$last" 2>/dev/null || echo 0)
  if [ $((now - prev)) -lt 21600 ]; then
    echo '{"wakeAgent": false}'
  else
    echo "$now" > "$last"
    echo "{\"wakeAgent\": true, \"context\": {\"mode\": \"$mode\", \"note\": \"heartbeat while not running\"}}"
  fi
  exit 0
fi

# ── 2) Schema validation gate ─────────────────────────────────────────────────
# When mode=running, validate state.json against the schema.
# Invalid state → do not wake the orchestrator (prevents LLM from writing garbage).
if [ -f "$STATE_FILE" ]; then
  state_schema="${SCHEMA_DIR}/state.schema.json"
  if [ -f "$state_schema" ]; then
    validate_result=$(validate_json_schema "$STATE_FILE" "$state_schema" 2>&1)
    validate_exit=$?
    if [ $validate_exit -ne 0 ]; then
      # Log the validation error
      echo "[tick-gate] Schema validation FAILED for $STATE_FILE" >&2
      echo "$validate_result" >&2
      echo '{"wakeAgent": false, "context": {"error": "schema_validation_failed", "detail": "state.json failed state.schema.json validation. Fix or re-migrate before next tick."}}'
      exit 0
    fi
  fi
fi

# ── 3) Activity gate: wake if the board db, runs/, or control.yaml changed ────
last="$STATE_DIR/last-activity-wake"
prev=$(cat "$last" 2>/dev/null || echo 0)
newest=0
for f in "$HOME/.hermes/kanban.db" "$CTRL"; do
  [ -f "$f" ] && m=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f") && [ "$m" -gt "$newest" ] && newest=$m
done
runs_newest=$(find "$REPO/$LEDGER_DIR/runs" -type f -newer "$last" 2>/dev/null | head -1)
if [ "$newest" -le "$prev" ] && [ -z "$runs_newest" ]; then
  now=$(date +%s)
  if [ $((now - prev)) -lt 10800 ]; then
    echo '{"wakeAgent": false}'
    exit 0
  fi
fi
date +%s > "$last"

# ── 4) Mandatory tick journal init ────────────────────────────────────────────
# tick-runtime.py init initializes or recovers the transaction journal.
# This runs BEFORE the LLM is woken, making it a non-bypassable pre-tick gate.
JOURNAL_DIR="$REPO/$LEDGER_DIR/journal"
STATE_FILE="$REPO/$LEDGER_DIR/state.json"
if [ -f "$STATE_FILE" ]; then
  python3 "$PACK_DIR/templates/scripts/tick-runtime.py" init "$STATE_FILE" "$JOURNAL_DIR" 2>/dev/null || \
    echo '{"wakeAgent": false, "context": {"error": "tick-runtime init failed"}}'
fi

echo '{"wakeAgent": true}'
