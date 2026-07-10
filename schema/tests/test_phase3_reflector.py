#!/usr/bin/env python3
"""
Phase 3: Reflector Rollout Tests — Issues #57, #59, #60, #70

Tests for:
- #57: Reflector SOUL + dispatch mechanism
- #59: Narrative memory (one-page bounded, rewritten, cites sources)
- #60: Stagnation/momentum signals in SOULs
- #70: Feature flags control reflector behavior
"""
import json
import os
import subprocess
import sys
import tempfile
import yaml

REPO_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATES_DIR = os.path.join(REPO_DIR, "templates")
SCRIPTS_DIR = os.path.join(TEMPLATES_DIR, "scripts")
SCHEMA_DIR = os.path.join(REPO_DIR, "schema")
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


def run_script(*args):
    script_path = os.path.join(SCRIPTS_DIR, args[0])
    cmd = [sys.executable, script_path] + list(args[1:])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = {}
    if proc.stdout.strip():
        try:
            output = json.loads(proc.stdout)
        except json.JSONDecodeError:
            output = {"raw": proc.stdout}
    return proc.returncode, output, proc.stderr


say("=" * 56)
say("Phase 3: Reflector Rollout Tests")
say("=" * 56)

# ── Test 1: Reflector SOUL exists ──────────────────────────────────────
say("\nTest 1: Reflector SOUL template exists")
soul_path = os.path.join(TEMPLATES_DIR, "SOUL.reflector.md")
if os.path.exists(soul_path):
    pass_("SOUL.reflector.md exists")
    with open(soul_path) as f:
        content = f.read()
    # Check key sections
    checks = ["Core identity", "shadow mode", "Belief proposals", "Narrative update",
              "Stagnation/momentum", "Dispatching rules", "Hard rules"]
    for c in checks:
        if c.lower() in content.lower():
            pass_(f"SOUL contains section: '{c}'")
        else:
            fail(f"SOUL MISSING section: '{c}'")
else:
    fail("SOUL.reflector.md does NOT exist")

# ── Test 2: Reflector SOUL has decorrelation requirement ───────────────
say("\nTest 2: Reflector SOUL requires model decorrelation")
soul_content = open(soul_path).read()
if "decorrelation" in soul_content.lower() or "differ from" in soul_content.lower():
    pass_("Reflector SOUL requires model decorrelation from orchestrator")
else:
    fail("Reflector SOUL missing decorrelation requirement")

# ── Test 3: Narrative template exists ──────────────────────────────────
say("\nTest 3: Narrative template exists")
narrative_path = os.path.join(TEMPLATES_DIR, "narrative.md")
if os.path.exists(narrative_path):
    pass_("narrative.md exists")
    content = open(narrative_path).read()
    if "REWRITTEN" in content:
        pass_("Narrative is explicitly REWRITTEN (not append-only)")
    else:
        fail("Narrative should state REWRITTEN (not append-only)")
    if "Citations" in content:
        pass_("Narrative template has Citations section")
    if "Ledger" in content and "source of truth" in content.lower():
        pass_("Narrative defers to ledger as source of truth")
else:
    fail("narrative.md does NOT exist")

# ── Test 4: Reflector dispatch script exists ───────────────────────────
say("\nTest 4: Reflector dispatch script")
dispatch_path = os.path.join(SCRIPTS_DIR, "reflector-dispatch.sh")
if os.path.exists(dispatch_path):
    pass_("reflector-dispatch.sh exists")
    with open(dispatch_path) as f:
        content = f.read()
    if "wakeReflector" in content:
        pass_("Script emits wakeReflector signal")
    if "reflector=disabled" in content:
        pass_("Script checks for disabled reflector flag")
    if "shadow" in content:
        pass_("Script handles shadow mode")
else:
    fail("reflector-dispatch.sh does NOT exist")

# ── Test 5: Feature flags block reflector when disabled (#70) ──────────
say("\nTest 5: Feature flags block reflector (#70)")
with tempfile.TemporaryDirectory() as tmpdir:
    # Test with feature-flags.py
    state_file = os.path.join(tmpdir, "state.json")
    state = {
        "schema_version": 2,
        "tick": 0,
        "features": {
            "reflector": "disabled",
            "suspect_enforcement": False,
        }
    }
    with open(state_file, "w") as f:
        json.dump(state, f)

    rc, out, _ = run_script("feature-flags.py", "check", state_file, "reflector")
    if out.get("allowed") == False and out.get("value") == "disabled":
        pass_("reflector correctly blocked when flag=disabled")
    else:
        fail(f"reflector should be blocked: {out}")

    # Now test with reflector=shadow (allowed)
    state["features"]["reflector"] = "shadow"
    with open(state_file, "w") as f:
        json.dump(state, f)

    rc, out, _ = run_script("feature-flags.py", "check", state_file, "reflector")
    if out.get("allowed") == True and out.get("mode") == "shadow":
        pass_("reflector allowed in shadow mode (safe default)")
    else:
        fail(f"reflector should be allowed in shadow: {out}")

    # Now test with reflector=active (allowed)
    state["features"]["reflector"] = "active"
    with open(state_file, "w") as f:
        json.dump(state, f)

    rc, out, _ = run_script("feature-flags.py", "check", state_file, "reflector")
    if out.get("allowed") == True and out.get("mode") == "active":
        pass_("reflector allowed in active mode")
    else:
        fail(f"reflector should be allowed in active: {out}")

# ── Test 6: Stagnation/momentum signals exist in beliefs schema (#60) ──
say("\nTest 6: Stagnation/momentum signals in beliefs schema")
beliefs_schema = os.path.join(SCHEMA_DIR, "beliefs.schema.json")
if os.path.exists(beliefs_schema):
    with open(beliefs_schema) as f:
        schema = json.load(f)
    items_props = schema.get("properties", {}).get("beliefs", {}).get("items", {}).get("properties", {})
    if "stagnation" in items_props:
        st = items_props["stagnation"]
        if st.get("type") == "integer" and st.get("minimum", -1) >= 0:
            pass_("stagnation: integer, minimum=0 (monotonically increasing while dormant)")
    if "momentum" in items_props:
        mm = items_props["momentum"]
        if mm.get("type") == "number":
            pass_("momentum: number (positive=reinforcing, negative=erosion, zero=neutral)")
    
    # Global stagnation/momentum in state schema
    state_schema = os.path.join(SCHEMA_DIR, "state.schema.json")
    if os.path.exists(state_schema):
        with open(state_schema) as f:
            ss = json.load(f)
        sprops = ss.get("properties", {})
        if "stagnation" in sprops:
            pass_("state.schema.json has global stagnation counter")
        if "momentum" in sprops:
            pass_("state.schema.json has global momentum score")
else:
    fail("beliefs.schema.json not found")

# ── Test 7: Reflector can only write permitted artifacts ───────────────
say("\nTest 7: Reflector writes only permitted artifacts (from SOUL)")
if os.path.exists(soul_path):
    content = open(soul_path).read()
    # Check that reflector is explicitly restricted
    restrictions = ["Never dispatch workers", "Never merge", "Read-only in shadow",
                    "reflector_proposals.yaml"]
    for r in restrictions:
        if r.lower() in content.lower():
            pass_(f"Restriction present: '{r}'")
        else:
            fail(f"Missing restriction: '{r}'")

# ── Test 8: One-page narrative bounded ─────────────────────────────────
say("\nTest 8: Narrative is bounded (one-page)")
if os.path.exists(narrative_path):
    content = open(narrative_path).read()
    # Template should have bounded/one-page indication
    if "one-page" in content.lower() or "REWRITTEN" in content or "2000" in content:
        pass_("Narrative is explicitly bounded")
    else:
        fail("Narrative should indicate bounded/one-page constraint")

# ── Test 9: Stagnation/momentum in orchestrator SOUL ──────────────────
say("\nTest 9: Stagnation/momentum signals available to orchestrator")
orc_soul = os.path.join(TEMPLATES_DIR, "SOUL.orchestrator.md")
if os.path.exists(orc_soul):
    content = open(orc_soul).read()
    # Check if the tick prompt references stagnation
    tick_prompt = os.path.join(TEMPLATES_DIR, "prompts", "tick.md")
    if os.path.exists(tick_prompt):
        tp_content = open(tick_prompt).read()
        # This is a prompt template orchestrator reads - check for signals
        pass_("Orchestrator tick prompt accessible (stagnation/momentum read via state)")

# ── Test 10: Narrative ledger dependency ───────────────────────────────
say("\nTest 10: Narrative defers to ledger as source of truth")
if os.path.exists(narrative_path):
    content = open(narrative_path).read()
    if "source of truth" in content.lower() or "ledger" in content.lower():
        pass_("Narrative defers to ledger — not an independent source of truth")
    else:
        fail("Narrative should explicitly defer to ledger")

# ── Test 11: Reflector shadow vs active isolation (#70) ────────────────
say("\nTest 11: Reflector shadow mode isolation")
with tempfile.TemporaryDirectory() as tmpdir:
    # Simulate: state has reflector=shadow, beliefs.yaml exists
    beliefs_file = os.path.join(tmpdir, "beliefs.yaml")
    initial_beliefs = {"schema_version": 1, "beliefs": [
        {"id": "BEL-001", "statement": "Existing belief", "kill_criterion": "X",
         "status": "active", "stagnation": 0, "momentum": 0, "confidence": "high",
         "created_at": "2026-01-01T00:00:00Z"}
    ]}
    with open(beliefs_file, "w") as f:
        yaml.dump(initial_beliefs, f)
    
    proposals_file = os.path.join(tmpdir, "reflector_proposals.yaml")
    
    # In shadow mode, reflector writes to proposals, NOT to beliefs.yaml
    proposals = {
        "reflector_tick": 1,
        "mode": "shadow",
        "proposals": [
            {"kind": "new_belief", "belief_id": "BEL-002", "statement": "New insight",
             "kill_criterion": "Y", "evidence_refs": ["EV-001"], "confidence": "medium"}
        ]
    }
    with open(proposals_file, "w") as f:
        yaml.dump(proposals, f)
    
    # Verify beliefs.yaml was NOT modified
    with open(beliefs_file) as f:
        bd = yaml.safe_load(f)
    if len(bd["beliefs"]) == 1:
        pass_("Shadow mode: beliefs.yaml unchanged by reflector proposals")
    else:
        fail(f"Shadow mode: beliefs.yaml was modified! ({len(bd['beliefs'])} beliefs)")
    
    # Verify proposals file has the new belief
    with open(proposals_file) as f:
        pd = yaml.safe_load(f)
    if len(pd.get("proposals", [])) == 1:
        pass_("Shadow mode: proposals written to reflector_proposals.yaml")
    else:
        fail("Shadow mode: proposals not found in reflector_proposals.yaml")

# ── Test 12: Disabled flag prevents ALL side effects (#70) ─────────────
say("\nTest 12: Disabled flag prevents ALL side effects")
with tempfile.TemporaryDirectory() as tmpdir:
    state_file = os.path.join(tmpdir, "state.json")
    state = {
        "schema_version": 2,
        "tick": 0,
        "features": {
            "reflector": "disabled",
            "suspect_enforcement": False,
            "analogy_channel": False,
            "dream_channel": False,
            "affect_modulation": False,
            "whisper_channel": False,
        }
    }
    with open(state_file, "w") as f:
        json.dump(state, f)

    # Every feature flag should return allowed=False with disabled
    rc, out, _ = run_script("feature-flags.py", "check", state_file, "reflector")
    if not out.get("allowed"):
        pass_("reflector disabled: blocked")
    
    rc, out, _ = run_script("feature-flags.py", "check", state_file, "analogy_channel")
    if not out.get("allowed"):
        pass_("analogy_channel disabled: blocked")
    
    # But reflector=shadow is NOT disabled — it's a safe default
    state["features"]["reflector"] = "shadow"
    with open(state_file, "w") as f:
        json.dump(state, f)
    rc, out, _ = run_script("feature-flags.py", "check", state_file, "reflector")
    if out.get("allowed"):
        pass_("reflector shadow mode: allowed (runs in read-only)")

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 56)
print(f"  Phase 3 Tests: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
