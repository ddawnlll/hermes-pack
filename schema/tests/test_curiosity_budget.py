#!/usr/bin/env python3
"""
Issue #30 — Curiosity Budget Tests
Verifies protected discovery budget: min 20%, adaptive growth, ROI isolation.
"""
import json, os, sys, tempfile, shutil

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
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

# Import
sys.path.insert(0, os.path.join(REPO_ROOT, "templates"))
from importlib.machinery import SourceFileLoader
mod = SourceFileLoader("curiosity_budget", os.path.join(REPO_ROOT, "templates", "curiosity-budget.py")).load_module()
compute_curiosity_budget = mod.compute_curiosity_budget
update_state_curiosity_budget = mod.update_state_curiosity_budget
validate_curiosity_budget_in_schema = mod.validate_curiosity_budget_in_schema

# ── Test 1: curiosity-budget.py exists
print("[TEST] Test 1: curiosity-budget.py exists")
if os.path.exists(os.path.join(REPO_ROOT, "templates", "curiosity-budget.py")):
    pass_("curiosity-budget.py exists")
else:
    fail("curiosity-budget.py NOT found")

# ── Test 2: state.schema.json has curiosity_budget_usd
print("[TEST] Test 2: state.schema.json has curiosity_budget_usd")
ok, msg = validate_curiosity_budget_in_schema(os.path.join(REPO_ROOT, "schema", "state.schema.json"))
if ok:
    pass_(msg)
else:
    fail(msg)

# ── Test 3: Base 20% minimum with $25 budget
print("[TEST] Test 3: Base 20% = $5.00 on $25 budget")
result = compute_curiosity_budget(25.0, 0.0)
expected = round(25.0 * 0.20, 4)
if abs(result["curiosity_usd"] - expected) < 0.001:
    pass_(f"curiosity_usd={result['curiosity_usd']} (expected {expected})")
else:
    fail(f"curiosity_usd={result['curiosity_usd']}, expected {expected}")
if abs(result["ratio"] - 0.20) < 0.001:
    pass_("ratio=0.20 (base minimum)")
else:
    fail(f"ratio={result['ratio']}, expected 0.20")

# ── Test 4: Never below 20% even with zero hit rate
print("[TEST] Test 4: Never below 20%")
for rate in [0.0, -0.5, -1.0]:
    result = compute_curiosity_budget(100.0, rate)
    if result["ratio"] >= 0.20:
        pass_(f"hit_rate={rate}: ratio={result['ratio']} >= 0.20")
    else:
        fail(f"hit_rate={rate}: ratio={result['ratio']} < 0.20!")

# ── Test 5: Adaptive growth with high hit rate
print("[TEST] Test 5: Adaptive growth with high hit rate")
result = compute_curiosity_budget(25.0, 1.0)  # 100% hit rate
if result["ratio"] > 0.20:
    pass_(f"hit_rate=1.0: ratio={result['ratio']} > 0.20 (adaptive growth)")
else:
    fail(f"hit_rate=1.0: ratio={result['ratio']}, should be > 0.20")

# ── Test 6: Never above 50% ceiling
print("[TEST] Test 6: Never above 50% ceiling")
result = compute_curiosity_budget(25.0, 1.0)
if result["ratio"] <= 0.50:
    pass_(f"ratio={result['ratio']} <= 0.50 (ceiling respected)")
else:
    fail(f"ratio={result['ratio']} > 0.50, exceeds ceiling!")

# ── Test 7: $0 budget → $0 curiosity
print("[TEST] Test 7: Zero budget")
result = compute_curiosity_budget(0.0, 0.5)
if result["curiosity_usd"] == 0.0:
    pass_("Zero budget → zero curiosity")
else:
    fail(f"Zero budget gave curiosity_usd={result['curiosity_usd']}")

# ── Test 8: ROI gate isolation — curiosity is separate slice
print("[TEST] Test 8: ROI gate isolation")
result = compute_curiosity_budget(25.0, 0.0)
roi_budget = 25.0 - result["curiosity_usd"]
if roi_budget > 0 and result["curiosity_usd"] > 0:
    pass_(f"ROI budget={roi_budget:.2f}, Curiosity={result['curiosity_usd']:.2f} (separate slices)")
else:
    fail(f"Budget partitioning failed: ROI={roi_budget}, Curiosity={result['curiosity_usd']}")

# ── Test 9: Update state.json
print("[TEST] Test 9: Update state.json with curiosity budget")
tmpdir = tempfile.mkdtemp()
try:
    state_path = os.path.join(tmpdir, "state.json")
    with open(state_path, "w") as f:
        json.dump({"schema_version": 1, "tick": 5, "budget_usd": 25.0, "explorer_hit_rate": 0.5}, f)
    result = update_state_curiosity_budget(state_path)
    with open(state_path) as f:
        state = json.load(f)
    if "curiosity_budget_usd" in state and state["curiosity_budget_usd"] > 0:
        pass_(f"state.json updated: curiosity_budget_usd={state['curiosity_budget_usd']}")
    else:
        fail(f"state.json not properly updated: {state.get('curiosity_budget_usd')}")
    if "curiosity_ratio" in state:
        pass_(f"curiosity_ratio={state['curiosity_ratio']}")
    else:
        fail("curiosity_ratio missing from state")
finally:
    shutil.rmtree(tmpdir)

# ── Test 10: Negative budget handled
print("[TEST] Test 10: Negative budget handled gracefully")
result = compute_curiosity_budget(-10.0, 0.0)
if result["curiosity_usd"] == 0.0:
    pass_("Negative budget → zero curiosity")
else:
    fail(f"Negative budget gave curiosity_usd={result['curiosity_usd']}")

# ── Summary
print()
print("=" * 60)
print(f"  Curiosity Budget Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 60)
sys.exit(1 if FAIL_COUNT > 0 else 0)
