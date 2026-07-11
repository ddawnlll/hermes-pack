#!/usr/bin/env python3
"""
Issue #1 — Schema version bump integration test
Verifies that schema_version bump procedure works end-to-end.
"""
import json, os, sys

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..")
PASS_COUNT = 0
FAIL_COUNT = 0

def pass_(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"\033[1;32m[TEST] PASS:\033[0m {msg}")

def fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"\033[1;31m[TEST] FAIL:\033[0m {msg}")

# ── Test 1: All schemas have schema_version ───────────────────────────────────
print("[TEST] Test 1: All schema files have schema_version")
schema_files = [f for f in os.listdir(SCHEMA_DIR) if f.endswith(".schema.json")]
if not schema_files:
    fail("No schema files found in schema/ directory")
else:
    for sf in sorted(schema_files):
        with open(os.path.join(SCHEMA_DIR, sf)) as f:
            schema = json.load(f)
        props = schema.get("properties", {})
        if "schema_version" in props:
            sv = props["schema_version"]
            if sv.get("minimum") == 1:
                pass_(f"{sf}: schema_version, minimum=1")
            else:
                fail(f"{sf}: schema_version missing minimum")
        else:
            fail(f"{sf}: MISSING schema_version")
    
    # Count
    if len(schema_files) >= 5:
        pass_(f"{len(schema_files)} schema files present (≥5 required)")
    else:
        fail(f"Only {len(schema_files)} schema files, need ≥5")

# ── Test 2: Schema version bump consistency ───────────────────────────────────
print("[TEST] Test 2: Schema version bump consistency")
all_at_v1 = True
for sf in sorted(schema_files):
    with open(os.path.join(SCHEMA_DIR, sf)) as f:
        schema = json.load(f)
    # Check the default value in schema_version property
    sv = schema.get("properties", {}).get("schema_version", {})
    default = sv.get("default", 0)
    if default != 1:
        all_at_v1 = False
        fail(f"{sf}: schema_version default={default}, expected 1")
if all_at_v1:
    pass_("All schemas at schema_version=1")

# ── Test 3: README has schema_version bump procedure ────────────────────────
print("[TEST] Test 3: README documents schema version bump procedure")
readme_path = os.path.join(SCHEMA_DIR, "..", "README.md")
if not os.path.exists(readme_path):
    readme_path = os.path.join(SCHEMA_DIR, "..", "..", "README.md")
if os.path.exists(readme_path):
    with open(readme_path, encoding="utf-8", errors="replace") as f:
        readme = f.read()
    if "schema_version" in readme or "Schema Version Bump" in readme:
        pass_("README documents schema_version bump procedure")
    else:
        fail("README missing schema_version bump documentation")
else:
    fail("README.md not found")

# ── Test 4: All required fields in state.schema.json match templates/state.json
print("[TEST] Test 4: state.schema.json required fields match template")
state_schema_path = os.path.join(SCHEMA_DIR, "state.schema.json")
template_path = os.path.join(SCHEMA_DIR, "..", "templates", "state.json")
if os.path.exists(state_schema_path) and os.path.exists(template_path):
    with open(template_path) as f:
        template = json.load(f)
    with open(state_schema_path) as f:
        state_schema = json.load(f)
    
    required = set(state_schema.get("required", []))
    template_keys = set(template.keys())
    
    missing_from_template = required - template_keys
    if not missing_from_template:
        pass_("All required schema fields present in state.json template")
    else:
        fail(f"Template missing required schema fields: {missing_from_template}")
else:
    fail("state.schema.json or templates/state.json not found")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 56)
print(f"  Schema Contract Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
