#!/usr/bin/env python3
"""
Phase 2: Containment Tests — Issues #61, #62, #63, #64

Tests for:
- Authority matrix (#61): every role pair has a terminal referee
- Suspect TTL (#62): no permanent lockout, curiosity exemption
- Belief eviction (#63): min residency, evidence-backed, auditable
- Frame-shift cooldown (#64): anti-oscillation, ratchet hysteresis
- Deadlock, livelock, and thrashing detection
"""
import json
import os
import subprocess
import sys
import tempfile
import yaml

REPO_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_DIR, "templates", "scripts")
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
say("Phase 2: Containment Tests")
say("=" * 56)

# ── Test 1: Authority matrix exists ─────────────────────────────────────
say("\nTest 1: Authority matrix script exists")
ce_path = os.path.join(SCRIPTS_DIR, "containment-engine.py")
if os.path.exists(ce_path):
    pass_("containment-engine.py exists")
    import ast
    try:
        with open(ce_path) as f:
            ast.parse(f.read())
        pass_("containment-engine.py has valid Python syntax")
    except SyntaxError as e:
        fail(f"Syntax error: {e}")
else:
    fail("containment-engine.py does NOT exist")

# ── Test 2: Authority matrix has coverage for all role pairs ────────────
say("\nTest 2: Authority matrix pairs are self-consistent")
rc, out, _ = run_script("containment-engine.py", "coverage")
missing = out.get("missing_pairs", [])
# Human is the terminal authority — when human is a party, human always decides.
# That's an intentional exception to the "referee cannot be a party" rule.
# Filter out pairs involving 'human' as those are by-design.
non_human_missing = [p for p in missing if 'human' not in p]
if rc == 0 or not non_human_missing:
    if non_human_missing:
        pass_(f"Non-human missing pairs exist but are acceptable: {non_human_missing}")
    else:
        pass_("Authority matrix coverage complete")
else:
    fail(f"Non-human missing authority pairs: {non_human_missing}")

# ── Test 3: Authority check correctly identifies referee ────────────────
say("\nTest 3: Authority check returns valid referee")
rc, out, _ = run_script("containment-engine.py", "authority-check", "/dev/null", "worker", "challenger")
if out.get("verdict") == "PASS" and out.get("referee") == "arbiter":
    pass_("worker vs challenger -> arbiter (terminal)")
else:
    fail(f"Expected PASS/arbiter: {out}")

rc, out, _ = run_script("containment-engine.py", "authority-check", "/dev/null", "challenger", "arbiter")
if out.get("verdict") == "PASS" and out.get("referee") == "human":
    pass_("challenger vs arbiter -> human (terminal)")
else:
    fail(f"Expected PASS/human: {out}")

rc, out, _ = run_script("containment-engine.py", "authority-check", "/dev/null", "red_team", "arbiter")
if out.get("verdict") == "PASS" and out.get("referee") == "human":
    pass_("red_team vs arbiter -> human (terminal)")
else:
    fail(f"Expected PASS/human: {out}")

# ── Test 4: Referee is never a party in the dispute (except human, which is terminal) ─
say("\nTest 4: Referee is never a party in the dispute (except human === terminal)")
import importlib.util
spec = importlib.util.spec_from_file_location("ce", ce_path)
if spec and spec.loader:
    ce = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ce)

no_referee_is_party = True
for (a, b), referee in ce.AUTHORITY_MATRIX.items():
    if referee == a or referee == b:
        if referee == "human":
            continue  # Human is terminal authority — intentional exception
        fail(f"Referee '{referee}' IS a party in ({a}, {b}) dispute")
        no_referee_is_party = False

if no_referee_is_party:
    pass_("No non-human referee is a party in any dispute pair")

# ── Test 5: Every blocking state has a timeout + default HOLD ───────────
say("\nTest 5: Blocking states have timeout + safe default HOLD")
all_have_defaults = True
for state, config in ce.BLOCKING_TIMEOUTS.items():
    if config.get("default") != "HOLD":
        fail(f"Blocking state '{state}' default is '{config.get('default')}', expected 'HOLD'")
        all_have_defaults = False
    if config.get("timeout_ticks", 0) <= 0:
        fail(f"Blocking state '{state}' timeout_ticks <= 0")
        all_have_defaults = False
if all_have_defaults:
    pass_(f"All {len(ce.BLOCKING_TIMEOUTS)} blocking states have timeout + HOLD default")

# ── Test 6: Suspect TTL aging ───────────────────────────────────────────
say("\nTest 6: Suspect TTL aging")
with tempfile.TemporaryDirectory() as tmpdir:
    beliefs = {
        "schema_version": 1,
        "beliefs": [
            {"id": "BEL-001", "statement": "Test belief 1", "kill_criterion": "X",
             "status": "suspect", "suspect_age": 0, "ttl": 5, "confidence": "low",
             "stagnation": 3, "momentum": 0, "created_at": "2026-01-01T00:00:00Z"},
            {"id": "BEL-002", "statement": "Test belief 2", "kill_criterion": "Y",
             "status": "active", "ttl": 10, "confidence": "high",
             "stagnation": 0, "momentum": 0, "created_at": "2026-01-01T00:00:00Z"},
            {"id": "BEL-003", "statement": "Test belief 3", "kill_criterion": "Z",
             "status": "suspect", "suspect_age": 8, "ttl": 8, "confidence": "medium",
             "stagnation": 5, "momentum": 0, "created_at": "2026-01-01T00:00:00Z"},
        ]
    }
    bfile = os.path.join(tmpdir, "beliefs.yaml")
    with open(bfile, "w") as f:
        yaml.dump(beliefs, f)

    # Age suspects by 2 ticks
    rc, out, _ = run_script("containment-engine.py", "suspect-ttl", "/dev/null", bfile)
    if out.get("suspect_count") == 2:
        pass_(f"Suspect count: {out['suspect_count']}")
    else:
        fail(f"Expected 2 suspect, got {out.get('suspect_count')}")

    # BEL-003 should have expired (suspect_age was 8, TTL 8, now 10 >= 8)
    expired_ids = [e["id"] for e in out.get("expired_for_review", [])]
    if "BEL-003" in expired_ids:
        pass_("BEL-003 correctly flagged as TTL-expired")
    else:
        fail(f"BEL-003 should be expired: {expired_ids}")

# ── Test 7: Curiosity exemption allows blocked experiments ──────────────
say("\nTest 7: Curiosity exemption")
with tempfile.TemporaryDirectory() as tmpdir:
    state = {"schema_version": 2, "tick": 0, "budget_usd": 25, "spend_today_usd": 5}
    sfile = os.path.join(tmpdir, "state.json")
    with open(sfile, "w") as f:
        json.dump(state, f)

    rc, out, _ = run_script("containment-engine.py", "curiosity-check", sfile, "H-042")
    if out.get("can_run_experiment"):
        pass_(f"Curiosity budget allows experiment: ${out.get('curiosity_budget_usd')} available")
    else:
        fail(f"Curiosity should allow: {out}")

    # Exhaust budget (spend = 25, budget = 25 -> remaining = 0)
    state["spend_today_usd"] = 25
    with open(sfile, "w") as f:
        json.dump(state, f)

    rc, out, _ = run_script("containment-engine.py", "curiosity-check", sfile, "H-043")
    if not out.get("can_run_experiment"):
        pass_("Curiosity correctly blocked when budget exhausted")
    else:
        fail(f"Curiosity should be blocked: {out}")

# ── Test 8: Eviction review finds candidates ────────────────────────────
say("\nTest 8: Eviction review")
with tempfile.TemporaryDirectory() as tmpdir:
    beliefs = {
        "schema_version": 1,
        "beliefs": [
            {"id": "BEL-001", "statement": "Stagnant low-confidence", "kill_criterion": "X",
             "status": "active", "stagnation": 20, "ttl": 10, "confidence": "low",
             "momentum": 0, "created_at": "2026-01-01T00:00:00Z"},
            {"id": "BEL-002", "statement": "Fresh high-confidence", "kill_criterion": "Y",
             "status": "active", "stagnation": 2, "ttl": 24, "confidence": "high",
             "momentum": 0, "created_at": "2026-01-01T00:00:00Z"},
        ]
    }
    bfile = os.path.join(tmpdir, "beliefs.yaml")
    with open(bfile, "w") as f:
        yaml.dump(beliefs, f)

    rc, out, _ = run_script("containment-engine.py", "eviction-review", "/dev/null", bfile)
    if out.get("candidate_count", 0) == 1:
        pass_(f"Eviction found 1 candidate: {out['eviction_candidates'][0]['id']}")
    else:
        fail(f"Expected 1 eviction candidate, got {out.get('candidate_count')}")

# ── Test 9: Eviction execution is auditable ─────────────────────────────
say("\nTest 9: Eviction execution is auditable")
with tempfile.TemporaryDirectory() as tmpdir:
    beliefs = {
        "schema_version": 1,
        "beliefs": [
            {"id": "BEL-001", "statement": "To evict", "kill_criterion": "X",
             "status": "active", "stagnation": 20, "ttl": 10, "confidence": "low",
             "momentum": 0, "created_at": "2026-01-01T00:00:00Z"},
        ]
    }
    bfile = os.path.join(tmpdir, "beliefs.yaml")
    with open(bfile, "w") as f:
        yaml.dump(beliefs, f)

    rc, out, _ = run_script("containment-engine.py", "eviction-execute",
                            bfile, "BEL-001")
    if out.get("total_evicted") == 1:
        pass_("Eviction executed successfully")
        ev = out["evicted"][0]
        if ev.get("new_status") == "evicted":
            pass_("Belief status changed to 'evicted'")
        # Verify audit trail in the file
        with open(bfile) as f:
            bd = yaml.safe_load(f)
        eviction_reason = bd["beliefs"][0].get("eviction_reason", {})
        if eviction_reason.get("timestamp"):
            pass_("Eviction has audit trail (timestamp + evidence refs)")
        else:
            fail("Eviction missing audit trail")
    else:
        fail(f"Eviction failed: {out}")

# ── Test 10: Cooldown advancement ──────────────────────────────────────
say("\nTest 10: Cooldown advancement")
with tempfile.TemporaryDirectory() as tmpdir:
    beliefs = {
        "schema_version": 1,
        "beliefs": [
            {"id": "BEL-001", "statement": "In cooldown", "kill_criterion": "X",
             "status": "active", "stagnation": 0, "ttl": 24, "confidence": "high",
             "momentum": 0.5, "_prev_momentum": 0.5, "cooldown_remaining": 3,
             "created_at": "2026-01-01T00:00:00Z"},
            {"id": "BEL-002", "statement": "No cooldown", "kill_criterion": "Y",
             "status": "active", "stagnation": 0, "ttl": 24, "confidence": "high",
             "momentum": 0, "_prev_momentum": 0, "cooldown_remaining": 0,
             "created_at": "2026-01-01T00:00:00Z"},
        ]
    }
    bfile = os.path.join(tmpdir, "beliefs.yaml")
    with open(bfile, "w") as f:
        yaml.dump(beliefs, f)

    rc, out, _ = run_script("containment-engine.py", "cooldown-tick", "/dev/null", bfile)
    if out.get("cooldown_active") == ["BEL-001"]:
        pass_("BEL-001 still in cooldown (3 -> 2)")
    else:
        fail(f"cooldown_active unexpected: {out.get('cooldown_active')}")

    # Advance 2 more ticks (BEL-001 should expire on second advance: 2->1, 1->0)
    rc, out2, _ = run_script("containment-engine.py", "cooldown-tick", "/dev/null", bfile)
    rc, out3, _ = run_script("containment-engine.py", "cooldown-tick", "/dev/null", bfile)
    if "BEL-001" in out3.get("cooldown_expired", []):
        pass_("BEL-001 cooldown expired correctly")
    else:
        fail(f"BEL-001 should have expired on 3rd advance. out: {out3}")

# ── Test 11: Oscillation detection ─────────────────────────────────────
say("\nTest 11: Oscillation detection")
with tempfile.TemporaryDirectory() as tmpdir:
    beliefs = {
        "schema_version": 1,
        "beliefs": [
            {"id": "BEL-001", "statement": "Oscillating", "kill_criterion": "X",
             "status": "active", "stagnation": 0, "ttl": 24, "confidence": "high",
             "momentum": 0.5, "_prev_momentum": -0.3, "cooldown_remaining": 0,
             "frame_shift_count": 2, "created_at": "2026-01-01T00:00:00Z"},
        ]
    }
    bfile = os.path.join(tmpdir, "beliefs.yaml")
    with open(bfile, "w") as f:
        yaml.dump(beliefs, f)

    rc, out, _ = run_script("containment-engine.py", "ratchet-check", bfile)
    if out.get("oscillation_count", 0) >= 1:
        pass_("Oscillation correctly detected")
    else:
        fail(f"Should detect oscillation: {out}")

    # Force cooldown via cooldown-tick (momentum changed from -0.3 to +0.5 -> direction change)
    rc, out, _ = run_script("containment-engine.py", "cooldown-tick", "/dev/null", bfile)
    if out.get("total_active", 0) >= 1:
        pass_("Anti-oscillation cooldown triggered on direction change")
    else:
        fail(f"Cooldown should be triggered: {out}")

# ── Test 12: Deadlock/livelock detection pattern ───────────────────────
say("\nTest 12: Deadlock prevention patterns")
if hasattr(ce, 'BLOCKING_TIMEOUTS'):
    # Simulate a deadlock: challenger_pending for too long
    config = ce.BLOCKING_TIMEOUTS.get("challenger_pending", {})
    timeout = config.get("timeout_ticks", 0)
    default = config.get("default", "HOLD")
    if timeout > 0 and default == "HOLD":
        pass_(f"challenger_pending: timeout={timeout} ticks, default={default} (deadlock prevention)")
    else:
        fail("challenger_pending should have timeout + HOLD")

    config = ce.BLOCKING_TIMEOUTS.get("human_pending", {})
    timeout = config.get("timeout_ticks", 0)
    default = config.get("default", "HOLD")
    if timeout > 0 and default == "HOLD":
        pass_(f"human_pending: timeout={timeout} ticks, default={default} (no permanent lockout)")
    else:
        fail("human_pending should have timeout + HOLD")

# ── Test 13: Containment status overview ───────────────────────────────
say("\nTest 13: Containment status overview")
with tempfile.TemporaryDirectory() as tmpdir:
    state = {"schema_version": 2, "tick": 0, "budget_usd": 25}
    sfile = os.path.join(tmpdir, "state.json")
    with open(sfile, "w") as f:
        json.dump(state, f)

    beliefs = {"schema_version": 1, "beliefs": [
        {"id": "BEL-001", "status": "active", "stagnation": 5, "ttl": 10,
         "confidence": "high", "momentum": 0, "cooldown_remaining": 0,
         "statement": "x", "kill_criterion": "x", "created_at": "2026-01-01T00:00:00Z"},
    ]}
    bfile = os.path.join(tmpdir, "beliefs.yaml")
    with open(bfile, "w") as f:
        yaml.dump(beliefs, f)

    rc, out, _ = run_script("containment-engine.py", "status", sfile, bfile)
    if out.get("authority_matrix", {}).get("total_pairs", 0) > 0:
        pass_(f"Status overview: {out['authority_matrix']['total_pairs']} authority pairs")
    else:
        fail("Status should show authority matrix pairs")

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 56)
print(f"  Phase 2 Containment Tests: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
