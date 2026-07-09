#!/usr/bin/env python3
"""
Goal Engine Verification Tests — Issue #6
Tests that goal.schema.json exists with proper fields,
templates/goal.yaml is valid and matches the schema,
goal_type supports eternal/gate_target/metric_target,
and never_stop_rules contain min_open_hypotheses and exhaustion_policy.
"""
import json
import os
import sys
import yaml

REPO_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMA_DIR = os.path.join(REPO_DIR, "schema")
TEMPLATES_DIR = os.path.join(REPO_DIR, "templates")
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


# ── Helper: minimal JSON Schema validator (draft-07 subset) ──────────────
def validate_schema(obj, sch, path="", errors=None):
    if errors is None:
        errors = []
    if not isinstance(sch, dict):
        return errors

    # Type check
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

    # Recurse
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


# ── Helper: load JSON schema ─────────────────────────────────────────────
def load_goal_schema():
    path = os.path.join(SCHEMA_DIR, "goal.schema.json")
    if not os.path.exists(path):
        fail(f"goal.schema.json not found at {path}")
        return None
    with open(path) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: goal.schema.json exists and is valid JSON
# ═══════════════════════════════════════════════════════════════════════════
say("Test 1: goal.schema.json exists and is valid JSON")
goal_schema_path = os.path.join(SCHEMA_DIR, "goal.schema.json")
if os.path.exists(goal_schema_path):
    pass_("goal.schema.json exists")
    try:
        with open(goal_schema_path) as f:
            goal_schema = json.load(f)
        pass_("goal.schema.json is valid JSON")
    except json.JSONDecodeError as e:
        fail(f"goal.schema.json is NOT valid JSON: {e}")
        goal_schema = None
else:
    fail("goal.schema.json does NOT exist")
    goal_schema = None

# ═══════════════════════════════════════════════════════════════════════════
# Test 2: goal.schema.json has required top-level properties
# ═══════════════════════════════════════════════════════════════════════════
say("Test 2: goal.schema.json has required top-level properties")
if goal_schema:
    props = goal_schema.get("properties", {})
    required_fields = ["schema_version", "goal_type", "statement",
                       "success_criteria", "never_stop_rules",
                       "stop_conditions", "goal_status"]
    missing = [f for f in required_fields if f not in props]
    if missing:
        fail(f"goal.schema.json missing properties: {missing}")
    else:
        pass_("goal.schema.json has all 7 required properties")
        for f in required_fields:
            pass_(f"  property '{f}' present")
else:
    fail("Skipped: goal.schema.json not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 3: goal_type enum includes eternal, gate_target, metric_target
# ═══════════════════════════════════════════════════════════════════════════
say("Test 3: goal_type enum includes eternal, gate_target, metric_target")
if goal_schema:
    goal_type_prop = goal_schema.get("properties", {}).get("goal_type", {})
    enum_vals = goal_type_prop.get("enum", [])
    expected = ["eternal", "gate_target", "metric_target"]
    if set(expected).issubset(set(enum_vals)):
        pass_(f"goal_type enum contains all 3 types: {enum_vals}")
    else:
        missing = [v for v in expected if v not in enum_vals]
        fail(f"goal_type enum missing: {missing} (got {enum_vals})")
else:
    fail("Skipped: goal.schema.json not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 4: never_stop_rules has min_open_hypotheses and exhaustion_policy
# ═══════════════════════════════════════════════════════════════════════════
say("Test 4: never_stop_rules has min_open_hypotheses and exhaustion_policy")
if goal_schema:
    nsr = goal_schema.get("properties", {}).get("never_stop_rules", {})
    nsr_props = nsr.get("properties", {})
    checks = {
        "min_open_hypotheses": nsr_props.get("min_open_hypotheses"),
        "exhaustion_policy": nsr_props.get("exhaustion_policy"),
    }
    all_ok = True
    for name, prop in checks.items():
        if prop is None:
            fail(f"never_stop_rules missing property: '{name}'")
            all_ok = False
        else:
            pass_(f"never_stop_rules has '{name}' (type={prop.get('type')})")
    if all_ok:
        pass_("never_stop_rules has both required fields")

    # Check min_open_hypotheses is integer with minimum >= 1
    min_h = checks.get("min_open_hypotheses", {})
    if min_h.get("type") == "integer":
        pass_("min_open_hypotheses type is integer")
    else:
        fail(f"min_open_hypotheses type should be integer, got {min_h.get('type')}")
    min_val = min_h.get("minimum")
    if min_val is not None and min_val >= 1:
        pass_(f"min_open_hypotheses minimum >= 1 (got {min_val})")
    else:
        fail(f"min_open_hypotheses minimum should be >= 1, got {min_val}")

    # Check exhaustion_policy enum values
    ep = checks.get("exhaustion_policy", {})
    ep_enum = ep.get("enum", [])
    expected_ep = ["generate_ideas", "wait", "stop"]
    if set(expected_ep).issubset(set(ep_enum)):
        pass_(f"exhaustion_policy enum includes all expected values: {ep_enum}")
    else:
        missing_ep = [v for v in expected_ep if v not in ep_enum]
        fail(f"exhaustion_policy enum missing: {missing_ep}")
else:
    fail("Skipped: goal.schema.json not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 5: templates/goal.yaml exists and is valid YAML
# ═══════════════════════════════════════════════════════════════════════════
say("Test 5: templates/goal.yaml exists and is valid YAML")
goal_yaml_path = os.path.join(TEMPLATES_DIR, "goal.yaml")
if os.path.exists(goal_yaml_path):
    pass_("templates/goal.yaml exists")
    try:
        with open(goal_yaml_path) as f:
            goal_data = yaml.safe_load(f)
        if isinstance(goal_data, dict):
            pass_("templates/goal.yaml is valid YAML and parses to a dict")
        else:
            fail(f"templates/goal.yaml parsed to {type(goal_data).__name__}, expected dict")
            goal_data = None
    except yaml.YAMLError as e:
        fail(f"templates/goal.yaml is NOT valid YAML: {e}")
        goal_data = None
else:
    fail("templates/goal.yaml does NOT exist")
    goal_data = None

# ═══════════════════════════════════════════════════════════════════════════
# Test 6: templates/goal.yaml fields match goal.schema.json
# ═══════════════════════════════════════════════════════════════════════════
say("Test 6: templates/goal.yaml fields match goal.schema.json")
if goal_schema and goal_data:
    # Check goal.yaml has no unexpected fields
    allowed = set(goal_schema.get("properties", {}).keys())
    yaml_keys = set(goal_data.keys())
    unexpected = yaml_keys - allowed
    if unexpected:
        fail(f"templates/goal.yaml has unexpected fields (not in schema): {unexpected}")
    else:
        pass_("templates/goal.yaml has no unexpected fields")

    # Check required fields present
    required = goal_schema.get("required", [])
    missing_req = [r for r in required if r not in goal_data]
    if missing_req:
        fail(f"templates/goal.yaml missing required fields: {missing_req}")
    else:
        pass_("templates/goal.yaml has all required fields")

    # Check goal_type is valid
    valid_types = goal_schema["properties"]["goal_type"]["enum"]
    gtype = goal_data.get("goal_type")
    if gtype in valid_types:
        pass_(f"templates/goal.yaml goal_type='{gtype}' is valid")
    else:
        fail(f"templates/goal.yaml goal_type='{gtype}' NOT in valid types {valid_types}")

    # Check never_stop_rules structure
    nsr_yaml = goal_data.get("never_stop_rules", {})
    nsr_schema_props = goal_schema["properties"]["never_stop_rules"].get("properties", {})
    for nsr_field in nsr_schema_props:
        if nsr_field in nsr_yaml:
            pass_(f"templates/goal.yaml never_stop_rules has '{nsr_field}'")
        else:
            fail(f"templates/goal.yaml never_stop_rules MISSING '{nsr_field}'")

    # Check schema_version
    sv = goal_data.get("schema_version")
    sv_schema = goal_schema["properties"]["schema_version"]
    if isinstance(sv, int) and sv >= sv_schema.get("minimum", 1):
        pass_(f"templates/goal.yaml schema_version={sv} is valid")
    else:
        fail(f"templates/goal.yaml schema_version={sv} invalid")

    # Full validation pass
    errors = validate_schema(goal_data, goal_schema)
    if not errors:
        pass_("templates/goal.yaml FULLY VALIDATES against goal.schema.json")
    else:
        fail(f"templates/goal.yaml schema validation errors: {errors}")
elif not goal_schema:
    fail("Skipped: goal.schema.json not loaded")
else:
    fail("Skipped: templates/goal.yaml not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 7: success_criteria items have correct structure per schema
# ═══════════════════════════════════════════════════════════════════════════
say("Test 7: success_criteria items have correct structure")
if goal_schema:
    sc_schema = goal_schema.get("properties", {}).get("success_criteria", {})
    items_schema = sc_schema.get("items", {})
    items_props = items_schema.get("properties", {})

    crit_fields = ["kind", "gate", "source", "field", "op", "value"]
    present = [f for f in crit_fields if f in items_props]
    if len(present) == len(crit_fields):
        pass_(f"success_criteria items have all {len(crit_fields)} properties")
    else:
        missing = [f for f in crit_fields if f not in items_props]
        fail(f"success_criteria items missing properties: {missing}")

    # kind enum check
    kind_prop = items_props.get("kind", {})
    kind_enum = kind_prop.get("enum", [])
    if "praxis_gate" in kind_enum and "metric" in kind_enum:
        pass_("success_criteria kind enum has 'praxis_gate' and 'metric'")
    else:
        fail(f"success_criteria kind enum should have praxis_gate and metric, got {kind_enum}")

    # op enum check
    op_prop = items_props.get("op", {})
    op_enum = op_prop.get("enum", [])
    expected_ops = [">=", "<=", ">", "<", "==", "!="]
    if set(expected_ops).issubset(set(op_enum)):
        pass_("success_criteria op enum has all comparison operators")
    else:
        missing_ops = [v for v in expected_ops if v not in op_enum]
        fail(f"success_criteria op enum missing: {missing_ops}")
else:
    fail("Skipped: goal.schema.json not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 8: stop_conditions enum includes expected safety valves
# ═══════════════════════════════════════════════════════════════════════════
say("Test 8: stop_conditions enum includes expected safety valves")
if goal_schema:
    sc_array = goal_schema.get("properties", {}).get("stop_conditions", {})
    items_schema = sc_array.get("items", {})
    sc_enum = items_schema.get("enum", [])
    expected_stops = ["budget_exhausted", "mode:killed", "human_gate_pending>72h", "family_exhausted"]
    present_stops = [v for v in expected_stops if v in sc_enum]
    if len(present_stops) == len(expected_stops):
        pass_(f"stop_conditions enum has all {len(expected_stops)} safety valves")
    else:
        missing_stops = [v for v in expected_stops if v not in sc_enum]
        fail(f"stop_conditions enum missing: {missing_stops}")
else:
    fail("Skipped: goal.schema.json not loaded")


# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 56)
print(f"  Goal Engine Test Suite Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
