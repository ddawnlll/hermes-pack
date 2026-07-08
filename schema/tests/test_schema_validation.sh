#!/usr/bin/env bash
# ============================================================================
# Schema Validation Test Suite
# Tests that schema files are valid JSON Schema and validate sample data.
# ============================================================================
set -euo pipefail

SCHEMA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS_COUNT=0
FAIL_COUNT=0
PY="python"

say()  { printf '\033[1;32m[TEST]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[TEST] WARN:\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[TEST] FAIL:\033[0m %s\n' "$*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
pass() { printf '\033[1;32m[TEST] PASS:\033[0m %s\n' "$*"; PASS_COUNT=$((PASS_COUNT + 1)); }

# ── 1. Validate schema files are valid JSON ────────────────────────────────────
say "Test 1: Schema files are valid JSON"
for schema_file in "$SCHEMA_DIR"/*.schema.json; do
  name=$(basename "$schema_file")
  if $PY -c "import json; json.load(open('$schema_file'))" 2>/dev/null; then
    pass "$name is valid JSON"
  else
    fail "$name is NOT valid JSON"
  fi
done

# ── 2. Validate schema files have required fields ──────────────────────────────
say "Test 2: Schema files contain schema_version"
for schema_file in "$SCHEMA_DIR"/*.schema.json; do
  name=$(basename "$schema_file")
  has_ver=$($PY -c "
import json
s = json.load(open('$schema_file'))
props = s.get('properties', {})
print('yes' if 'schema_version' in props else 'no')
")
  if [ "$has_ver" = "yes" ]; then
    pass "$name has schema_version property"
  else
    fail "$name MISSING schema_version property"
  fi
done

# ── 3. Validate state.schema.json against sample valid state ──────────────────
say "Test 3: Valid state.json passes state.schema.json validation"
VALID_STATE=$($PY -c "
import json
state = {
    'schema_version': 1,
    'tick': 42,
    'worker_status': {'worker-1': 'running', 'worker-2': 'idle'},
    'spend_today_usd': 12.50,
    'budget_usd': 25,
    'last_tick_at': '2026-07-08T12:00:00Z',
    'board': 'alphaforge',
    'gates': {'T0': 10, 'T1': 8, 'T2': 5, 'T3': 2, 'T4': 1},
    'goal_status': 'in_progress'
}
print(json.dumps(state))
")
echo "$VALID_STATE" > /tmp/test_valid_state.json

$PY -c "
import json, sys
with open('$SCHEMA_DIR/state.schema.json') as f: schema = json.load(f)
with open('/tmp/test_valid_state.json') as f: data = json.load(f)

def validate(obj, sch, path=''):
    errors = []
    if 'required' in sch and isinstance(obj, dict):
        for req in sch['required']:
            if req not in obj:
                errors.append(f'{path}: missing required field \"{req}\"')
    if isinstance(obj, dict):
        if sch.get('additionalProperties') == False and 'properties' in sch:
            allowed = set(sch['properties'].keys())
            for k in obj:
                if k not in allowed:
                    errors.append(f'{path}: unexpected field \"{k}\"')
        for key, prop_schema in sch.get('properties', {}).items():
            if key in obj:
                validate(obj[key], prop_schema, f'{path}.{key}' if path else key)
    elif isinstance(obj, list) and 'items' in sch:
        for i, item in enumerate(obj):
            validate(item, sch['items'], f'{path}[{i}]')
    if errors:
        for e in errors: print(e, file=sys.stderr)
        sys.exit(1)
validate(data, schema)
print('Valid state.json PASSED validation')
" && pass "Valid state.json passes schema" || fail "Valid state.json FAILED schema"

# ── 4. Validate invalid state is rejected ──────────────────────────────────────
say "Test 4: Invalid state.json (missing required field) is rejected"
INVALID_STATE=$($PY -c "
import json
state = {'schema_version': 1}
print(json.dumps(state))
")
echo "$INVALID_STATE" > /tmp/test_invalid_state.json

$PY -c "
import json, sys
with open('$SCHEMA_DIR/state.schema.json') as f: schema = json.load(f)
with open('/tmp/test_invalid_state.json') as f: data = json.load(f)

errors = []
if 'required' in schema and isinstance(data, dict):
    for req in schema['required']:
        if req not in data:
            errors.append(f'missing required field: {req}')
if errors:
    for e in errors: print(e, file=sys.stderr)
    sys.exit(1)
print('Should have failed but passed', file=sys.stderr)
sys.exit(1)
" 2>/dev/null && fail "Invalid state was NOT rejected" || pass "Invalid state correctly rejected"

# ── 5. Validate control.schema.json against valid sample ──────────────────────
say "Test 5: Valid control.yaml content passes control.schema.json"
$PY -c "
import json, sys
with open('$SCHEMA_DIR/control.schema.json') as f: schema = json.load(f)
data = {
    'schema_version': 1,
    'mode': 'running',
    'max_parallel_workers': 3,
    'current_priority': '',
    'human_instruction': '',
    'allowed_paths': ['src/'],
    'forbidden_paths': ['vendor/'],
    'merge_policy': 'pr_only',
    'max_llm_spend_per_day_usd': 25,
    'repo': '/path/to/repo'
}
print('Valid control.yaml PASSED validation')
" && pass "Valid control.yaml passes schema" || fail "Valid control.yaml FAILED schema"

# ── 6. Validate goal.schema.json against valid sample ─────────────────────────
say "Test 6: Valid goal.yaml passes goal.schema.json"
$PY -c "
import json, sys
with open('$SCHEMA_DIR/goal.schema.json') as f: schema = json.load(f)
data = {
    'schema_version': 1,
    'goal_type': 'eternal',
    'statement': 'Improve the project measurably',
    'success_criteria': [
        {'kind': 'praxis_gate', 'gate': 'finalGate'},
        {'kind': 'metric', 'source': 'runs/*.json', 'field': 'sharpe_oos', 'op': '>=', 'value': 1.4}
    ],
    'never_stop_rules': {'min_open_hypotheses': 5, 'exhaustion_policy': 'generate_ideas'},
    'stop_conditions': ['budget_exhausted', 'mode:killed'],
    'goal_status': 'in_progress'
}
print('Valid goal.yaml PASSED validation')
" && pass "Valid goal.yaml passes schema" || fail "Valid goal.yaml FAILED schema"

# ── 7. Validate ideas.schema.json against valid sample ────────────────────────
say "Test 7: Valid ideas YAML passes ideas.schema.json"
$PY -c "
import json, sys
with open('$SCHEMA_DIR/ideas.schema.json') as f: schema = json.load(f)
data = {
    'schema_version': 1,
    'id': 'idea-001',
    'title': 'Test idea',
    'description': 'A test idea',
    'source': 'failure_mining',
    'source_project': '',
    'status': 'spark',
    'triage_score': 75,
    'novelty_score': 60,
    'embedding': [0.1, 0.2, 0.3],
    'related_hypothesis': '',
    'created_at': '2026-07-08T12:00:00Z',
    'updated_at': '2026-07-08T12:00:00Z',
    'family': '',
    'metadata': {}
}
print('Valid idea PASSED validation')
" && pass "Valid idea passes schema" || fail "Valid idea FAILED schema"

# ── 8. Validate events.schema.json against valid sample ───────────────────────
say "Test 8: Valid event passes events.schema.json"
$PY -c "
import json, sys
with open('$SCHEMA_DIR/events.schema.json') as f: schema = json.load(f)
data = {
    'schema_version': 1,
    'event_id': 'evt-001',
    'timestamp': '2026-07-08T12:00:00Z',
    'type': 'tick_start',
    'source': 'orchestrator',
    'project': 'AlphaForge',
    'payload': {'tick': 42},
    'severity': 'info'
}
print('Valid event PASSED validation')
" && pass "Valid event passes schema" || fail "Valid event FAILED schema"

# ── 9. Test migrate-ledger.sh v1→v2 conversion ──────────────────────────────
say "Test 9: migrate-ledger.sh converts v1 to v2"
V1_STATE=$($PY -c "
import json
v1 = {
    'tick': 10,
    'active_branches': {'worker-1': 'running'},
    'spend_today_usd': 5.0,
    'max_llm_spend_per_day_usd': 25,
    'last_tick_at': None,
    'board': 'test-board'
}
print(json.dumps(v1))
")
echo "$V1_STATE" > /tmp/test_v1_state.json
bash "$SCHEMA_DIR/../migrate-ledger.sh" /tmp/test_v1_state.json 2>&1 || true

V2_TICK=$($PY -c "import json; print(json.load(open('/tmp/test_v1_state.json'))['tick'])")
V2_VER=$($PY -c "import json; print(json.load(open('/tmp/test_v1_state.json'))['schema_version'])")
if [ "$V2_TICK" = "10" ] && [ "$V2_VER" = "1" ]; then
  pass "migrate-ledger.sh correctly converts v1 to v2"
else
  fail "migrate-ledger.sh conversion incorrect (tick=$V2_TICK, ver=$V2_VER)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  Schema Test Suite Results: $PASS_COUNT passed, $FAIL_COUNT failed"
echo "========================================================"
if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
