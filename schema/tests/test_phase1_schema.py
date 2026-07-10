#!/usr/bin/env python3
"""
Beliefs Workspace Schema Tests — Issue #56, #58, #60, #69

Tests for:
- beliefs.schema.json structure and validation
- Capacity cap enforcement
- Mandatory kill_criterion
- relies_on in hypotheses
- Provenance records
- Stagnation/momentum fields
- Blame propagation
- Feature flags
"""
import json
import os
import subprocess
import sys
import tempfile
import yaml

REPO_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMA_DIR = os.path.join(REPO_DIR, "schema")
TEMPLATES_DIR = os.path.join(REPO_DIR, "templates")
SCRIPTS_DIR = os.path.join(TEMPLATES_DIR, "scripts")
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


def load_json_schema(path):
    with open(path) as f:
        return json.load(f)


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def run_script(script_name, *args):
    """Run a scripts/ tool and return (exit_code, stdout_json, stderr)."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [sys.executable, script_path] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = {}
    if proc.stdout.strip():
        try:
            output = json.loads(proc.stdout)
        except json.JSONDecodeError:
            output = {"raw": proc.stdout}
    return proc.returncode, output, proc.stderr


# ═══════════════════════════════════════════════════════════════════════════
# Test Suite
# ═══════════════════════════════════════════════════════════════════════════

say("=" * 56)
say("Phase 1: Schema & Operational Tests")
say("=" * 56)

# ── 1. beliefs.schema.json exists and is valid JSON ─────────────────────
say("\nTest 1: beliefs.schema.json exists and is valid")
beliefs_schema_path = os.path.join(SCHEMA_DIR, "beliefs.schema.json")
schema = None
if os.path.exists(beliefs_schema_path):
    pass_("beliefs.schema.json exists")
    try:
        schema = load_json_schema(beliefs_schema_path)
        pass_("beliefs.schema.json is valid JSON")
    except json.JSONDecodeError as e:
        fail(f"beliefs.schema.json is NOT valid JSON: {e}")
else:
    fail("beliefs.schema.json does NOT exist")

# ── 2. beliefs.schema.json has required properties ──────────────────────
say("\nTest 2: beliefs.schema.json has required top-level properties")
if schema:
    props = schema.get("properties", {})
    required = ["schema_version", "beliefs", "capacity", "narrative"]
    missing = [f for f in required if f not in props]
    if missing:
        fail(f"Missing properties: {missing}")
    else:
        pass_("All required properties present: " + ", ".join(required))
else:
    fail("Skipped: schema not loaded")

# ── 3. beliefs array has capacity cap (maxItems) ────────────────────────
say("\nTest 3: beliefs array has capacity cap (maxItems)")
if schema:
    beliefs_prop = schema.get("properties", {}).get("beliefs", {})
    max_items = beliefs_prop.get("maxItems")
    if max_items and max_items > 0:
        pass_(f"beliefs array has maxItems={max_items} capacity cap")
    else:
        fail("beliefs array missing maxItems or maxItems=0")
else:
    fail("Skipped: schema not loaded")

# ── 4. Belief items require kill_criterion ─────────────────────────────
say("\nTest 4: Belief items require kill_criterion")
if schema:
    items_schema = schema.get("properties", {}).get("beliefs", {}).get("items", {})
    items_required = items_schema.get("required", [])
    if "kill_criterion" in items_required:
        pass_("kill_criterion is required for each belief")
    else:
        fail("kill_criterion NOT in required fields for belief items")
else:
    fail("Skipped: schema not loaded")

# ── 5. Belief items have stagnation and momentum ────────────────────────
say("\nTest 5: Belief items have stagnation and momentum fields")
if schema:
    items_props = schema.get("properties", {}).get("beliefs", {}).get("items", {}).get("properties", {})
    if "stagnation" in items_props:
        pass_("stagnation field present on belief items")
    else:
        fail("stagnation field MISSING on belief items")
    if "momentum" in items_props:
        pass_("momentum field present on belief items")
    else:
        fail("momentum field MISSING on belief items")
    if "ttl" in items_props:
        pass_("ttl field present on belief items")
    else:
        fail("ttl field MISSING on belief items")
    if "cooldown_remaining" in items_props:
        pass_("cooldown_remaining field present on belief items")
    else:
        fail("cooldown_remaining field MISSING on belief items")
else:
    fail("Skipped: schema not loaded")

# ── 6. Belief status enum has correct values ────────────────────────────
say("\nTest 6: Belief status enum values")
if schema:
    status_prop = schema.get("properties", {}).get("beliefs", {}).get("items", {}).get("properties", {}).get("status", {})
    enum_vals = set(status_prop.get("enum", []))
    expected = {"active", "suspect", "refuted", "evicted"}
    if enum_vals == expected:
        pass_(f"Belief status enum correct: {sorted(enum_vals)}")
    else:
        fail(f"Belief status enum mismatch: got {enum_vals}")
else:
    fail("Skipped: schema not loaded")

# ── 7. provenance.schema.json exists and is valid ───────────────────────
say("\nTest 7: provenance.schema.json exists")
prov_schema_path = os.path.join(SCHEMA_DIR, "provenance.schema.json")
prov_schema = None
if os.path.exists(prov_schema_path):
    pass_("provenance.schema.json exists")
    try:
        prov_schema = load_json_schema(prov_schema_path)
        pass_("provenance.schema.json is valid JSON")
        prov_required = prov_schema.get("required", [])
        expected_req = ["provenance_id", "entity_type", "entity_id", "channel", "source", "timestamp"]
        if set(expected_req).issubset(set(prov_required)):
            pass_("Provenance schema has all required fields")
        else:
            fail("Provenance schema missing required fields")
    except json.JSONDecodeError as e:
        fail(f"provenance.schema.json is NOT valid JSON: {e}")
else:
    fail("provenance.schema.json does NOT exist")

# ── 8. templates/beliefs.yaml exists ────────────────────────────────────
say("\nTest 8: templates/beliefs.yaml")
beliefs_yaml_path = os.path.join(TEMPLATES_DIR, "beliefs.yaml")
if os.path.exists(beliefs_yaml_path):
    pass_("templates/beliefs.yaml exists")
    try:
        bd = load_yaml(beliefs_yaml_path)
        if isinstance(bd, dict) and "beliefs" in bd:
            pass_("templates/beliefs.yaml is valid")
        else:
            fail("beliefs.yaml missing 'beliefs' key")
    except yaml.YAMLError as e:
        fail(f"beliefs.yaml invalid: {e}")
else:
    fail("templates/beliefs.yaml does NOT exist")

# ── 9. hypothesis.schema.json has relies_on ─────────────────────────────
say("\nTest 9: hypothesis.schema.json has relies_on")
hyp_schema_path = os.path.join(SCHEMA_DIR, "hypothesis.schema.json")
if os.path.exists(hyp_schema_path):
    try:
        hyp_schema = load_json_schema(hyp_schema_path)
        hyp_props = hyp_schema.get("properties", {})
        checks = {"relies_on": "relies_on field", "provenance": "provenance field"}
        all_ok = True
        for field, desc in checks.items():
            if field in hyp_props:
                pass_(f"{desc} present")
            else:
                fail(f"{desc} MISSING")
                all_ok = False
        if all_ok:
            pass_("hypothesis.schema.json complete")
    except Exception as e:
        fail(f"hypothesis.schema.json error: {e}")
else:
    fail("hypothesis.schema.json does NOT exist")

# ── 10. templates/hypothesis.yaml has relies_on ─────────────────────────
say("\nTest 10: templates/hypothesis.yaml has relies_on")
hyp_yaml = os.path.join(TEMPLATES_DIR, "hypothesis.yaml")
if os.path.exists(hyp_yaml):
    hd = load_yaml(hyp_yaml)
    if isinstance(hd, dict) and "relies_on" in hd:
        pass_("relies_on present in hypothesis template")
        if isinstance(hd["relies_on"], list):
            pass_("relies_on is a list (supports [])")
    else:
        fail("relies_on MISSING in hypothesis template")
else:
    fail("templates/hypothesis.yaml does NOT exist")

# ── 11. State schema has v0.5 fields ────────────────────────────────────
say("\nTest 11: State schema has v0.5 fields")
state_schema_path = os.path.join(SCHEMA_DIR, "state.schema.json")
if os.path.exists(state_schema_path):
    state_schema = load_json_schema(state_schema_path)
    state_props = state_schema.get("properties", {})
    v05_fields = {
        "run_id": "Run ID for crash recovery",
        "phase": "Tick phase for crash recovery",
        "beliefs": "Beliefs workspace summary",
        "stagnation": "Global stagnation counter",
        "momentum": "Global momentum score",
        "features": "Feature flags",
        "channel_budgets": "Channel budgets",
        "channel_spend_today": "Channel spend tracking",
        "calibration": "Calibration scores",
    }
    missing = []
    for field, desc in v05_fields.items():
        if field not in state_props:
            missing.append(field)
            fail(f"state.schema.json MISSING '{field}' ({desc})")
        else:
            pass_(f"state.schema.json has '{field}'")
    if not missing:
        pass_("All v0.5 state fields present")
else:
    fail("state.schema.json does NOT exist")

# ── 12. Feature flags default to safe values ────────────────────────────
say("\nTest 12: Feature flags default to safe values")
if os.path.exists(state_schema_path):
    features_prop = load_json_schema(state_schema_path).get("properties", {}).get("features", {}).get("properties", {})
    safe_defaults = {
        "reflector": "shadow",
        "suspect_enforcement": False,
        "analogy_channel": False,
        "dream_channel": False,
        "affect_modulation": False,
        "whisper_channel": False,
    }
    all_safe = True
    for flag, expected in safe_defaults.items():
        actual = features_prop.get(flag, {}).get("default")
        if actual != expected:
            fail(f"Feature '{flag}' default is {actual!r}, expected {expected!r}")
            all_safe = False
        else:
            pass_(f"'{flag}' defaults to {expected!r}")
    if all_safe:
        pass_("ALL feature flags have safe defaults")

# ── 13. Scripts exist and are syntactically valid ───────────────────────
say("\nTest 13: Operational scripts exist")
scripts = ["blame-propagation.py", "provenance-track.py", "feature-flags.py"]
import ast
all_scripts_ok = True
for s in scripts:
    spath = os.path.join(SCRIPTS_DIR, s)
    if os.path.exists(spath):
        try:
            with open(spath) as f:
                ast.parse(f.read())
            pass_(f"{s} exists and is valid Python")
        except SyntaxError as e:
            fail(f"{s}: syntax error: {e}")
            all_scripts_ok = False
    else:
        fail(f"{s} does NOT exist")
        all_scripts_ok = False
if all_scripts_ok:
    pass_("All operational scripts present and valid")

# ── 14. Blame propagation idempotency ──────────────────────────────────
say("\nTest 14: Blame propagation idempotency")
with tempfile.TemporaryDirectory() as tmpdir:
    hyps = [
        {"id": "H-001", "relies_on": [], "status": "active", "title": "Parent", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "H-002", "relies_on": ["H-001"], "status": "active", "title": "Child", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "H-003", "relies_on": ["H-002"], "status": "active", "title": "Grandchild", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "H-004", "relies_on": [], "status": "active", "title": "Independent", "created_at": "2026-01-01T00:00:00Z"},
    ]
    for h in hyps:
        with open(os.path.join(tmpdir, f"{h['id']}.yaml"), "w") as f:
            yaml.dump(h, f)

    # First propagation (transitive: H-001->H-002->H-003 = 3 affected including root)
    rc1, out1, _ = run_script("blame-propagation.py", "propagate", tmpdir, "H-001")
    total = out1.get("total_affected", 0)
    propagated = out1.get("propagated_to", [])
    if total == 3:
        pass_(f"First propagation: {total} affected (H-001 root + H-002 + H-003 transitive)")
    else:
        fail(f"Expected 3 affected (transitive), got {total}: {propagated}")

    # Second propagation (idempotent: 0 new, 2 already failed - H-002, H-003)
    rc2, out2, _ = run_script("blame-propagation.py", "propagate", tmpdir, "H-001")
    if out2.get("total_affected") == 0 and len(out2.get("already_failed", [])) == 2:
        pass_("Second propagation is idempotent: 0 new, 2 already failed (transitive deps)")
    else:
        fail(f"Not idempotent: affected={out2.get('total_affected')}, already_failed={len(out2.get('already_failed', []))}")

    # Independent hypothesis still active
    h4 = load_yaml(os.path.join(tmpdir, "H-004.yaml"))
    if h4.get("status") == "active":
        pass_("Independent hypothesis unaffected")
    else:
        fail(f"Independent became {h4.get('status')}")

    # Check blocked
    rc3, out3, _ = run_script("blame-propagation.py", "check", tmpdir, "H-002")
    if out3.get("blocked"):
        pass_("Dependent hypothesis correctly detected as blocked")
    else:
        fail("Dependent should be blocked")

# ── 15. Provenance recording and validation ─────────────────────────────
say("\nTest 15: Provenance recording and validation")
with tempfile.TemporaryDirectory() as tmpdir:
    rc1, out1, _ = run_script("provenance-track.py", "record", tmpdir,
                               "hypothesis", "H-001", "orchestrator",
                               "--source=tick-42", "--cost=0.05")
    if out1.get("status") == "recorded":
        pass_(f"Provenance recorded: {out1.get('provenance_id')}")
    else:
        fail(f"Provenance NOT recorded: {out1}")

    # Idempotency (same entity+channel+source)
    rc2, out2, _ = run_script("provenance-track.py", "record", tmpdir,
                               "hypothesis", "H-001", "orchestrator",
                               "--source=tick-42", "--cost=0.05")
    if out2.get("status") == "exists":
        pass_("Duplicate provenance correctly deduplicated")
    else:
        fail(f"Not deduplicated: {out2}")

    # Validation PASS
    rc3, out3, _ = run_script("provenance-track.py", "validate", tmpdir, "hypothesis", "H-001")
    if out3.get("verdict") == "PASS":
        pass_("Validation PASS for recorded entity")
    else:
        fail(f"Validation should PASS: {out3}")

    # Validation FAIL for unrecorded merge
    rc4, out4, _ = run_script("provenance-track.py", "validate", tmpdir, "merge", "MERGE-001")
    if rc4 != 0 and out4.get("verdict") == "FAIL":
        pass_("Validation FAIL for unrecorded merge (correct)")
    else:
        fail(f"Merge should FAIL validation: {out4}")

    # Generate report
    rc5, out5, _ = run_script("provenance-track.py", "report", tmpdir, "--days=30")
    if out5.get("total_events", 0) >= 1:
        pass_(f"Provenance report generated: {out5.get('total_events')} events")
    else:
        fail(f"Report should have events: {out5}")

# ── 16. Feature flags gate correctly ───────────────────────────────────
say("\nTest 16: Feature flags gate correctly")
with tempfile.TemporaryDirectory() as tmpdir:
    state_file = os.path.join(tmpdir, "state.json")
    state = {
        "schema_version": 2,
        "tick": 0,
        "features": {
            "reflector": "shadow",
            "suspect_enforcement": False,
            "analogy_channel": False,
            "dream_channel": True,
        }
    }
    with open(state_file, "w") as f:
        json.dump(state, f)

    # analogy_channel disabled
    rc1, out1, _ = run_script("feature-flags.py", "check", state_file, "analogy_channel")
    if rc1 != 0 and out1.get("allowed") == False:
        pass_("analogy_channel blocked when disabled")
    else:
        fail(f"analogy_channel should be blocked: {out1}")

    # reflector shadow mode = allowed
    rc2, out2, _ = run_script("feature-flags.py", "check", state_file, "reflector")
    if rc2 == 0 and out2.get("allowed") == True and out2.get("mode") == "shadow":
        pass_("reflector allowed in shadow mode")
    else:
        fail(f"reflector should be allowed: {out2}")

    # dream_channel enabled
    rc3, out3, _ = run_script("feature-flags.py", "check", state_file, "dream_channel")
    if rc3 == 0 and out3.get("allowed") == True:
        pass_("dream_channel allowed when enabled")
    else:
        fail(f"dream_channel should be allowed: {out3}")

    # Unknown feature
    rc4, out4, _ = run_script("feature-flags.py", "check", state_file, "nonexistent")
    if rc4 != 0 and out4.get("allowed") == False:
        pass_("Unknown feature correctly rejected")
    else:
        fail(f"Unknown feature should be rejected: {out4}")

    # Set feature flag
    rc5, out5, _ = run_script("feature-flags.py", "set", state_file, "analogy_channel", "true")
    if out5.get("changed"):
        pass_("Feature flag set correctly")

    # Now analogy should be allowed
    rc6, out6, _ = run_script("feature-flags.py", "check", state_file, "analogy_channel")
    if rc6 == 0 and out6.get("allowed") == True:
        pass_("analogy_channel allowed after enabling")
    else:
        fail(f"analogy_channel should be allowed after set: {out6}")

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 56)
print(f"  Phase 1 Tests: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
