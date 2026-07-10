#!/usr/bin/env python3
"""
prereg-lock.py — Pre-registration Lock Gate (Issue #27 / #54)

Locks metric, threshold, and relies_on at hypothesis dispatch time so that
post-hoc changes (p-hacking) are detected deterministically.

Two subcommands:

  lock    — Create a lock file at dispatch time.
  verify  — Verify reported values against an existing lock file.

Uses the same directory structure as the Praxis LockGate pattern but with
a simpler file format (KEY=VALUE lines + SHA-256 hash).

Fail-closed: on any error, outputs {"verdict": "FAIL", "error": "..."} and
exits with code 1.

Usage:
  prereg-lock.py lock <locks_dir> <task_id> <hypothesis_id> <metric_name> <direction> <threshold> [relies_on...]
  prereg-lock.py verify <locks_dir> <task_id> <metric_name> <direction> <threshold> [relies_on...]

Examples:
  prereg-lock.py lock /repo/.ledger/locks T42 H7 accuracy >= 0.85
  prereg-lock.py lock /repo/.ledger/locks T42 H7 sharpe >= 1.5 "H5 H6"
  prereg-lock.py verify /repo/.ledger/locks T42 accuracy >= 0.85

Output (stdout JSON):
  For lock:
    {"action": "lock", "task_id": "...", "lock_file": "...", "sha256": "..."}
  For verify:
    {"verdict": "PASS"|"FAIL", "task_id": "...", "error": "..."}

Exit codes:
  0 = success (lock created or verify PASS)
  1 = failure (lock not created or verify FAIL)
"""
import hashlib
import json
import os
import sys
import time

VALID_DIRECTIONS = {">=", "<=", ">", "<", "==", "!="}


def create_lock(locks_dir, task_id, hypothesis_id, metric_name, direction, threshold, relies_on=None):
    """Create a lock file with canonical content + SHA-256 integrity hash."""
    os.makedirs(locks_dir, exist_ok=True)

    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"Invalid direction '{direction}'. Must be one of: {', '.join(sorted(VALID_DIRECTIONS))}")

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Build canonical content
    lines = [
        f"hypothesis_id={hypothesis_id}",
        f"metric_name={metric_name}",
        f"direction={direction}",
        f"threshold={threshold}",
        f"timestamp={timestamp}",
        f"task_id={task_id}",
    ]
    if relies_on:
        relies_on_str = " ".join(relies_on) if isinstance(relies_on, list) else relies_on
        lines.append(f"relies_on={relies_on_str}")

    lock_content = "\n".join(lines)
    sha256 = hashlib.sha256(lock_content.encode("utf-8")).hexdigest()

    lock_file = os.path.join(locks_dir, f"{task_id}.lock")
    with open(lock_file, "w") as f:
        f.write(lock_content + "\n")
        f.write(f"sha256={sha256}\n")

    return lock_file, sha256, timestamp


def verify_lock(locks_dir, task_id, reported_metric, reported_direction, reported_threshold, reported_relies_on=None):
    """Read lock file and compare reported values. Detect tampering."""
    lock_file = os.path.join(locks_dir, f"{task_id}.lock")

    if not os.path.exists(lock_file):
        return {
            "verdict": "FAIL",
            "expected": {},
            "reported": {
                "metric_name": reported_metric,
                "direction": reported_direction,
                "threshold": reported_threshold,
            },
            "error": f"Lock file not found at {lock_file}. Hypothesis may not have been pre-registered.",
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

    # Compare fields
    expected_metric = lock_data.get("metric_name", "")
    expected_direction = lock_data.get("direction", "")
    expected_threshold = lock_data.get("threshold", "")
    expected_relies_on = lock_data.get("relies_on", "")

    mismatches = []
    if expected_metric != reported_metric:
        mismatches.append(f"metric_name (locked='{expected_metric}' vs reported='{reported_metric}')")
    if expected_direction != reported_direction:
        mismatches.append(f"direction (locked='{expected_direction}' vs reported='{reported_direction}')")
    if expected_threshold != reported_threshold:
        mismatches.append(f"threshold (locked='{expected_threshold}' vs reported='{reported_threshold}')")

    # relies_on comparison (if both are present)
    if reported_relies_on is not None and expected_relies_on:
        reported_ro = " ".join(reported_relies_on) if isinstance(reported_relies_on, list) else reported_relies_on
        if expected_relies_on != reported_ro:
            mismatches.append(f"relies_on (locked='{expected_relies_on}' vs reported='{reported_ro}')")

    if mismatches:
        return {
            "verdict": "FAIL",
            "expected": {
                "metric_name": expected_metric,
                "direction": expected_direction,
                "threshold": expected_threshold,
                "relies_on": expected_relies_on,
            },
            "reported": {
                "metric_name": reported_metric,
                "direction": reported_direction,
                "threshold": reported_threshold,
            },
            "error": f"Pre-registration mismatch on field(s): {'; '.join(mismatches)}",
        }

    return {
        "verdict": "PASS",
        "expected": {
            "metric_name": expected_metric,
            "direction": expected_direction,
            "threshold": expected_threshold,
            "relies_on": expected_relies_on,
        },
        "reported": {
            "metric_name": reported_metric,
            "direction": reported_direction,
            "threshold": reported_threshold,
        },
        "error": "",
    }


def main():
    if len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    subcommand = sys.argv[1]

    try:
        if subcommand == "lock":
            if len(sys.argv) < 7:
                print("Usage: prereg-lock.py lock <locks_dir> <task_id> <hypothesis_id> <metric_name> <direction> <threshold> [relies_on...]", file=sys.stderr)
                sys.exit(1)

            locks_dir = sys.argv[2]
            task_id = sys.argv[3]
            hypothesis_id = sys.argv[4]
            metric_name = sys.argv[5]
            direction = sys.argv[6]
            threshold = sys.argv[7]
            relies_on = sys.argv[8:] if len(sys.argv) > 8 else None

            lock_file, sha256_val, ts = create_lock(
                locks_dir, task_id, hypothesis_id, metric_name, direction, threshold, relies_on
            )

            output = {
                "action": "lock",
                "task_id": task_id,
                "hypothesis_id": hypothesis_id,
                "lock_file": lock_file,
                "sha256": sha256_val,
                "timestamp": ts,
            }
            print(json.dumps(output, indent=2))
            sys.exit(0)

        elif subcommand == "verify":
            if len(sys.argv) < 6:
                print("Usage: prereg-lock.py verify <locks_dir> <task_id> <metric_name> <direction> <threshold> [relies_on...]", file=sys.stderr)
                sys.exit(1)

            locks_dir = sys.argv[2]
            task_id = sys.argv[3]
            metric_name = sys.argv[4]
            direction = sys.argv[5]
            threshold = sys.argv[6]
            relies_on = sys.argv[7:] if len(sys.argv) > 7 else None

            result = verify_lock(locks_dir, task_id, metric_name, direction, threshold, relies_on)

            output = {
                "verdict": result["verdict"],
                "task_id": task_id,
                "expected": result.get("expected", {}),
                "reported": result.get("reported", {}),
            }
            if result.get("error"):
                output["error"] = result["error"]

            print(json.dumps(output, indent=2))
            sys.exit(0 if result["verdict"] == "PASS" else 1)

        else:
            print(f"Unknown subcommand: {subcommand}. Use 'lock' or 'verify'.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        output = {
            "verdict": "FAIL",
            "error": f"Unexpected error: {e}",
        }
        print(json.dumps(output))
        sys.exit(1)


if __name__ == "__main__":
    main()
