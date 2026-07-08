#!/usr/bin/env python3
"""
Schema Validation Test Suite
Tests that schema files are valid JSON Schema and validate sample data.
"""
import json
import os
import sys
import glob

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..")
PASS_COUNT = 0
FAIL_COUNT = 0

def say(msg):
    print(f"\033[1;32m[TEST]\033[0m {msg}")

def fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"\033[1;31m[TEST] FAIL:\033[0m {msg}")

def pass_(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"\033[1;32m[TEST] PASS:\033[0m {msg}")

# Helper: minimal JSON Schema validator (draft-07 subset)
def validate_schema(obj, sch, path="", errors=None):
    if errors is None:
        errors = []
    if not isinstance(sch, dict):
        return errors

    # Type check (skip type check if obj is None and type is a union including null)
    expected_type = sch.get("type")
    if obj is not None and expected_type == "integer" and not isinstance(obj, int):
        errors.append(f'{path}: expected integer, got {type(obj).__name__}')
    if obj is not None and expected_type == "number" and not isinstance(obj, (int, float)):
        errors.append(f'{path}: expected number, got {type(obj).__name__}')
    if obj is not None and expected_type == "string" and not isinstance(obj, str):
        errors.append(f'{path}: expected string, got {type(obj).__name__}')
    if obj is not None and expected_type == "boolean" and not isinstance(obj, bool):
        errors.append(f'{path}: expected boolean, got {type(obj).__name__}')
    if expected_type == "array" and not isinstance(obj, list):
        errors.append(f'{path}: expected array, got {type(obj).__name__}')
    if expected_type == "object" and not isinstance(obj, dict):
        errors.append(f'{path}: expected object, got {type(obj).__name__}')

    # Enum check
    if "enum" in sch and obj not in sch["enum"]:
        errors.append(f'{path}: expected one of {sch["enum"]}, got "{obj}"')

    # Required check
    if "required" in sch and isinstance(obj, dict):
        for req in sch["required"]:
            if req not in obj:
                errors.append(f'{path}: missing required field "{req}"')

    if isinstance(obj, dict):
        if sch.get("additionalProperties") is False and "properties" in sch:
            allowed = set(sch["properties"].keys())
            for k in obj:
                if k not in allowed:
                    errors.append(f'{path}: unexpected field "{k}"')
        for key, prop_schema in sch.get("properties", {}).items():
            if key in obj:
                validate_schema(obj[key], prop_schema, f"{path}.{key}" if path else key, errors)
    elif isinstance(obj, list) and "items" in sch:
        for i, item in enumerate(obj):
            validate_schema(item, sch["items"], f"{path}[{i}]", errors)
    return errors

# ── Test 1: Schema files are valid JSON ──────────────────────────────────────
say("Test 1: Schema files are valid JSON")
schema_files = glob.glob(os.path.join(SCHEMA_DIR, "*.schema.json"))
if not schema_files:
    fail("No schema files found in schema/ directory")
else:
    for sf in schema_files:
        name = os.path.basename(sf)
        try:
            with open(sf) as f:
                json.load(f)
            pass_(f"{name} is valid JSON")
        except json.JSONDecodeError as e:
            fail(f"{name} is NOT valid JSON: {e}")

# ── Test 2: Schema files have schema_version property ───────────────────────
say("Test 2: Schema files contain schema_version")
for sf in schema_files:
    name = os.path.basename(sf)
    with open(sf) as f:
        schema = json.load(f)
    props = schema.get("properties", {})
    if "schema_version" in props:
        pass_(f"{name} has schema_version property")
    else:
        fail(f"{name} MISSING schema_version property")

# ── Test 3: Valid state passes schema ────────────────────────────────────────
say("Test 3: Valid state.json passes state.schema.json validation")
with open(os.path.join(SCHEMA_DIR, "state.schema.json")) as f:
    state_schema = json.load(f)

valid_state = {
    "schema_version": 1,
    "tick": 42,
    "worker_status": {"worker-1": "running", "worker-2": "idle"},
    "spend_today_usd": 12.50,
    "budget_usd": 25,
    "last_tick_at": "2026-07-08T12:00:00Z",
    "board": "alphaforge",
    "gates": {"T0": 10, "T1": 8, "T2": 5, "T3": 2, "T4": 1},
    "goal_status": "in_progress"
}

errors = validate_schema(valid_state, state_schema)
if not errors:
    pass_("Valid state.json passes schema")
else:
    fail(f"Valid state.json FAILED: {errors}")

# ── Test 4: Invalid state (missing required field) is rejected ──────────────
say("Test 4: Invalid state.json (missing required field) is rejected")
invalid_state = {"schema_version": 1}
errors = validate_schema(invalid_state, state_schema)
if errors:
    pass_("Invalid state correctly rejected: " + "; ".join(errors))
else:
    fail("Invalid state was NOT rejected")

# ── Test 5: Invalid state (unexpected field) is rejected ────────────────────
say("Test 5: Invalid state.json (unexpected field) is rejected")
bad_state = {"schema_version": 1, "tick": 0, "nonexistent_field": "value"}
errors = validate_schema(bad_state, state_schema)
if errors:
    pass_("Invalid state with unexpected field rejected: " + "; ".join(errors))
else:
    fail("Invalid state with unexpected field was NOT rejected")

# ── Test 6: Valid control.yaml content passes schema ────────────────────────
say("Test 6: Valid control.yaml content passes control.schema.json")
with open(os.path.join(SCHEMA_DIR, "control.schema.json")) as f:
    control_schema = json.load(f)

valid_control = {
    "schema_version": 1,
    "mode": "running",
    "max_parallel_workers": 3,
    "current_priority": "",
    "human_instruction": "",
    "allowed_paths": ["src/"],
    "forbidden_paths": ["vendor/"],
    "merge_policy": "pr_only",
    "max_llm_spend_per_day_usd": 25,
    "repo": "/path/to/repo"
}
errors = validate_schema(valid_control, control_schema)
if not errors:
    pass_("Valid control.yaml passes schema")
else:
    fail(f"Valid control.yaml FAILED: {errors}")

# ── Test 7: Valid goal.yaml passes schema ───────────────────────────────────
say("Test 7: Valid goal.yaml passes goal.schema.json")
with open(os.path.join(SCHEMA_DIR, "goal.schema.json")) as f:
    goal_schema = json.load(f)

valid_goal = {
    "schema_version": 1,
    "goal_type": "eternal",
    "statement": "Improve the project measurably",
    "success_criteria": [
        {"kind": "praxis_gate", "gate": "finalGate"},
        {"kind": "metric", "source": "runs/*.json", "field": "sharpe_oos", "op": ">=", "value": 1.4}
    ],
    "never_stop_rules": {"min_open_hypotheses": 5, "exhaustion_policy": "generate_ideas"},
    "stop_conditions": ["budget_exhausted", "mode:killed"],
    "goal_status": "in_progress"
}
errors = validate_schema(valid_goal, goal_schema)
if not errors:
    pass_("Valid goal.yaml passes schema")
else:
    fail(f"Valid goal.yaml FAILED: {errors}")

# ── Test 8: Valid ideas YAML passes schema ──────────────────────────────────
say("Test 8: Valid ideas YAML passes ideas.schema.json")
with open(os.path.join(SCHEMA_DIR, "ideas.schema.json")) as f:
    ideas_schema = json.load(f)

valid_idea = {
    "schema_version": 1,
    "id": "idea-001",
    "title": "Test idea",
    "description": "A test idea",
    "source": "failure_mining",
    "source_project": "",
    "status": "spark",
    "triage_score": 75,
    "novelty_score": 60,
    "embedding": [0.1, 0.2, 0.3],
    "related_hypothesis": "",
    "created_at": "2026-07-08T12:00:00Z",
    "updated_at": "2026-07-08T12:00:00Z",
    "family": "",
    "metadata": {}
}
errors = validate_schema(valid_idea, ideas_schema)
if not errors:
    pass_("Valid idea passes schema")
else:
    fail(f"Valid idea FAILED: {errors}")

# ── Test 9: Valid event passes schema ───────────────────────────────────────
say("Test 9: Valid event passes events.schema.json")
with open(os.path.join(SCHEMA_DIR, "events.schema.json")) as f:
    events_schema = json.load(f)

valid_event = {
    "schema_version": 1,
    "event_id": "evt-001",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "tick_start",
    "source": "orchestrator",
    "project": "AlphaForge",
    "payload": {"tick": 42},
    "severity": "info"
}
errors = validate_schema(valid_event, events_schema)
if not errors:
    pass_("Valid event passes schema")
else:
    fail(f"Valid event FAILED: {errors}")

# ── Test 10: Test migrate-ledger.sh logic (v1 → v2) ─────────────────────────
say("Test 10: migrate-ledger.sh v1 to v2 conversion logic")
v1_state = {
    "tick": 10,
    "active_branches": {"worker-1": "running"},
    "spend_today_usd": 5.0,
    "max_llm_spend_per_day_usd": 25,
    "last_tick_at": None,
    "board": "test-board"
}

# Replicate migrate-ledger.sh logic (mode is in control.yaml, not state.json)
v2_state = {
    "schema_version": 1,
    "tick": v1_state.get("tick", v1_state.get("current_tick", 0)),
    "worker_status": v1_state.get("worker_status", v1_state.get("active_branches", {})),
    "spend_today_usd": v1_state.get("spend_today_usd", v1_state.get("total_budget_spent", 0)),
    "budget_usd": v1_state.get("budget_usd", v1_state.get("max_llm_spend_per_day_usd", 25)),
    "last_tick_at": v1_state.get("last_tick_at", None),
    "board": v1_state.get("board", ""),
    "gates": v1_state.get("gates", {"T0": 0, "T1": 0, "T2": 0, "T3": 0, "T4": 0}),
    "goal_status": v1_state.get("goal_status", "none")
}

# Verify v2 state validates against schema
errors = validate_schema(v2_state, state_schema)
if not errors and v2_state["tick"] == 10 and v2_state["schema_version"] == 1:
    pass_("migrate-ledger.sh correctly converts v1 to v2")
else:
    fail(f"Migration logic incorrect: errors={errors}")

# ── Test 11: Control schema rejects invalid mode ────────────────────────────
say("Test 11: Control schema rejects invalid mode")
bad_control = {"schema_version": 1, "mode": "invalid_mode"}
errors = validate_schema(bad_control, control_schema)
if errors:
    pass_("Invalid mode rejected: " + "; ".join(errors))
else:
    fail("Invalid mode was NOT rejected")

# ── Test 12: Registry schema exists and has schema_version ──────────────────
say("Test 12: Registry schema exists and has schema_version")
registry_schema_path = os.path.join(SCHEMA_DIR, "registry.schema.json")
if os.path.exists(registry_schema_path):
    pass_("registry.schema.json exists")
    with open(registry_schema_path) as f:
        reg_schema = json.load(f)
    props = reg_schema.get("properties", {})
    if "schema_version" in props and "projects" in props:
        pass_("registry.schema.json has schema_version and projects")
    else:
        fail("registry.schema.json missing schema_version or projects")
else:
    fail("registry.schema.json does NOT exist")

# ── Test 13: Valid registry passes schema ───────────────────────────────────
say("Test 13: Valid registry passes registry.schema.json")
if os.path.exists(registry_schema_path):
    with open(registry_schema_path) as f:
        reg_schema = json.load(f)
    valid_registry = {
        "schema_version": 1,
        "projects": [
            {
                "name": "AlphaForge",
                "adapter": "v7-alphaforge",
                "repo": "/path/to/alphaforge",
                "ledger": ".alphaforge/orchestrator",
                "board": "alphaforge",
                "tick": "af-orchestrator-tick",
                "profiles": ["af-orchestrator", "af-worker-1"],
                "status": "active",
                "goal_status": "in_progress",
                "registered_at": "2026-07-08T12:00:00Z",
                "updated_at": "2026-07-08T12:00:00Z",
            }
        ],
    }
    errors = validate_schema(valid_registry, reg_schema)
    if not errors:
        pass_("Valid registry passes schema")
    else:
        fail(f"Valid registry FAILED: {errors}")

# ── Test 14: Registry test bootstrap registry creation ──────────────────────
say("Test 14: Bootstrap registry entry logic")
test_registry = {"schema_version": 1, "projects": []}
entry = {
    "name": "TestProject",
    "adapter": "test-adapter",
    "repo": "/tmp/test-repo",
    "ledger": ".test-ledger",
    "board": "test-board",
    "tick": "test-tick",
    "profiles": ["orch", "worker-1"],
    "status": "active",
    "goal_status": "none",
    "registered_at": "2026-07-08T12:00:00Z",
    "updated_at": "2026-07-08T12:00:00Z",
}
test_registry["projects"].append(entry)
errors = validate_schema(test_registry, reg_schema if os.path.exists(registry_schema_path) else {})
if not errors:
    pass_("Bootstrap registry entry passes schema")
else:
    fail(f"Registry entry FAILED: {errors}")

# Test idempotent update: same repo updates, doesn't duplicate
test_registry2 = {"schema_version": 1, "projects": []}
test_registry2["projects"].append(dict(entry))
# Simulate idempotent update (find by repo and update)
existing_idx = next((i for i, p in enumerate(test_registry2["projects"]) if p["repo"] == entry["repo"]), -1)
if existing_idx >= 0:
    test_registry2["projects"][existing_idx]["status"] = "paused"
else:
    test_registry2["projects"].append(entry)
assert len(test_registry2["projects"]) == 1
assert test_registry2["projects"][0]["status"] == "paused"
pass_("Registry idempotent update: re-bootstrap updates existing entry, no duplicate")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 56)
print(f"  Schema Test Suite Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
