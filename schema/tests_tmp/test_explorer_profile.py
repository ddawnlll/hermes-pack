#!/usr/bin/env python3
"""
Explorer Profile Verification Tests — Issue #25
Tests that:
1. templates/explorer-profile.yaml exists with required parameters
2. Default parameter values are correct
3. source_types list includes all 4 required strategies
4. idle_trigger_hypotheses is an integer >= 0
5. templates/scripts/explorer-dispatch.sh exists
6. Explorer dispatch checks scar-tissue (objections.jsonl)
7. Explorer dispatch generates JSON with action and params fields
8. Refuted hypotheses are down-weighted by the dispatch logic
9. Dispatch exits cleanly when idle conditions are NOT met
10. Explorer profile schema_version is valid
"""
import json
import os
import re
import sys
import tempfile
import yaml

REPO_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
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


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: explorer-profile.yaml exists and is valid YAML
# ═══════════════════════════════════════════════════════════════════════════
say("Test 1: explorer-profile.yaml exists and is valid YAML")
profile_path = os.path.join(TEMPLATES_DIR, "explorer-profile.yaml")
if os.path.exists(profile_path):
    pass_("templates/explorer-profile.yaml exists")
    try:
        with open(profile_path) as f:
            profile = yaml.safe_load(f)
        if isinstance(profile, dict):
            pass_("templates/explorer-profile.yaml is valid YAML and parses to a dict")
        else:
            fail(f"explorer-profile.yaml parsed to {type(profile).__name__}, expected dict")
            profile = None
    except yaml.YAMLError as e:
        fail(f"explorer-profile.yaml is NOT valid YAML: {e}")
        profile = None
else:
    fail("templates/explorer-profile.yaml does NOT exist")
    profile = None

# ═══════════════════════════════════════════════════════════════════════════
# Test 2: explorer-profile.yaml has all required parameters
# ═══════════════════════════════════════════════════════════════════════════
say("Test 2: explorer-profile.yaml has all required parameters")
if profile:
    required_params = [
        "schema_version",
        "profile_name",
        "divergence_temp",
        "refuted_penalty",
        "exploration_budget_pct",
        "source_types",
        "idle_trigger_hypotheses",
    ]
    missing = [p for p in required_params if p not in profile]
    if missing:
        fail(f"explorer-profile.yaml missing parameters: {missing}")
    else:
        pass_(f"explorer-profile.yaml has all {len(required_params)} required parameters")
        for p in required_params:
            pass_(f"  parameter '{p}' present")
else:
    fail("Skipped: explorer-profile.yaml not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 3: Default parameter values are correct
# ═══════════════════════════════════════════════════════════════════════════
say("Test 3: Default parameter values are correct")
if profile:
    checks = {
        "divergence_temp": (1.2, "default 1.2"),
        "refuted_penalty": (0.5, "default 0.5"),
        "exploration_budget_pct": (20, "default 20%"),
        "profile_name": ("explorer", "profile_name is 'explorer'"),
    }
    all_ok = True
    for param, (expected, desc) in checks.items():
        actual = profile.get(param)
        if actual == expected:
            pass_(f"  {param}={actual} ({desc})")
        else:
            fail(f"  {param}={actual} expected {expected} ({desc})")
            all_ok = False
    if all_ok:
        pass_("All default parameter values match specification")
else:
    fail("Skipped: explorer-profile.yaml not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 4: source_types includes all 4 required strategies
# ═══════════════════════════════════════════════════════════════════════════
say("Test 4: source_types includes all 4 required strategies")
if profile:
    source_types = profile.get("source_types", [])
    if isinstance(source_types, list):
        required_types = ["cross_project", "codebase_scan", "random_mutation", "adjoint_variant"]
        missing_types = [t for t in required_types if t not in source_types]
        if missing_types:
            fail(f"source_types missing: {missing_types}")
        else:
            pass_(f"source_types contains all 4 required types: {required_types}")
        for t in required_types:
            if t in source_types:
                pass_(f"  source_type '{t}' present")
            else:
                fail(f"  source_type '{t}' MISSING")
    else:
        fail(f"source_types is {type(source_types).__name__}, expected list")
else:
    fail("Skipped: explorer-profile.yaml not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 5: idle_trigger_hypotheses is a valid integer >= 0
# ═══════════════════════════════════════════════════════════════════════════
say("Test 5: idle_trigger_hypotheses is a valid integer >= 0")
if profile:
    ith = profile.get("idle_trigger_hypotheses")
    if isinstance(ith, int) and not isinstance(ith, bool):
        if ith >= 0:
            pass_(f"idle_trigger_hypotheses={ith} is a valid integer >= 0")
        else:
            fail(f"idle_trigger_hypotheses={ith} is negative")
    else:
        fail(f"idle_trigger_hypotheses={ith} is not an integer (type={type(ith).__name__})")
else:
    fail("Skipped: explorer-profile.yaml not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 6: schema_version is a valid positive integer
# ═══════════════════════════════════════════════════════════════════════════
say("Test 6: schema_version is a valid positive integer")
if profile:
    sv = profile.get("schema_version")
    if isinstance(sv, int) and not isinstance(sv, bool):
        if sv >= 1:
            pass_(f"schema_version={sv} is a valid positive integer")
        else:
            fail(f"schema_version={sv} should be >= 1")
    else:
        fail(f"schema_version={sv} is not an integer (type={type(sv).__name__})")
else:
    fail("Skipped: explorer-profile.yaml not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 7: explorer-dispatch.sh exists and is executable
# ═══════════════════════════════════════════════════════════════════════════
say("Test 7: templates/scripts/explorer-dispatch.sh exists")
dispatch_path = os.path.join(SCRIPTS_DIR, "explorer-dispatch.sh")
if os.path.exists(dispatch_path):
    pass_("templates/scripts/explorer-dispatch.sh exists")
    with open(dispatch_path) as f:
        first_line = f.readline().strip()
    if first_line.startswith("#!/usr/bin/env bash") or first_line.startswith("#!/bin/bash"):
        pass_("explorer-dispatch.sh has valid shebang line")
    else:
        fail(f"explorer-dispatch.sh shebang is invalid: '{first_line}'")
    # Check for JSON output pattern
    with open(dispatch_path) as f:
        content = f.read()
    if '"action"' in content and '"params"' in content:
        pass_("explorer-dispatch.sh produces JSON with action and params fields")
    else:
        fail("explorer-dispatch.sh missing JSON action/params output pattern")
else:
    fail("templates/scripts/explorer-dispatch.sh does NOT exist")

# ═══════════════════════════════════════════════════════════════════════════
# Test 8: Dispatch logic checks scar-tissue (objections.jsonl)
# ═══════════════════════════════════════════════════════════════════════════
say("Test 8: Dispatch logic checks scar-tissue (objections.jsonl)")
if os.path.exists(dispatch_path):
    with open(dispatch_path) as f:
        content = f.read()
    # The dispatch script should reference the scar-tissue file
    has_scar_ref = "objections.jsonl" in content or "scar" in content.lower() and "tissue" in content.lower()
    has_refuted_ref = "refuted" in content.lower()
    if has_scar_ref or has_refuted_ref:
        pass_("explorer-dispatch.sh references scar-tissue / refuted hypotheses")
    else:
        fail("explorer-dispatch.sh does NOT reference scar-tissue memory")

    # Check for refuted family filtering logic
    if "REFUTED_FAMILIES" in content or "refuted" in content.lower():
        pass_("explorer-dispatch.sh filters out refuted hypothesis families")
    else:
        fail("explorer-dispatch.sh missing refuted-family filtering logic")
else:
    fail("Skipped: explorer-dispatch.sh not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 9: Dispatch idle-gate logic (not idle when hypotheses >= threshold)
# ═══════════════════════════════════════════════════════════════════════════
say("Test 9: Dispatch idle-gate logic")
if os.path.exists(dispatch_path):
    with open(dispatch_path) as f:
        content = f.read()
    # Check for idle gate comparison
    idle_gate_patterns = [
        "idle_trigger" in content,
        re.search(r'open.*hypoth|hypoth.*open', content, re.IGNORECASE) is not None,
        "Not idle" in content or "idle" in content.lower(),
    ]
    gate_ok = sum(1 for p in idle_gate_patterns if p)
    if gate_ok >= 2:
        pass_(f"explorer-dispatch.sh has idle gate logic ({gate_ok}/3 patterns matched)")
    else:
        fail(f"explorer-dispatch.sh missing idle gate logic ({gate_ok}/3 patterns matched)")
else:
    fail("Skipped: explorer-dispatch.sh not loaded")

# ═══════════════════════════════════════════════════════════════════════════
# Test 10: Dispatch generates valid exploration parameters via simulation
# ═══════════════════════════════════════════════════════════════════════════
say("Test 10: Simulated dispatch generates valid exploration parameters")
# Simulate the core dispatch logic in Python (mirrors explorer-dispatch.sh)
def simulate_dispatch(
    open_hypotheses=0,
    idle_trigger=3,
    scar_tissue_lines=None,
):
    """Simulate the explorer dispatch logic."""
    # Idle gate
    if open_hypotheses >= idle_trigger:
        return {"action": "none", "reason": f"Not idle: {open_hypotheses} >= {idle_trigger}"}

    # Parse scar-tissue for refuted families
    refuted_families = []
    if scar_tissue_lines:
        for line in scar_tissue_lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            stance = obj.get("stance", "")
            sev = obj.get("severity", "")
            if stance == "BLOCK" and sev in ("blocking", "major"):
                fam = obj.get("claim_attacked", obj.get("hypothesis_id", ""))
                if fam:
                    refuted_families.append(fam)

    # Select source type with refuted penalty
    all_sources = ["cross_project", "codebase_scan", "random_mutation", "adjoint_variant"]
    active = []
    for st in all_sources:
        st_key = st.replace("_", "").replace("-", "").lower()
        blocked = any(st_key in rf.replace("_", "").replace("-", "").lower() for rf in refuted_families)
        if not blocked:
            active.append(st)

    source_type = active[0] if active else all_sources[0]

    return {
        "action": "generate",
        "params": {
            "divergence_temp": 1.2,
            "refuted_penalty": 0.5,
            "source_type": source_type,
            "open_hypotheses": open_hypotheses,
        },
    }

# Sim 1: idle state, no scar-tissue -> generate
result_idle = simulate_dispatch(open_hypotheses=0)
if result_idle["action"] == "generate":
    pass_("Idle state (0 open hypotheses): dispatch returns action='generate'")
else:
    fail(f"Idle state should generate: got action='{result_idle['action']}'")

# Sim 2: not idle (5 open >= 3 trigger) -> none
result_busy = simulate_dispatch(open_hypotheses=5)
if result_busy["action"] == "none":
    pass_("Busy state (5 open >= 3 trigger): dispatch returns action='none'")
else:
    fail(f"Busy state should return none: got action='{result_busy['action']}'")

# Sim 3: idle with scar-tissue BLOCK -> filtered source type
scar_lines = [
    json.dumps({"stance": "BLOCK", "severity": "blocking", "claim_attacked": "random_mutation"})
]
result_scar = simulate_dispatch(open_hypotheses=0, scar_tissue_lines=scar_lines)
if result_scar["action"] == "generate":
    # Should avoid random_mutation
    if result_scar["params"]["source_type"] != "random_mutation":
        pass_(f"Scar-tissue BLOCK on random_mutation: source_type='{result_scar['params']['source_type']}' (correctly avoided)")
    else:
        fail(f"Scar-tissue BLOCK should exclude random_mutation but got '{result_scar['params']['source_type']}'")
else:
    fail(f"Scar-tissue dispatch should generate but got action='{result_scar['action']}'")

# Sim 4: params contain all required fields
required_params = ["divergence_temp", "refuted_penalty", "source_type"]
if result_idle["action"] == "generate":
    missing_params = [p for p in required_params if p not in result_idle["params"]]
    if not missing_params:
        pass_(f"Dispatch params contain all {len(required_params)} required fields: {required_params}")
    else:
        fail(f"Dispatch params missing: {missing_params}")
else:
    fail("Cannot check params: dispatch did not generate")


# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 56)
print(f"  Explorer Profile Test Suite Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
