#!/usr/bin/env python3
"""
Events Schema Test Suite
Dedicated tests for events.schema.json — the append-only event log schema
used by the Live Ticker and audit trail.
"""
import json
import os
import sys

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..")
EVENTS_SCHEMA_PATH = os.path.join(SCHEMA_DIR, "events.schema.json")
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


# ── Minimal JSON Schema validator (draft-07 subset) ──────────────────────────
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

    # Properties check
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


# ── Load schema ──────────────────────────────────────────────────────────────
say("Loading events.schema.json")
try:
    with open(EVENTS_SCHEMA_PATH) as f:
        schema = json.load(f)
    pass_("events.schema.json is valid JSON")
except (FileNotFoundError, json.JSONDecodeError) as e:
    fail(f"Failed to load events.schema.json: {e}")
    # Cannot proceed without schema
    print()
    print("=" * 56)
    print(f"  Events Schema Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    print("=" * 56)
    sys.exit(1)


# ── Test 1: Schema has required top-level fields ─────────────────────────────
say("Test 1: events.schema.json has all required properties")
required_properties = ["schema_version", "event_id", "timestamp", "type", "source", "payload", "severity"]
props = schema.get("properties", {})
missing = [p for p in required_properties if p not in props]
if not missing:
    pass_("All required properties present: " + ", ".join(required_properties))
else:
    fail(f"Missing properties: {missing}")


# ── Test 2: Required fields are correctly declared ──────────────────────────
say("Test 2: Required fields match schema requirements")
declared_required = set(schema.get("required", []))
expected_required = {"schema_version", "event_id", "timestamp", "type"}
extra = declared_required - expected_required
missing_req = expected_required - declared_required
if not extra and not missing_req:
    pass_("Required fields exactly match: " + ", ".join(sorted(expected_required)))
else:
    if missing_req:
        fail(f"Missing from required list: {missing_req}")
    if extra:
        fail(f"Extra in required list: {extra}")


# ── Test 3: Event types enum includes expected entries ───────────────────────
say("Test 3: Event type enum contains expected entries")
type_prop = props.get("type", {})
type_enum = type_prop.get("enum", [])
expected_types = [
    "tick_start", "tick_end", "tick_skip",
    "worker_dispatch", "worker_complete", "worker_fail", "worker_abort", "worker_kill",
    "praxis_verify_start", "praxis_verdict",
    "gate_pass", "gate_fail", "gate_hold",
    "goal_status_change",
    "idea_generated", "idea_promoted",
    "merge", "pr_created",
    "budget_warning", "budget_exhausted",
    "human_gate_pending", "human_approve", "human_reject",
    "config_change",
    "error", "warning",
]
missing_types = [t for t in expected_types if t not in type_enum]
if not missing_types:
    pass_(f"All {len(expected_types)} expected event types present")
else:
    fail(f"Missing event types: {missing_types}")


# ── Test 4: Severity enum has expected values ────────────────────────────────
say("Test 4: Severity enum has correct values")
severity_prop = props.get("severity", {})
severity_enum = severity_prop.get("enum", [])
expected_severities = {"info", "warning", "error", "critical"}
if set(severity_enum) == expected_severities:
    pass_("Severity enum correct: " + ", ".join(severity_enum))
else:
    fail(f"Severity enum mismatch: got {severity_enum}, expected {expected_severities}")


# ── Test 5: Valid event passes schema validation ────────────────────────────
say("Test 5: Valid event with all fields passes schema")
valid_event_full = {
    "schema_version": 1,
    "event_id": "evt-001",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "tick_start",
    "source": "orchestrator",
    "project": "AlphaForge",
    "payload": {"tick": 42},
    "severity": "info",
}
errors = validate_schema(valid_event_full, schema)
if not errors:
    pass_("Full valid event passes schema")
else:
    fail(f"Full valid event FAILED: {errors}")


# ── Test 6: Minimal valid event (only required fields) passes ────────────────
say("Test 6: Minimal event (only required fields) passes schema")
valid_event_min = {
    "schema_version": 1,
    "event_id": "evt-002",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "tick_end",
}
errors = validate_schema(valid_event_min, schema)
if not errors:
    pass_("Minimal event passes schema")
else:
    fail(f"Minimal event FAILED: {errors}")


# ── Test 7: Each event type validates correctly ──────────────────────────────
say("Test 7: All event types pass schema validation")
base_event = {
    "schema_version": 1,
    "event_id": "evt-type-xxx",
    "timestamp": "2026-07-08T12:00:00Z",
}
type_failures = []
for etype in expected_types:
    candidate = dict(base_event)
    candidate["event_id"] = f"evt-{etype}"
    candidate["type"] = etype
    errs = validate_schema(candidate, schema)
    if errs:
        type_failures.append(f"{etype}: {errs}")
if not type_failures:
    pass_(f"All {len(expected_types)} event types pass validation")
else:
    fail(f"Event type validation failures: {type_failures}")


# ── Test 8: Invalid event (missing required field) is rejected ──────────────
say("Test 8: Missing required field is rejected")
invalid_missing = {"schema_version": 1}
errors = validate_schema(invalid_missing, schema)
if errors:
    pass_("Missing-required rejected: " + "; ".join(errors))
else:
    fail("Missing-required was NOT rejected")


# ── Test 9: Invalid event type is rejected ───────────────────────────────────
say("Test 9: Invalid event type is rejected")
invalid_type = {
    "schema_version": 1,
    "event_id": "evt-bad",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "nonexistent_type",
}
errors = validate_schema(invalid_type, schema)
if errors:
    pass_("Invalid event type rejected")
else:
    fail("Invalid event type was NOT rejected")


# ── Test 10: Unexpected field is rejected (additionalProperties: false) ─────
say("Test 10: Unexpected field is rejected (additionalProperties: false)")
invalid_extra = {
    "schema_version": 1,
    "event_id": "evt-extra",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "tick_start",
    "bogus_field": "should_not_be_here",
}
errors = validate_schema(invalid_extra, schema)
if errors:
    pass_("Unexpected field rejected: " + "; ".join(errors))
else:
    fail("Unexpected field was NOT rejected")


# ── Test 11: Invalid severity is rejected ────────────────────────────────────
say("Test 11: Invalid severity is rejected")
invalid_sev = {
    "schema_version": 1,
    "event_id": "evt-sev",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "tick_start",
    "severity": "super-critical",
}
errors = validate_schema(invalid_sev, schema)
if errors:
    pass_("Invalid severity rejected")
else:
    fail("Invalid severity was NOT rejected")


# ── Test 12: String properties have correct types ────────────────────────────
say("Test 12: Property types are correct")
type_checks = [
    ("schema_version", "integer"),
    ("event_id", "string"),
    ("timestamp", "string"),
    ("type", "string"),
    ("source", "string"),
    ("project", "string"),
    ("payload", "object"),
    ("severity", "string"),
]
type_errors = []
for prop_name, expected_type in type_checks:
    prop_schema = props.get(prop_name, {})
    actual_type = prop_schema.get("type")
    if actual_type != expected_type:
        type_errors.append(f"{prop_name}: expected type {expected_type}, got {actual_type}")
if not type_errors:
    pass_("All property types match expected types")
else:
    fail("Type mismatches: " + "; ".join(type_errors))


# ── Test 13: Default values are correct ──────────────────────────────────────
say("Test 13: Default values match expectations")
default_checks = [
    ("source", ""),
    ("project", ""),
    ("payload", {}),
    ("severity", "info"),
    ("schema_version", 1),
]
default_errors = []
for prop_name, expected_default in default_checks:
    prop_schema = props.get(prop_name, {})
    actual_default = prop_schema.get("default")
    if actual_default != expected_default:
        default_errors.append(f"{prop_name}: expected default {expected_default!r}, got {actual_default!r}")
if not default_errors:
    pass_("All defaults match expectations")
else:
    fail("Default mismatches: " + "; ".join(default_errors))


# ── Test 14: Event with worker_dispatch passes ───────────────────────────────
say("Test 14: worker_dispatch event with payload passes schema")
worker_dispatch_event = {
    "schema_version": 1,
    "event_id": "evt-worker-dispatch",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "worker_dispatch",
    "source": "orchestrator",
    "project": "AlphaForge",
    "payload": {"worker_id": "w-1", "task": "fix_bug_42", "llm": "claude-opus-4"},
    "severity": "info",
}
errors = validate_schema(worker_dispatch_event, schema)
if not errors:
    pass_("worker_dispatch event passes schema")
else:
    fail(f"worker_dispatch event FAILED: {errors}")


# ── Test 15: praxis_verdict event with payload passes ───────────────────────
say("Test 15: praxis_verdict event with payload passes schema")
praxis_verdict_event = {
    "schema_version": 1,
    "event_id": "evt-praxis-001",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "praxis_verdict",
    "source": "praxis",
    "project": "AlphaForge",
    "payload": {"gate": "finalGate", "result": "PASS", "attempt_id": "att-001"},
    "severity": "info",
}
errors = validate_schema(praxis_verdict_event, schema)
if not errors:
    pass_("praxis_verdict event passes schema")
else:
    fail(f"praxis_verdict event FAILED: {errors}")


# ── Test 16: error event with payload passes ─────────────────────────────────
say("Test 16: error event with payload passes schema")
error_event = {
    "schema_version": 1,
    "event_id": "evt-error-001",
    "timestamp": "2026-07-08T12:00:00Z",
    "type": "error",
    "source": "worker",
    "project": "AlphaForge",
    "payload": {"message": "Out of memory", "exit_code": 137},
    "severity": "error",
}
errors = validate_schema(error_event, schema)
if not errors:
    pass_("error event with error severity passes schema")
else:
    fail(f"error event FAILED: {errors}")


# ── Test 17: Schema uses correct draft-07 $schema ────────────────────────────
say("Test 17: Schema uses draft-07 $schema")
actual_schema_ver = schema.get("$schema", "")
if "draft-07" in actual_schema_ver:
    pass_(f"$schema references draft-07")
else:
    fail(f"$schema is {actual_schema_ver}, expected draft-07")


# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 56)
print(f"  Events Schema Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
