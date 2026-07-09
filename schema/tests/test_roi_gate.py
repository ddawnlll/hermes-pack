#!/usr/bin/env python3
"""
Issue #29 — ROI/Exploitation Throttle Gate Tests
Tests that only refuted families are throttled, novel hypotheses never throttled,
and high-variance discovery is not suppressed.
"""
import json, os, sys, tempfile, shutil

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "templates", "scripts")
PASS_COUNT = 0
FAIL_COUNT = 0

def pass_(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"[TEST] PASS: {msg}")

def fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"[TEST] FAIL: {msg}")

# Import roi-gate
sys.path.insert(0, os.path.join(REPO_ROOT, "templates"))
from importlib.machinery import SourceFileLoader
mod = SourceFileLoader("roi_gate", os.path.join(REPO_ROOT, "templates", "roi-gate.py")).load_module()
check_roi_gate = mod.check_roi_gate
load_objections = mod.load_objections
load_roi_ledger = mod.load_roi_ledger
get_family_streak = mod.get_family_streak
append_to_roi_ledger = mod.append_to_roi_ledger

# ── Test 1: ROI gate script exists
print("[TEST] Test 1: roi-gate.py exists")
if os.path.exists(os.path.join(REPO_ROOT, "templates", "roi-gate.py")):
    pass_("roi-gate.py exists")
else:
    fail("roi-gate.py NOT found")

# ── Test 2: New/novel hypothesis never throttled
print("[TEST] Test 2: New hypothesis never throttled")
result = check_roi_gate("new-family-xyz", set(), [])
if not result["throttled"]:
    pass_("Novel hypothesis not throttled")
else:
    fail(f"Novel hypothesis throttled: {result}")

# ── Test 3: Refuted family with low streak not throttled
print("[TEST] Test 3: Refuted family streak below threshold")
refuted = {"dead-family"}
records = [
    {"family_id": "dead-family", "value": 0, "spend_usd": 1.0},
    {"family_id": "dead-family", "value": 0, "spend_usd": 1.0},
]
result = check_roi_gate("dead-family", refuted, records, streak_threshold=3)
if not result["throttled"]:
    pass_("Refuted family with streak=2 not throttled (below K=3)")
else:
    fail(f"Should not throttle at streak=2, got: {result}")

# ── Test 4: Refuted family with streak >= K IS throttled
print("[TEST] Test 4: Refuted family streak >= K throttled")
records = [
    {"family_id": "dead-family", "value": 0, "spend_usd": 1.0},
    {"family_id": "dead-family", "value": 0, "spend_usd": 1.0},
    {"family_id": "dead-family", "value": 0, "spend_usd": 1.0},
]
result = check_roi_gate("dead-family", refuted, records, streak_threshold=3)
if result["throttled"]:
    pass_(f"Refuted family throttled at streak={result['streak']}")
else:
    fail(f"Should throttle at streak=3, got: {result}")

# ── Test 5: Productive run resets streak
print("[TEST] Test 5: Productive run resets streak")
records = [
    {"family_id": "dead-family", "value": 0, "spend_usd": 1.0},
    {"family_id": "dead-family", "value": 0, "spend_usd": 1.0},
    {"family_id": "dead-family", "value": 5, "spend_usd": 1.0},  # productive!
    {"family_id": "dead-family", "value": 0, "spend_usd": 1.0},
]
result = check_roi_gate("dead-family", refuted, records, streak_threshold=3)
if not result["throttled"]:
    pass_("Streak reset after productive run (streak=1)")
else:
    fail(f"Should not throttle after productive run, got: {result}")

# ── Test 6: High-variance discovery not suppressed
print("[TEST] Test 6: High-variance discovery not suppressed")
# 20 empty ticks + 1 explosion — novel family should NOT be throttled
refuted = {"dead-family"}
records = []
for i in range(20):
    records.append({"family_id": "other-dead", "value": 0, "spend_usd": 0.5})
# New family appears — never seen in refuted
result = check_roi_gate("brand-new-alpha", refuted, records)
if not result["throttled"]:
    pass_("High-variance discovery: novel family not suppressed")
else:
    fail(f"Novel family suppressed in high-variance scenario: {result}")

# ── Test 7: Unknown family not in refuted not throttled
print("[TEST] Test 7: Unknown family not throttled")
result = check_roi_gate("unknown-family", {"only-this"}, [])
if not result["throttled"]:
    pass_("Unknown family not throttled")
else:
    fail(f"Unknown family throttled: {result}")

# ── Test 8: ROI ledger append works
print("[TEST] Test 8: ROI ledger append")
tmpdir = tempfile.mkdtemp()
try:
    ledger_path = os.path.join(tmpdir, "roi", "ledger.jsonl")
    rec = append_to_roi_ledger(ledger_path, "tick-1", "family-a", 2.5, 3)
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            lines = f.readlines()
        if len(lines) == 1:
            parsed = json.loads(lines[0])
            if parsed["family_id"] == "family-a" and parsed["value"] == 3:
                pass_("ROI ledger append works correctly")
            else:
                fail(f"Wrong data in ledger: {parsed}")
        else:
            fail(f"Expected 1 line, got {len(lines)}")
    else:
        fail("Ledger file not created")
finally:
    shutil.rmtree(tmpdir)

# ── Test 9: load_objections works
print("[TEST] Test 9: load_objections")
tmpdir = tempfile.mkdtemp()
try:
    obj_path = os.path.join(tmpdir, "scar-tissue", "objections.jsonl")
    os.makedirs(os.path.dirname(obj_path))
    with open(obj_path, "w") as f:
        f.write(json.dumps({"verdict": "BLOCK", "family_id": "f1"}) + "\n")
        f.write(json.dumps({"verdict": "SUSTAIN", "family_id": "f2"}) + "\n")
        f.write(json.dumps({"verdict": "BLOCK", "family_id": "f3"}) + "\n")
    refuted = load_objections(obj_path)
    if refuted == {"f1", "f3"}:
        pass_("load_objections correctly identifies BLOCKED families")
    else:
        fail(f"Expected {{f1, f3}}, got {refuted}")
finally:
    shutil.rmtree(tmpdir)

# ── Summary
print()
print("=" * 60)
print(f"  ROI Gate Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 60)
sys.exit(1 if FAIL_COUNT > 0 else 0)
