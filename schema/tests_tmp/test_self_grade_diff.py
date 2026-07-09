#!/usr/bin/env python3
"""
Self-grade Diff Tests — Issue #28 ($0 Gate / Self-grade diff)
Tests that:
1. mechanical_verdict = FAIL when evidence_bundle_status is FAIL
2. mechanical_verdict = FAIL when praxis_exit_code is 2
3. mechanical_verdict = FAIL when both conditions trigger
4. mechanical_verdict = HOLD when acceptance criteria not fully met
5. mechanical_verdict = PASS when all checks pass
6. self-grade-check PASSes when orchestrator_verdict <= mechanical_verdict
7. self-grade-check FAILs when orchestrator_verdict > mechanical_verdict
8. Optimism ordering: FAIL < HOLD < PASS is strictly enforced
9. Edge case: empty praxis_exit_code → FAIL
10. Edge case: total_criteria=0, all met → PASS

Simulates the diff/check logic in pure Python to avoid shell dependency
in the test suite. Tests match the actual bash scripts' behavior.
"""
import json
import sys

PASS_COUNT = 0
FAIL_COUNT = 0

# Optimism ranks: FAIL=0, HOLD=1, PASS=2
OPTIMISM_RANK = {"FAIL": 0, "HOLD": 1, "PASS": 2}


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


# ── Simulated self-grade-diff logic (mirrors self-grade-diff.sh) ──────────────


def compute_mechanical_verdict(praxis_exit_code, evidence_bundle_status,
                               acceptance_met, total_criteria):
    """Simulate self-grade-diff.sh: deterministic mechanical verdict."""
    mechanical = "PASS"
    reasons = []

    # Rule 1: praxis_exit_code == 2 → FAIL
    if praxis_exit_code == 2:
        mechanical = "FAIL"
        reasons.append("praxis_exit_code=2 (Praxis FAIL)")

    # Rule 1b: empty/null exit code → FAIL
    if praxis_exit_code is None or praxis_exit_code == "":
        mechanical = "FAIL"
        reasons.append("praxis_exit_code is empty (missing Praxis result)")

    # Rule 2: evidence_bundle_status == FAIL → FAIL
    if evidence_bundle_status == "FAIL":
        mechanical = "FAIL"
        reasons.append("evidence_bundle_status=FAIL")

    # Rule 3: acceptance not fully met → HOLD (only if not already FAIL)
    if mechanical != "FAIL":
        try:
            if int(acceptance_met) < int(total_criteria):
                mechanical = "HOLD"
                reasons.append(
                    f"acceptance_criteria_met ({acceptance_met}/{total_criteria}) < total_criteria ({total_criteria})"
                )
        except (ValueError, TypeError):
            # Non-numeric → treat as not-less-than (falls through to PASS)
            pass

    # No reason set → everything passed
    if not reasons:
        reasons.append(
            f"all checks passed (praxis_exit_code={praxis_exit_code}, "
            f"evidence_bundle_status={evidence_bundle_status}, "
            f"acceptance_criteria_met={acceptance_met}/{total_criteria})"
        )

    return {
        "mechanical_verdict": mechanical,
        "components": {
            "praxis_exit_code": praxis_exit_code,
            "evidence_bundle_status": evidence_bundle_status,
            "acceptance_criteria_met": acceptance_met,
            "total_criteria": total_criteria,
            "reason": "; ".join(reasons),
        },
    }


# ── Simulated self-grade-check logic (mirrors self-grade-check.sh) ────────────


def check_orchestrator_optimism(mechanical_verdict, orchestrator_verdict):
    """Simulate self-grade-check.sh: orchestrator optimism check."""
    # Validate inputs
    for name, val in [("mechanical", mechanical_verdict),
                      ("orchestrator", orchestrator_verdict)]:
        if val not in OPTIMISM_RANK:
            return {
                "verdict": "FAIL",
                "orchestrator": orchestrator_verdict,
                "mechanical": mechanical_verdict,
                "error": f"Invalid {name}_verdict '{val}'. Must be FAIL, HOLD, or PASS.",
            }

    mechanical_rank = OPTIMISM_RANK[mechanical_verdict]
    orchestrator_rank = OPTIMISM_RANK[orchestrator_verdict]

    # Invariant: orchestrator_verdict <= mechanical_verdict
    if orchestrator_rank > mechanical_rank:
        return {
            "verdict": "FAIL",
            "orchestrator": orchestrator_verdict,
            "mechanical": mechanical_verdict,
            "optimism_rank": {
                "orchestrator": orchestrator_rank,
                "mechanical": mechanical_rank,
            },
            "error": (
                f"Orchestrator verdict '{orchestrator_verdict}' (rank {orchestrator_rank}) "
                f"is more optimistic than mechanical verdict '{mechanical_verdict}' "
                f"(rank {mechanical_rank}). "
                f"Orchestrator cannot be more optimistic than evidence."
            ),
        }

    return {
        "verdict": "PASS",
        "orchestrator": orchestrator_verdict,
        "mechanical": mechanical_verdict,
        "optimism_rank": {
            "orchestrator": orchestrator_rank,
            "mechanical": mechanical_rank,
        },
        "error": "",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Tests — self-grade-diff (mechanical verdict computation)
# ═══════════════════════════════════════════════════════════════════════════

def test_mechanical_verdict_fail_on_praxis_fail():
    """Rule 1: praxis_exit_code == 2 → mechanical = FAIL"""
    say("Test 1: mechanical_verdict FAIL when praxis_exit_code=2")
    result = compute_mechanical_verdict(2, "PASS", 5, 5)
    if result["mechanical_verdict"] == "FAIL":
        pass_("praxis_exit_code=2 produces mechanical_verdict=FAIL")
        if "praxis_exit_code=2" in result["components"]["reason"]:
            pass_("Reason includes praxis_exit_code=2 reference")
        else:
            fail("Reason missing praxis_exit_code=2 reference")
    else:
        fail(
            f"Expected mechanical_verdict=FAIL, got {result['mechanical_verdict']}"
        )


def test_mechanical_verdict_fail_on_evidence_fail():
    """Rule 2: evidence_bundle_status == FAIL → mechanical = FAIL"""
    say("Test 2: mechanical_verdict FAIL when evidence_bundle_status=FAIL")
    result = compute_mechanical_verdict(0, "FAIL", 5, 5)
    if result["mechanical_verdict"] == "FAIL":
        pass_("evidence_bundle_status=FAIL produces mechanical_verdict=FAIL")
        if "evidence_bundle_status=FAIL" in result["components"]["reason"]:
            pass_("Reason includes evidence_bundle_status=FAIL reference")
        else:
            fail("Reason missing evidence_bundle_status=FAIL reference")
    else:
        fail(
            f"Expected mechanical_verdict=FAIL, got {result['mechanical_verdict']}"
        )


def test_mechanical_verdict_fail_on_both():
    """Both praxis FAIL and evidence FAIL → FAIL (with combined reasons)"""
    say("Test 3: mechanical_verdict FAIL when both conditions trigger")
    result = compute_mechanical_verdict(2, "FAIL", 5, 5)
    if result["mechanical_verdict"] == "FAIL":
        pass_("Both conditions produce mechanical_verdict=FAIL")
        reason = result["components"]["reason"]
        if "praxis_exit_code=2" in reason and "evidence_bundle_status=FAIL" in reason:
            pass_("Reason includes both triggering conditions")
        else:
            fail("Reason should reference both conditions")
    else:
        fail(
            f"Expected mechanical_verdict=FAIL, got {result['mechanical_verdict']}"
        )


def test_mechanical_verdict_hold_on_insufficient_criteria():
    """Rule 3: acceptance_met < total → mechanical = HOLD"""
    say("Test 4: mechanical_verdict HOLD when acceptance criteria not fully met")
    result = compute_mechanical_verdict(0, "PASS", 3, 5)
    if result["mechanical_verdict"] == "HOLD":
        pass_("3/5 acceptance criteria produces mechanical_verdict=HOLD")
        if "acceptance_criteria_met" in result["components"]["reason"]:
            pass_("Reason includes acceptance criteria ratio")
        else:
            fail("Reason missing acceptance criteria ratio")
    else:
        fail(
            f"Expected mechanical_verdict=HOLD, got {result['mechanical_verdict']}"
        )


def test_mechanical_verdict_pass_on_all_ok():
    """Rule 4: all checks pass → mechanical = PASS"""
    say("Test 5: mechanical_verdict PASS when all checks pass")
    result = compute_mechanical_verdict(0, "PASS", 5, 5)
    if result["mechanical_verdict"] == "PASS":
        pass_("All checks pass produces mechanical_verdict=PASS")
        if "all checks passed" in result["components"]["reason"]:
            pass_("Reason confirms all checks passed")
        else:
            fail("Reason should confirm all checks passed")
    else:
        fail(
            f"Expected mechanical_verdict=PASS, got {result['mechanical_verdict']}"
        )


def test_mechanical_verdict_pass_on_zero_criteria():
    """Edge case: total_criteria=0, all met → PASS"""
    say("Test 6: mechanical_verdict PASS when total_criteria=0")
    result = compute_mechanical_verdict(0, "PASS", 0, 0)
    if result["mechanical_verdict"] == "PASS":
        pass_("0/0 acceptance criteria produces mechanical_verdict=PASS")
    else:
        fail(
            f"Expected mechanical_verdict=PASS, got {result['mechanical_verdict']}"
        )


def test_mechanical_verdict_fail_on_empty_praxis():
    """Edge case: empty praxis_exit_code → FAIL"""
    say("Test 7: mechanical_verdict FAIL when praxis_exit_code is empty")
    result = compute_mechanical_verdict("", "PASS", 5, 5)
    if result["mechanical_verdict"] == "FAIL":
        pass_("Empty praxis_exit_code produces mechanical_verdict=FAIL")
        if "empty" in result["components"]["reason"]:
            pass_("Reason indicates missing Praxis result")
        else:
            fail("Reason should mention missing Praxis result")
    else:
        fail(
            f"Expected mechanical_verdict=FAIL, got {result['mechanical_verdict']}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tests — self-grade-check (orchestrator optimism check)
# ═══════════════════════════════════════════════════════════════════════════

def test_check_pass_when_orchestrator_equals_mechanical():
    """Pass when orchestrator == mechanical (same rank)"""
    say("Test 8: self-grade-check PASSes when orchestrator == mechanical")
    result = check_orchestrator_optimism("HOLD", "HOLD")
    if result["verdict"] == "PASS":
        pass_("HOLD == HOLD → PASS")
    else:
        fail(f"Expected PASS, got {result['verdict']}: {result.get('error', '')}")

    result2 = check_orchestrator_optimism("PASS", "PASS")
    if result2["verdict"] == "PASS":
        pass_("PASS == PASS → PASS")
    else:
        fail(f"Expected PASS, got {result2['verdict']}: {result2.get('error', '')}")

    result3 = check_orchestrator_optimism("FAIL", "FAIL")
    if result3["verdict"] == "PASS":
        pass_("FAIL == FAIL → PASS")
    else:
        fail(f"Expected PASS, got {result3['verdict']}: {result3.get('error', '')}")


def test_check_pass_when_orchestrator_less_optimistic():
    """Pass when orchestrator < mechanical (less optimistic is safe)"""
    say("Test 9: self-grade-check PASSes when orchestrator < mechanical")
    result = check_orchestrator_optimism("PASS", "HOLD")
    if result["verdict"] == "PASS":
        pass_("orchestrator=HOLD < mechanical=PASS → PASS")
    else:
        fail(f"Expected PASS, got {result['verdict']}: {result.get('error', '')}")

    result2 = check_orchestrator_optimism("PASS", "FAIL")
    if result2["verdict"] == "PASS":
        pass_("orchestrator=FAIL < mechanical=PASS → PASS")
    else:
        fail(f"Expected PASS, got {result2['verdict']}: {result2.get('error', '')}")

    result3 = check_orchestrator_optimism("HOLD", "FAIL")
    if result3["verdict"] == "PASS":
        pass_("orchestrator=FAIL < mechanical=HOLD → PASS")
    else:
        fail(f"Expected PASS, got {result3['verdict']}: {result3.get('error', '')}")


def test_check_fail_when_orchestrator_more_optimistic():
    """Fail when orchestrator > mechanical (too optimistic) — THE KEY TEST"""
    say("Test 10: self-grade-check FAILs when orchestrator > mechanical")
    # orchestrator=PASS but mechanical=FAIL → caught!
    result = check_orchestrator_optimism("FAIL", "PASS")
    if result["verdict"] == "FAIL":
        pass_(
            "orchestrator=PASS when mechanical=FAIL → FAIL (orchestrator too optimistic)"
        )
        if "more optimistic" in result.get("error", ""):
            pass_("Error message clearly explains optimism violation")
        else:
            fail("Error message should explain optimism violation")
    else:
        fail(
            f"Expected FAIL, got {result['verdict']}: orchestrator too optimistic"
        )

    # orchestrator=PASS but mechanical=HOLD
    result2 = check_orchestrator_optimism("HOLD", "PASS")
    if result2["verdict"] == "FAIL":
        pass_(
            "orchestrator=PASS when mechanical=HOLD → FAIL (orchestrator too optimistic)"
        )
    else:
        fail(
            f"Expected FAIL, got {result2['verdict']}: orcheator too optimistic"
        )

    # orchestrator=HOLD but mechanical=FAIL
    result3 = check_orchestrator_optimism("FAIL", "HOLD")
    if result3["verdict"] == "FAIL":
        pass_(
            "orchestrator=HOLD when mechanical=FAIL → FAIL (orchestrator too optimistic)"
        )
    else:
        fail(
            f"Expected FAIL, got {result3['verdict']}: orchestrator too optimistic"
        )


def test_check_fail_on_invalid_input():
    """Fail when input verdict is not FAIL/HOLD/PASS"""
    say("Test 11: self-grade-check FAILs on invalid input verdicts")
    result = check_orchestrator_optimism("INVALID", "PASS")
    if result["verdict"] == "FAIL":
        pass_("Invalid mechanical_verdict → FAIL")
    else:
        fail(f"Expected FAIL, got {result['verdict']}")

    result2 = check_orchestrator_optimism("PASS", "INVALID")
    if result2["verdict"] == "FAIL":
        pass_("Invalid orchestrator_verdict → FAIL")
    else:
        fail(f"Expected FAIL, got {result2['verdict']}")


# ═══════════════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════════════

def run_tests():
    global PASS_COUNT, FAIL_COUNT

    test_mechanical_verdict_fail_on_praxis_fail()
    test_mechanical_verdict_fail_on_evidence_fail()
    test_mechanical_verdict_fail_on_both()
    test_mechanical_verdict_hold_on_insufficient_criteria()
    test_mechanical_verdict_pass_on_all_ok()
    test_mechanical_verdict_pass_on_zero_criteria()
    test_mechanical_verdict_fail_on_empty_praxis()
    test_check_pass_when_orchestrator_equals_mechanical()
    test_check_pass_when_orchestrator_less_optimistic()
    test_check_fail_when_orchestrator_more_optimistic()
    test_check_fail_on_invalid_input()

    print()
    print("=" * 56)
    print(f"  Self-grade Diff Test Suite: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    print("=" * 56)
    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
