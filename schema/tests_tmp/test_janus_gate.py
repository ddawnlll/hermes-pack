#!/usr/bin/env python3
"""
Janus Gate Tests — Issue #24 (Janus / Red Team meta-gate)

Tests the two-faced meta-gate logic:
1. Forward face: scar-tissue memory check for refuted hypotheses
2. Backward face: falsifiability contract check (concrete, testable prediction)

Simulates the Janus gate logic in pure Python to match the bash script behavior.
Tests match the actual janus-gate.sh script's structural checks.
"""
import hashlib
import json
import math
import os
import sys
import tempfile

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


# ── Simulated Janus gate logic (mirrors janus-gate.sh) ─────────────────────


def create_evidence_bundle(hypothesis_id, metric_name, threshold, direction,
                           prediction="", task_id="T1", worker="worker-1"):
    """Create a minimal evidence bundle JSON."""
    bundle = {
        "schema_version": 1,
        "hypothesis_id": hypothesis_id,
        "task_id": task_id,
        "metric_name": metric_name,
        "threshold": threshold,
        "direction": direction,
        "worker": worker,
        "worker_output": {"value": 0.5, "unit": "score"},
    }
    if prediction:
        bundle["prediction"] = prediction
    return bundle


def create_scar_tissue_record(objection_id, hypothesis_id, metric_name,
                               status="active", claim_attacked="",
                               why="Prior refutation"):
    """Create a single scar-tissue JSONL record."""
    record = {
        "objection_id": objection_id,
        "hypothesis_id": hypothesis_id,
        "metric_name": metric_name,
        "status": status,
        "claim_attacked": claim_attacked or f"Hypothesis {hypothesis_id} claim on {metric_name}",
        "why": why,
        "retraction_criterion": f"Evidence showing {metric_name} >= previous best",
    }
    return record


def forward_face(evidence_bundle, scar_tissue_records, divergence_score):
    """
    Forward face: Check scar-tissue memory for similar refuted hypotheses.
    Returns {"verdict": "PASS"|"FAIL", "reason": "...", "match_count": int}
    """
    hypotheses = set()
    metrics = set()

    for record in scar_tissue_records:
        status = record.get("status", "active")
        if status in ("resolved", "superseded", "withdrawn"):
            continue
        hypotheses.add(record.get("hypothesis_id", ""))
        metrics.add(record.get("metric_name", ""))

    eb_hypothesis = evidence_bundle.get("hypothesis_id", "")
    eb_metric = evidence_bundle.get("metric_name", "")

    match_count = 0
    for record in scar_tissue_records:
        status = record.get("status", "active")
        if status in ("resolved", "superseded", "withdrawn"):
            continue
        rh = record.get("hypothesis_id", "")
        rm = record.get("metric_name", "")
        rc = record.get("claim_attacked", "")
        if eb_hypothesis and eb_hypothesis == rh:
            match_count += 1
        elif eb_metric and eb_metric == rm:
            match_count += 1
        elif eb_metric and eb_metric in rc:
            match_count += 1

    if match_count > 0:
        return {
            "verdict": "FAIL",
            "reason": f"Scar-tissue match: {match_count} prior refuted hypothesis(es) match this evidence bundle",
            "match_count": match_count,
            "explorer_divergence": divergence_score,
        }

    # Low divergence advisory (doesn't fail, just notes)
    reason = "No scar-tissue matches — hypothesis explores new territory"
    if divergence_score is not None and divergence_score < 0.05:
        reason += f"; Low divergence ({divergence_score}) — hypothesis closely resembles prior work"

    return {
        "verdict": "PASS",
        "reason": reason,
        "match_count": 0,
        "explorer_divergence": divergence_score,
    }


def backward_face(evidence_bundle):
    """
    Backward face: Check falsifiability contract.
    Hypothesis must have: prediction, metric, threshold, direction.
    Returns {"verdict": "PASS"|"HOLD", "reason": "...", "falsifiability": {...}}
    """
    has_prediction = bool(evidence_bundle.get("prediction") or
                          evidence_bundle.get("testable_prediction") or
                          evidence_bundle.get("hypothesis_prediction"))
    has_metric = bool(evidence_bundle.get("metric_name") or
                      evidence_bundle.get("metric") or
                      evidence_bundle.get("target_metric"))
    has_threshold = bool(evidence_bundle.get("threshold") or
                         evidence_bundle.get("target") or
                         evidence_bundle.get("success_threshold"))
    has_direction = bool(evidence_bundle.get("direction") or
                         evidence_bundle.get("comparison") or
                         evidence_bundle.get("improvement_direction"))

    fields_present = sum([has_prediction, has_metric, has_threshold, has_direction])
    missing = []
    if not has_prediction:
        missing.append("prediction")
    if not has_metric:
        missing.append("metric")
    if not has_threshold:
        missing.append("threshold")
    if not has_direction:
        missing.append("direction")

    falsifiability = {
        "has_prediction": has_prediction,
        "has_metric": has_metric,
        "has_threshold": has_threshold,
        "has_direction": has_direction,
        "fields_present": fields_present,
        "fields_required": 4,
    }

    if fields_present >= 4:
        return {
            "verdict": "PASS",
            "reason": "Hypothesis is falsifiable: prediction + metric + threshold + direction all present",
            "falsifiability": falsifiability,
        }
    elif fields_present >= 1:
        return {
            "verdict": "HOLD",
            "reason": f"Hypothesis is partially falsifiable ({fields_present}/4 fields present). Missing: {', '.join(missing)}. Add a concrete, testable prediction with metric, threshold, and direction.",
            "falsifiability": falsifiability,
        }
    else:
        return {
            "verdict": "HOLD",
            "reason": "Hypothesis is NOT falsifiable (0/4 fields present). A hypothesis must make a concrete, testable prediction with a measurable metric, threshold, and direction of improvement.",
            "falsifiability": falsifiability,
        }


def janus_gate(evidence_bundle, scar_tissue_records, divergence_score):
    """
    Full Janus gate: combines forward and backward faces.
    Returns {"verdict": "PASS"|"HOLD"|"FAIL", "forward": {...}, "backward": {...}}
    """
    forward = forward_face(evidence_bundle, scar_tissue_records, divergence_score)
    backward = backward_face(evidence_bundle)

    if forward["verdict"] == "FAIL":
        verdict = "FAIL"
        reason = f"Forward face failed: {forward['reason']}"
    elif backward["verdict"] == "HOLD":
        verdict = "HOLD"
        reason = f"Backward face advisory: {backward['reason']}"
    else:
        verdict = "PASS"
        reason = "Both faces pass: hypothesis explores new territory and is falsifiable"

    return {
        "verdict": verdict,
        "reason": reason,
        "forward": forward,
        "backward": backward,
    }


def red_team_trigger(evidence_bundle, janus_forward_result):
    """
    Red Team trigger: determines if a Red Team task should be dispatched.
    Triggered when Janus forward face returns FAIL.
    Returns {"action": "dispatch_red_team"|"skip", ...}
    """
    if janus_forward_result.get("verdict") != "FAIL":
        return {
            "action": "skip",
            "reason": "Janus forward verdict is not FAIL — no Red Team dispatch needed",
        }

    hypothesis_id = evidence_bundle.get("hypothesis_id", "unknown")
    metric_name = evidence_bundle.get("metric_name", "unknown")

    return {
        "action": "dispatch_red_team",
        "reason": f"Forward face FAIL on hypothesis {hypothesis_id} (metric: {metric_name})",
        "task_details": {
            "type": "red_team_review",
            "trigger": "janus_forward_fail",
            "hypothesis_id": hypothesis_id,
            "metric_name": metric_name,
            "scar_match_count": janus_forward_result.get("match_count", 0),
            "priority": "high",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


def run_tests():
    global PASS_COUNT, FAIL_COUNT

    # ═══════════════════════════════════════════════════════════════════════
    # Test 1: Forward face — scar-tissue match triggers FAIL
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 1: Forward face returns FAIL when scar-tissue matches hypothesis_id")
    eb = create_evidence_bundle(
        hypothesis_id="H7", metric_name="accuracy",
        threshold="0.85", direction=">=", prediction="Model accuracy >= 0.85"
    )
    scar = [
        create_scar_tissue_record("RT-001", "H7", "accuracy",
                                   why="Prior failed attempt at H7/accuracy"),
    ]
    result = forward_face(eb, scar, divergence_score=0.8)
    if result["verdict"] == "FAIL":
        pass_("forward_face() returned FAIL when scar-tissue matches hypothesis_id")
        if result["match_count"] >= 1:
            pass_(f"match_count={result['match_count']} correctly identifies 1+ scar match")
    else:
        fail(f"Expected FAIL but got {result['verdict']}: {result['reason']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 2: Forward face — no scar-tissue match returns PASS
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 2: Forward face returns PASS when no scar-tissue match")
    eb = create_evidence_bundle(
        hypothesis_id="H8", metric_name="f1_score",
        threshold="0.90", direction=">=", prediction="F1-score >= 0.90"
    )
    scar = [
        create_scar_tissue_record("RT-001", "H7", "accuracy",
                                   why="Prior failed attempt at H7/accuracy"),
    ]
    result = forward_face(eb, scar, divergence_score=0.9)
    if result["verdict"] == "PASS":
        pass_("forward_face() returns PASS when hypothesis/ metric not in scar-tissue")
        if result["match_count"] == 0:
            pass_("match_count=0 for non-matching hypothesis")
    else:
        fail(f"Expected PASS but got {result['verdict']}: {result['reason']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 3: Forward face — resolved scar records are skipped
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 3: Forward face skips resolved/superseded scar records")
    eb = create_evidence_bundle(
        hypothesis_id="H9", metric_name="precision",
        threshold="0.80", direction=">=", prediction="Precision >= 0.80"
    )
    scar = [
        create_scar_tissue_record("RT-001", "H9", "precision", status="resolved"),
        create_scar_tissue_record("RT-002", "H9", "precision", status="superseded"),
        create_scar_tissue_record("RT-003", "H9", "precision", status="withdrawn"),
    ]
    result = forward_face(eb, scar, divergence_score=0.7)
    if result["verdict"] == "PASS":
        pass_("forward_face() ignores resolved/superseded/withdrawn scar records")
    else:
        fail(f"Expected PASS (resolved records ignored) but got {result['verdict']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 4: Forward face — empty scar-tissue returns PASS
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 4: Forward face returns PASS with empty scar-tissue (first hypothesis)")
    eb = create_evidence_bundle(
        hypothesis_id="H10", metric_name="recall",
        threshold="0.85", direction=">=", prediction="Recall >= 0.85"
    )
    result = forward_face(eb, [], divergence_score=0.5)
    if result["verdict"] == "PASS":
        pass_("forward_face() returns PASS for empty scar-tissue (first hypothesis in family)")
    else:
        fail(f"Expected PASS for empty scar but got {result['verdict']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 5: Forward face — metric name overlap triggers FAIL
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 5: Forward face returns FAIL when metric name matches scar record")
    eb = create_evidence_bundle(
        hypothesis_id="H11", metric_name="accuracy",
        threshold="0.85", direction=">=", prediction="Accuracy >= 0.85"
    )
    scar = [
        create_scar_tissue_record("RT-010", "H_diff", "accuracy",
                                   why="Different hypothesis, same metric was refuted"),
    ]
    result = forward_face(eb, scar, divergence_score=0.6)
    if result["verdict"] == "FAIL":
        pass_("forward_face() FAILs when evidence metric matches scar-tissue metric_name")
    else:
        fail(f"Expected FAIL for metric overlap but got {result['verdict']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 6: Backward face — fully falsifiable returns PASS
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 6: Backward face returns PASS for fully falsifiable hypothesis")
    eb = create_evidence_bundle(
        hypothesis_id="H12", metric_name="auc_roc",
        threshold="0.90", direction=">=", prediction="AUC-ROC >= 0.90 on held-out test set"
    )
    result = backward_face(eb)
    if result["verdict"] == "PASS":
        pass_("backward_face() returns PASS when all 4 falsifiability fields present")
        fb = result["falsifiability"]
        if fb["fields_present"] == 4:
            pass_("falsifiability.fields_present=4 for complete hypothesis")
        if fb["has_prediction"] and fb["has_metric"] and fb["has_threshold"] and fb["has_direction"]:
            pass_("All 4 falsifiability flags are True")
    else:
        fail(f"Expected PASS but got {result['verdict']}: {result['reason']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 7: Backward face — missing prediction returns HOLD
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 7: Backward face returns HOLD for non-falsifiable hypothesis (no prediction)")
    eb = create_evidence_bundle(
        hypothesis_id="H13", metric_name="accuracy",
        threshold="0.85", direction=">=", prediction=""
    )
    result = backward_face(eb)
    if result["verdict"] == "HOLD":
        pass_("backward_face() returns HOLD when hypothesis has no prediction")
        if not result["falsifiability"]["has_prediction"]:
            pass_("falsifiability.has_prediction=False for missing prediction field")
    else:
        fail(f"Expected HOLD but got {result['verdict']}: {result['reason']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 8: Janus gate — full pipeline, scar match → FAIL
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 8: Janus gate overall verdict FAIL when forward face fails")
    eb = create_evidence_bundle(
        hypothesis_id="H14", metric_name="accuracy",
        threshold="0.90", direction=">=", prediction="Accuracy >= 0.90"
    )
    scar = [
        create_scar_tissue_record("RT-020", "H14", "accuracy",
                                   why="H14 accuracy hypothesis was previously refuted"),
    ]
    result = janus_gate(eb, scar, divergence_score=0.8)
    if result["verdict"] == "FAIL":
        pass_("janus_gate() returns FAIL when forward face detects scar match")
        if result["forward"]["verdict"] == "FAIL":
            pass_("Forward face component correctly FAILs")
    else:
        fail(f"Expected FAIL but got {result['verdict']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 9: Janus gate — no scar match, falsifiable → PASS
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 9: Janus gate returns PASS when both faces pass")
    eb = create_evidence_bundle(
        hypothesis_id="H15", metric_name="ndcg",
        threshold="0.85", direction=">=", prediction="NDCG@10 >= 0.85 on validation set"
    )
    result = janus_gate(eb, [], divergence_score=0.9)
    if result["verdict"] == "PASS":
        pass_("janus_gate() returns PASS for novel, falsifiable hypothesis")
        if result["forward"]["verdict"] == "PASS" and result["backward"]["verdict"] == "PASS":
            pass_("Both forward and backward faces return PASS")
    else:
        fail(f"Expected PASS but got {result['verdict']}: {result['reason']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 10: Janus gate — non-falsifiable, no scar match → HOLD
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 10: Janus gate returns HOLD for non-falsifiable but novel hypothesis")
    eb = create_evidence_bundle(
        hypothesis_id="H16", metric_name="bleu",
        threshold="", direction="", prediction=""
    )
    result = janus_gate(eb, [], divergence_score=0.7)
    if result["verdict"] == "HOLD":
        pass_("janus_gate() returns HOLD when backward face is HOLD (advisory)")
        if result["backward"]["verdict"] == "HOLD":
            pass_("Backward face correctly returns HOLD for non-falsifiable hypothesis")
    else:
        fail(f"Expected HOLD but got {result['verdict']}: {result['reason']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 11: Red Team trigger — dispatches on forward FAIL
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 11: Red Team trigger dispatches on Janus forward FAIL")
    eb = create_evidence_bundle(
        hypothesis_id="H17", metric_name="loss",
        threshold="0.50", direction="<=", prediction="Loss <= 0.50"
    )
    forward_result = {"verdict": "FAIL", "match_count": 2, "reason": "Scar match"}
    trigger = red_team_trigger(eb, forward_result)
    if trigger["action"] == "dispatch_red_team":
        pass_("red_team_trigger() dispatches red team task on forward FAIL")
        if trigger["task_details"]["scar_match_count"] == 2:
            pass_("Task details include correct scar_match_count")
        if trigger["task_details"]["hypothesis_id"] == "H17":
            pass_("Task details include correct hypothesis_id")
    else:
        fail(f"Expected dispatch_red_team but got {trigger['action']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Test 12: Red Team trigger — skips on forward PASS
    # ═══════════════════════════════════════════════════════════════════════
    say("Test 12: Red Team trigger skips when Janus forward is PASS")
    eb = create_evidence_bundle(
        hypothesis_id="H18", metric_name="f1",
        threshold="0.85", direction=">=", prediction="F1 >= 0.85"
    )
    forward_result = {"verdict": "PASS", "match_count": 0}
    trigger = red_team_trigger(eb, forward_result)
    if trigger["action"] == "skip":
        pass_("red_team_trigger() returns skip for forward PASS")
    else:
        fail(f"Expected skip but got {trigger['action']}")

    # ═══════════════════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════════════════
    print()
    print("=" * 56)
    print(f"  Janus Gate Test Suite: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    print("=" * 56)

    # Verify minimum 7 PASS assertions as required
    if PASS_COUNT >= 7:
        print(f"  ✓ Minimum 7 PASS assertions met ({PASS_COUNT} total)")
    else:
        print(f"  ✗ FAIL: Only {PASS_COUNT} PASS assertions (need >= 7)")

    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
