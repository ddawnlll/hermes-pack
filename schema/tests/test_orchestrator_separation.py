#!/usr/bin/env python3
"""
Issue #21 — Orchestrator conflict-of-interest separation test
Ensures orchestrator does NOT act as judge/merger of its own proposals.
"""
import os, sys

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

# ── Test 1: SOUL.orchestrator.md does NOT claim judge role ────────────────────
print("[TEST] Test 1: SOUL.orchestrator.md role separation")

soul_path = os.path.join(REPO_ROOT, "templates", "SOUL.orchestrator.md")
with open(soul_path) as f:
    soul = f.read()

if "strategist, judge, and control plane" in soul:
    fail("SOUL still claims 'strategist, judge, and control plane'")
else:
    pass_("SOUL removed 'judge' from self-description")

if "do NOT judge your own proposals" in soul or "Judgment and merge authority belong to the Arbiter" in soul:
    pass_("SOUL explicitly delegates judgment to Arbiter")
else:
    fail("SOUL missing Arbiter delegation text")

# ── Test 2: tick.md separates T1 recommendation from merge execution ─────────
print("[TEST] Test 2: tick.md T1/Arbiter separation")

tick_path = os.path.join(REPO_ROOT, "templates", "prompts", "tick.md")
with open(tick_path) as f:
    tick = f.read()

if "The orchestrator NEVER merges its own proposal" in tick:
    pass_("tick.md explicitly forbids self-merge")
else:
    fail("tick.md missing 'orchestrator NEVER merges' text")

if "Merge execution requires an Arbiter (T3) binding verdict" in tick:
    pass_("tick.md requires Arbiter binding verdict for merge")
else:
    fail("tick.md missing Arbiter binding requirement")

if "Makes **binding** merge/reject decision" in tick or "binding merge/reject decision" in tick:
    pass_("T3 Arbiter section mentions binding decision")
else:
    fail("T3 Arbiter section missing 'binding'")

if "Orchestrator executes the Arbiter's decision" in tick:
    pass_("tick.md says orchestrator only executes Arbiter decisions")
else:
    fail("tick.md missing execution-only role for orchestrator")

# ── Test 3: No single-actor merge gate in tick.md ──────────────────────────────
print("[TEST] Test 3: No single-actor merge gate")

# Look for old problematic text
problematic = [
    "orchestrator merges",
    "orchestrator-approved",
]
found_any = False
for phrase in problematic:
    if phrase.lower() in tick.lower():
        found_any = True
        fail(f"tick.md still contains problematic phrase: '{phrase}'")

if not found_any:
    pass_("tick.md free of single-actor merge phrases")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 56)
print(f"  Orchestrator Separation Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
