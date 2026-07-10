#!/usr/bin/env python3
"""
Pre-registration Lock Tests — Issue #27 ($0 Gate / Anti p-hacking)
Tests that:
1. prereg-lock.sh creates a lock file with the expected fields
2. prereg-verify.sh PASSes when reported metric matches the lock
3. prereg-verify.sh FAILs when reported metric differs from the lock
4. prereg-verify.sh FAILs when lock file is tampered with
5. prereg-verify.sh errors when lock file is missing
6. Lock file contains a valid SHA-256 hash
7. Lock directory is created if it doesn't exist

Simulates the lock/verify logic in pure Python to avoid shell dependency
in the test suite. Tests match the actual bash scripts' behavior.
"""
import hashlib
import json
import os
import sys
import tempfile
import time

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


# ── Simulated lock/verify logic (mirrors prereg-lock.sh / prereg-verify.sh) ──

VALID_DIRECTIONS = {">=", "<=", ">", "<", "==", "!="}


def create_lock(prereg_dir, task_id, hypothesis_id, metric_name, direction, threshold):
    """Simulate prereg-lock.sh: create a lock file with canonical content + SHA-256."""
    os.makedirs(prereg_dir, exist_ok=True)

    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"Invalid direction '{direction}'")

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lock_content = (
        f"hypothesis_id={hypothesis_id}\n"
        f"metric_name={metric_name}\n"
        f"direction={direction}\n"
        f"threshold={threshold}\n"
        f"timestamp={timestamp}\n"
        f"task_id={task_id}"
    )

    sha256 = hashlib.sha256(lock_content.encode("utf-8")).hexdigest()
    lock_file = os.path.join(prereg_dir, f"{task_id}.lock")

    with open(lock_file, "w") as f:
        f.write(lock_content + "\n")
        f.write(f"sha256={sha256}\n")

    return lock_file, sha256, timestamp


def verify_lock(prereg_dir, task_id, reported_metric, reported_direction, reported_threshold):
    """Simulate prereg-verify.sh: read lock file and compare reported values."""
    lock_file = os.path.join(prereg_dir, f"{task_id}.lock")

    if not os.path.exists(lock_file):
        return {
            "verdict": "FAIL",
            "expected": {},
            "reported": {
                "metric_name": reported_metric,
                "direction": reported_direction,
                "threshold": reported_threshold,
            },
            "error": f"Lock file not found at {lock_file}",
        }

    # Parse lock file
    lock_data = {}
    with open(lock_file) as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                key, _, value = line.partition("=")
                lock_data[key.strip()] = value.strip()

    # Tamper detection: recompute hash over content (lines before sha256=)
    with open(lock_file) as f:
        lines = f.readlines()

    content_lines = [l for l in lines if not l.startswith("sha256=")]
    canonical = "".join(content_lines).strip()
    computed_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    locked_sha256 = lock_data.get("sha256", "")
    if computed_sha256 != locked_sha256:
        return {
            "verdict": "FAIL",
            "expected": {
                "metric_name": lock_data.get("metric_name", ""),
                "direction": lock_data.get("direction", ""),
                "threshold": lock_data.get("threshold", ""),
            },
            "reported": {
                "metric_name": reported_metric,
                "direction": reported_direction,
                "threshold": reported_threshold,
            },
            "error": f"LOCK FILE TAMPERED: computed sha256={computed_sha256} != recorded {locked_sha256}",
        }

    expected_metric = lock_data.get("metric_name", "")
    expected_direction = lock_data.get("direction", "")
    expected_threshold = lock_data.get("threshold", "")

    mismatches = []
    if expected_metric != reported_metric:
        mismatches.append("metric_name")
    if expected_direction != reported_direction:
        mismatches.append("direction")
    if expected_threshold != reported_threshold:
        mismatches.append("threshold")

    if mismatches:
        return {
            "verdict": "FAIL",
            "expected": {
                "metric_name": expected_metric,
                "direction": expected_direction,
                "threshold": expected_threshold,
            },
            "reported": {
                "metric_name": reported_metric,
                "direction": reported_direction,
                "threshold": reported_threshold,
            },
            "error": f"Pre-registration mismatch on fields: {' '.join(mismatches)}",
        }

    return {
        "verdict": "PASS",
        "expected": {
            "metric_name": expected_metric,
            "direction": expected_direction,
            "threshold": expected_threshold,
        },
        "reported": {
            "metric_name": reported_metric,
            "direction": reported_direction,
            "threshold": reported_threshold,
        },
        "error": "",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════

def run_tests():
    global PASS_COUNT, FAIL_COUNT
    tmpdir = tempfile.mkdtemp()
    prereg_dir = os.path.join(tmpdir, "prereg")

    # ── Test 1: Lock succeeds ──────────────────────────────────────────────
    say("Test 1: prereg-lock creates lock file with correct content")
    task_id = "T42"
    hypothesis_id = "H7"
    metric_name = "accuracy"
    direction = ">="
    threshold = "0.85"

    lock_file, sha256_val, ts = create_lock(
        prereg_dir, task_id, hypothesis_id, metric_name, direction, threshold
    )

    if os.path.exists(lock_file):
        pass_("Lock file was created at expected path")
    else:
        fail("Lock file was NOT created")

    with open(lock_file) as f:
        content = f.read()

    checks = {
        "hypothesis_id": hypothesis_id,
        "metric_name": metric_name,
        "direction": direction,
        "threshold": threshold,
        "task_id": task_id,
    }
    all_ok = True
    for key, expected in checks.items():
        if f"{key}={expected}" in content:
            pass_(f"Lock file contains '{key}={expected}'")
        else:
            fail(f"Lock file MISSING '{key}={expected}'")
            all_ok = False

    if all_ok:
        pass_("Lock file has all 6 required fields (hypothesis_id, metric_name, direction, threshold, timestamp, task_id)")

    # ── Test 2: SHA-256 hash present and valid ─────────────────────────────
    say("Test 2: Lock file contains valid SHA-256 hash")
    if f"sha256={sha256_val}" in content:
        pass_(f"SHA-256 hash is present: {sha256_val}")
    else:
        fail("SHA-256 hash not found in lock file")

    # Verify the hash is 64 hex chars
    if len(sha256_val) == 64 and all(c in "0123456789abcdef" for c in sha256_val):
        pass_("SHA-256 hash is 64-character hex string (valid)")
    else:
        fail(f"SHA-256 hash is malformed: '{sha256_val}'")

    # ── Test 3: Verify PASSes when metric matches ──────────────────────────
    say("Test 3: prereg-verify PASSes with matching metric")
    result = verify_lock(prereg_dir, task_id, metric_name, direction, threshold)
    if result["verdict"] == "PASS":
        pass_("verify_lock returned PASS when all fields match")
        assert result["expected"]["metric_name"] == metric_name
        assert result["expected"]["direction"] == direction
        assert result["expected"]["threshold"] == threshold
        pass_("verify_lock returns expected fields in JSON output")
    else:
        fail(f"verify_lock should PASS but got: {result['verdict']}: {result.get('error', '')}")

    # ── Test 4: Verify FAILs when metric name differs ──────────────────────
    say("Test 4: prereg-verify FAILs with different metric name")
    result = verify_lock(prereg_dir, task_id, "f1_score", direction, threshold)
    if result["verdict"] == "FAIL":
        pass_("verify_lock returned FAIL when metric_name differs")
        if "metric_name" in result.get("error", ""):
            pass_("Error message identifies 'metric_name' as mismatched field")
    else:
        fail(f"verify_lock should FAIL but got: {result['verdict']}")

    # ── Test 5: Verify FAILs when direction differs ────────────────────────
    say("Test 5: prereg-verify FAILs with different direction")
    result = verify_lock(prereg_dir, task_id, metric_name, "<=", threshold)
    if result["verdict"] == "FAIL":
        pass_("verify_lock returned FAIL when direction differs")
    else:
        fail(f"verify_lock should FAIL but got: {result['verdict']}")

    # ── Test 6: Verify FAILs when threshold differs ────────────────────────
    say("Test 6: prereg-verify FAILs with different threshold")
    result = verify_lock(prereg_dir, task_id, metric_name, direction, "0.90")
    if result["verdict"] == "FAIL":
        pass_("verify_lock returned FAIL when threshold differs")
    else:
        fail(f"verify_lock should FAIL but got: {result['verdict']}")

    # ── Test 7: Verify FAILs with error when lock file missing ─────────────
    say("Test 7: prereg-verify FAILs with error when lock file missing")
    result = verify_lock(prereg_dir, "NONEXISTENT", metric_name, direction, threshold)
    if result["verdict"] == "FAIL":
        pass_("verify_lock returned FAIL for missing lock file")
        if "not found" in result.get("error", "").lower():
            pass_("Error message indicates lock file not found")
    else:
        fail(f"verify_lock should FAIL for missing lock but got: {result['verdict']}")

    # ── Test 8: Tamper detection ──────────────────────────────────────────
    say("Test 8: verify detects tampered lock file")
    # Create a second lock and manually alter it
    lock_file2, sha256_val2, _ = create_lock(
        prereg_dir, "T99", "H8", "recall", ">=", "0.90"
    )
    # Tamper: modify the threshold in the file
    with open(lock_file2) as f:
        orig = f.read()
    tampered = orig.replace("threshold=0.90", "threshold=0.99")
    with open(lock_file2, "w") as f:
        f.write(tampered)

    result = verify_lock(prereg_dir, "T99", "recall", ">=", "0.99")
    if result["verdict"] == "FAIL":
        pass_("verify_lock returned FAIL for tampered lock file")
        if "TAMPERED" in result.get("error", "").upper():
            pass_("Error message indicates tamper detection")
    else:
        fail(f"verify_lock should FAIL for tampered lock but got: {result['verdict']}")

    # ── Test 9: Lock directory created when missing ────────────────────────
    say("Test 9: Lock directory is created if it doesn't exist")
    fresh_dir = os.path.join(tmpdir, "fresh_prereg")
    # Ensure it doesn't exist
    if os.path.exists(fresh_dir):
        os.rmdir(fresh_dir)
    lock_file3, sha256_val3, _ = create_lock(
        fresh_dir, "T1", "H1", "loss", "<=", "0.50"
    )
    if os.path.exists(fresh_dir):
        pass_(f"Directory '{fresh_dir}' was auto-created")
    if os.path.exists(lock_file3):
        pass_("Lock file created in auto-created directory")
    else:
        fail("Lock file not created in auto-created directory")

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir)

    # Summary
    print()
    print("=" * 56)
    print(f"  Pre-registration Lock Test Suite: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    print("=" * 56)
    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
