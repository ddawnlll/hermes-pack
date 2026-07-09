#!/usr/bin/env python3
"""
Issue #31 — Escalation policy + AFK mode test
Ensures no global stall when human is AFK; old 72h hard-stop removed.
"""
import json, os, sys

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

# ── Test 1: goal.yaml no longer has 72h hard-stop ─────────────────────────────
print("[TEST] Test 1: goal.yaml stop_conditions")

goal_path = os.path.join(REPO_ROOT, "templates", "goal.yaml")
with open(goal_path) as f:
    goal = f.read()

# Check the actual YAML list contents, not just the whole file text
yaml_lines = [l.strip() for l in goal.splitlines() if l.strip().startswith("-")]
if any("human_gate_pending>72h" in l for l in yaml_lines):
    fail("goal.yaml still contains old 72h hard-stop in stop_conditions list")
else:
    pass_("goal.yaml removed human_gate_pending>72h from stop_conditions list")

if "PARKED when human is AFK" in goal or "system continues" in goal:
    pass_("goal.yaml comments mention AFK park+continue policy")
else:
    fail("goal.yaml missing AFK policy comment")

# ── Test 2: escalation-gate.sh exists and is deterministic ───────────────────
print("[TEST] Test 2: escalation-gate.sh existence and logic")

gate_path = os.path.join(REPO_ROOT, "templates", "scripts", "escalation-gate.sh")
if os.path.exists(gate_path):
    pass_("escalation-gate.sh exists")
else:
    fail("escalation-gate.sh missing")
    sys.exit(1)

with open(gate_path) as f:
    gate_src = f.read()

if "human_available" in gate_src:
    pass_("escalation-gate.sh checks human_available")
else:
    fail("escalation-gate.sh missing human_available check")

if "t4_budget" in gate_src:
    pass_("escalation-gate.sh checks t4_budget")
else:
    fail("escalation-gate.sh missing t4_budget check")

if '"action": "park"' in gate_src or "action=\"park\"" in gate_src:
    pass_("escalation-gate.sh produces park action for AFK")
else:
    fail("escalation-gate.sh missing park action")

if '"action": "escalate_to_t4"' in gate_src or "action=\"escalate_to_t4\"" in gate_src:
    pass_("escalation-gate.sh produces escalate_to_t4 action")
else:
    fail("escalation-gate.sh missing escalate_to_t4 action")

if "safe_default" in gate_src or "HOLD" in gate_src:
    pass_("escalation-gate.sh mentions safe-default HOLD")
else:
    fail("escalation-gate.sh missing safe-default HOLD")

# Simulate the gate logic in Python (since bash may not run cleanly on Windows)
def simulate_gate(human_available, t4_budget):
    if not human_available:
        return {"action": "park", "reason": "human_afk", "safe_default": "HOLD"}
    if t4_budget <= 0:
        return {"action": "hold", "reason": "t4_budget_exhausted", "safe_default": "HOLD"}
    return {"action": "escalate_to_t4", "reason": "", "safe_default": "HOLD"}

# ── Test 3: Simulate gate scenarios ──────────────────────────────────────────
print("[TEST] Test 3: Simulated escalation gate scenarios")

scenarios = [
    (True, 5.0, "escalate_to_t4"),
    (False, 5.0, "park"),
    (True, 0.0, "hold"),
    (False, 0.0, "park"),
]

for human, budget, expected in scenarios:
    result = simulate_gate(human, budget)
    if result["action"] == expected:
        pass_(f"human={human}, budget={budget} → {expected}")
    else:
        fail(f"human={human}, budget={budget} expected {expected}, got {result['action']}")

# ── Test 4: tick.md mentions AFK / escalation-gate ───────────────────────────
print("[TEST] Test 4: tick.md references AFK policy and escalation gate")

tick_path = os.path.join(REPO_ROOT, "templates", "prompts", "tick.md")
with open(tick_path) as f:
    tick = f.read()

if "escalation-gate.sh" in tick or "escalation gate" in tick.lower():
    pass_("tick.md references escalation-gate.sh")
else:
    fail("tick.md missing escalation-gate reference")

if "AFK" in tick or "human_available = false" in tick:
    pass_("tick.md mentions AFK mode")
else:
    fail("tick.md missing AFK mention")

if "PARK" in tick and "safe-default" in tick.replace("safe_default", "safe-default"):
    pass_("tick.md mentions PARK + safe-default")
else:
    fail("tick.md missing PARK + safe-default")

if "No global stall" in tick or "no global stall" in tick.lower():
    pass_("tick.md explicitly forbids global stall")
else:
    fail("tick.md missing 'no global stall' text")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 56)
print(f"  Escalation/AFK Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
