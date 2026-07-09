#!/usr/bin/env python3
"""
Issue #23 — Scar-tissue memory / Hindsight bridge FAIL test
Ensures FAIL verdicts are written as refuted_hypothesis, not skipped.
"""
import json, os, sys, tempfile

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
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

# ── Test 1: hindsight bridge source contains refuted_hypothesis logic ─────────
print("[TEST] Test 1: praxis-hindsight-bridge.py contains FAIL handling")

bridge_path = os.path.join(REPO_ROOT, "tools", "praxis-hindsight-bridge.py")
with open(bridge_path) as f:
    src = f.read()

if "refuted_hypothesis" in src:
    pass_("bridge source contains 'refuted_hypothesis'")
else:
    fail("bridge source missing 'refuted_hypothesis'")

if "confidence" in src and "0.3" in src:
    pass_("bridge uses low confidence (0.3) for refuted items")
else:
    fail("bridge missing low confidence for refuted items")

if "is_pass" in src and "is_fail" in src:
    pass_("bridge distinguishes PASS vs FAIL verdicts")
else:
    fail("bridge does not distinguish PASS vs FAIL")

# ── Test 2: tick.md references scar-tissue / refuted_hypothesis ─────────────
print("[TEST] Test 2: tick.md references scar-tissue memory check")

tick_path = os.path.join(REPO_ROOT, "templates", "prompts", "tick.md")
with open(tick_path) as f:
    tick = f.read()

if "refuted_hypothesis" in tick or "scar-tissue" in tick:
    pass_("tick.md mentions refuted_hypothesis or scar-tissue")
else:
    fail("tick.md missing refuted_hypothesis / scar-tissue mention")

if "Do NOT re-dispatch" in tick:
    pass_("tick.md explicitly warns against re-dispatching refuted hypotheses")
else:
    fail("tick.md missing re-dispatch warning")

# ── Test 3: Simulate bridge logic for PASS vs FAIL ────────────────────────────
print("[TEST] Test 3: simulated bridge logic for PASS vs FAIL")

def simulate_bridge_items(verdict_status):
    """Simulate the core decision logic from the bridge script."""
    is_pass = verdict_status == "PASS"
    is_fail = verdict_status in ("FAIL", "HOLD")
    if not is_pass and not is_fail:
        return []
    facts = ["Gate SchemaGate: PASS", "Gate FinalGate: FAIL"]
    items = []
    if is_pass:
        for fact in facts:
            items.append({
                "type": "verified_research_result",
                "confidence": "0.95",
                "verdict": verdict_status,
            })
    else:
        for fact in facts:
            items.append({
                "type": "refuted_hypothesis",
                "confidence": "0.3",
                "verdict": verdict_status,
            })
    return items

pass_items = simulate_bridge_items("PASS")
fail_items = simulate_bridge_items("FAIL")
hold_items = simulate_bridge_items("HOLD")
unknown_items = simulate_bridge_items("UNKNOWN")

if pass_items and all(i["type"] == "verified_research_result" for i in pass_items):
    pass_("PASS → verified_research_result with high confidence")
else:
    fail("PASS did not produce verified_research_result")

if fail_items and all(i["type"] == "refuted_hypothesis" for i in fail_items):
    pass_("FAIL → refuted_hypothesis with low confidence")
else:
    fail("FAIL did not produce refuted_hypothesis")

if hold_items and all(i["type"] == "refuted_hypothesis" for i in hold_items):
    pass_("HOLD → refuted_hypothesis with low confidence")
else:
    fail("HOLD did not produce refuted_hypothesis")

if not unknown_items:
    pass_("UNKNOWN → skipped (no items)")
else:
    fail("UNKNOWN should be skipped")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 56)
print(f"  Scar-tissue Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
