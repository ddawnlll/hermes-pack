#!/usr/bin/env python3
"""
blame-propagation.py — Deterministic blame propagation for hypothesis FAIL (#58)

When a hypothesis FAILs, blame propagates to all hypotheses that `relies_on` it.
Propagation is IDEMPOTENT: running twice on the same state produces the same result.

Usage:
  blame-propagation.py propagate <hypotheses_dir> <failed_hypothesis_id>
  blame-propagation.py check <hypotheses_dir> <hypothesis_id>

Commands:
  propagate   — Mark all dependents of the failed hypothesis as failed/refuted
  check       — Check if a hypothesis is blocked by a failed dependency

Output:
  JSON with affected hypothesis IDs and the propagation action taken.

Exit codes:
  0 = success (or no dependencies affected)
  1 = error or propagation failure
"""
import hashlib
import json
import os
import sys
import time

import yaml


def datetime_utcnow():
    """Return ISO 8601 UTC timestamp string."""
    return __import__("datetime").datetime.utcnow().isoformat() + "Z"


def load_hypothesis(hypotheses_dir, hid):
    """Load a hypothesis YAML file by ID."""
    # Try various file naming patterns
    for prefix in ["", "H-", "hypothesis-"]:
        for ext in [".yaml", ".yml", ".json"]:
            path = os.path.join(hypotheses_dir, f"{prefix}{hid}{ext}")
            if os.path.exists(path):
                with open(path) as f:
                    if ext == ".json":
                        return json.load(f)
                    else:
                        return yaml.safe_load(f)
    return None


def find_all_hypotheses(hypotheses_dir):
    """Find all hypothesis files in the directory."""
    results = []
    if not os.path.isdir(hypotheses_dir):
        return results
    for fname in os.listdir(hypotheses_dir):
        if fname.endswith((".yaml", ".yml", ".json")):
            try:
                with open(os.path.join(hypotheses_dir, fname)) as f:
                    if fname.endswith(".json"):
                        data = json.load(f)
                    else:
                        data = yaml.safe_load(f)
                if isinstance(data, dict) and "id" in data:
                    results.append(data)
            except (yaml.YAMLError, json.JSONDecodeError):
                pass
    return results


def _write_hypothesis(hypotheses_dir, h):
    """Write a hypothesis dict back to its file."""
    hid = h.get("id", "")
    for prefix in ["", "H-", "hypothesis-"]:
        for ext in [".yaml", ".yml", ".json"]:
            path = os.path.join(hypotheses_dir, f"{prefix}{hid}{ext}")
            if os.path.exists(path) or (prefix == "" and ext == ".yaml"):
                if ext == ".json":
                    with open(path, "w") as f:
                        json.dump(h, f, indent=2)
                else:
                    with open(path, "w") as f:
                        yaml.dump(h, f, default_flow_style=False)
                return
    # Fallback: write as YAML
    with open(os.path.join(hypotheses_dir, f"{hid}.yaml"), "w") as f:
        yaml.dump(h, f, default_flow_style=False)


def propagate_fail(hypotheses_dir, failed_id):
    """Propagate FAIL transitively to all hypotheses whose dependencies have failed.
    
    Idempotent: running twice on the same state produces identical results.
    Transitive: if H-002 relies on H-001 (failed), and H-003 relies on H-002,
    then both H-002 and H-003 are marked failed.
    """
    if not os.path.isdir(hypotheses_dir):
        return {"error": f"Hypotheses directory not found: {hypotheses_dir}"}

    affected = []
    already_failed = []
    not_found = []
    errors = []

    # Build a mutable map: hypothesis_id -> data
    all_h = find_all_hypotheses(hypotheses_dir)
    h_map = {h.get("id", ""): h for h in all_h if h.get("id")}

    if failed_id not in h_map:
        not_found.append(failed_id)

    # Collect all failed IDs (initial + any we mark during propagation)
    failed_ids = set()
    if failed_id in h_map and h_map[failed_id].get("status") in ("failed", "refuted"):
        failed_ids.add(failed_id)

    # If the root hasn't been marked failed yet, mark it
    if failed_id in h_map and h_map[failed_id].get("status") not in ("failed", "refuted", "cancelled"):
        old = h_map[failed_id].get("status", "active")
        h_map[failed_id]["status"] = "failed"
        h_map[failed_id]["updated_at"] = datetime_utcnow()
        _write_hypothesis(hypotheses_dir, h_map[failed_id])
        failed_ids.add(failed_id)
        if failed_id != failed_id or True:  # Always report the root
            affected.append({
                "hypothesis_id": failed_id,
                "old_status": old,
                "new_status": "failed",
                "reason": "Root failure"
            })

    # Transitive propagation: iteratively find hypotheses whose dependencies
    # intersect failed_ids, mark them, and add them to failed_ids.
    changed = True
    while changed:
        changed = False
        for hid, h in list(h_map.items()):
            if hid in failed_ids:
                continue
            if h.get("status") in ("failed", "refuted", "cancelled"):
                already_failed.append(hid)
                failed_ids.add(hid)
                changed = True
                continue

            relies_on = h.get("relies_on", [])
            if not isinstance(relies_on, list):
                relies_on = [relies_on]

            # Check if any dependency is in failed_ids
            dep_failed = [d for d in relies_on if d in failed_ids]
            if dep_failed:
                current_status = h.get("status", "draft")
                # Idempotency: skip if already failed/refuted
                if current_status in ("failed", "refuted", "cancelled"):
                    already_failed.append(hid)
                    failed_ids.add(hid)
                    continue

                # Propagate FAIL
                h["status"] = "failed"
                h["updated_at"] = datetime_utcnow()
                _write_hypothesis(hypotheses_dir, h)
                failed_ids.add(hid)
                changed = True
                affected.append({
                    "hypothesis_id": hid,
                    "old_status": current_status,
                    "new_status": "failed",
                    "reason": f"Dependencies failed: {dep_failed}"
                })

    return {
        "failed_hypothesis": failed_id,
        "propagated_to": affected,
        "already_failed": already_failed,
        "not_found": not_found,
        "errors": errors,
        "total_affected": len(affected),
    }


def check_blocked(hypotheses_dir, hypothesis_id):
    """Check if a hypothesis is blocked by any failed dependency. Idempotent check only."""
    h = load_hypothesis(hypotheses_dir, hypothesis_id)
    if not h:
        return {"error": f"Hypothesis {hypothesis_id} not found"}

    relies_on = h.get("relies_on", [])
    if not isinstance(relies_on, list):
        relies_on = [relies_on]

    if not relies_on:
        return {
            "hypothesis_id": hypothesis_id,
            "blocked": False,
            "reason": "No dependencies",
        }

    all_h = find_all_hypotheses(hypotheses_dir)
    dep_map = {dh.get("id", ""): dh for dh in all_h}

    blocked_by = []
    for dep_id in relies_on:
        dep = dep_map.get(dep_id)
        if dep and dep.get("status") in ("failed", "refuted", "cancelled"):
            blocked_by.append(dep_id)

    return {
        "hypothesis_id": hypothesis_id,
        "blocked": len(blocked_by) > 0,
        "blocked_by": blocked_by,
        "relies_on": relies_on,
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "propagate":
        if len(sys.argv) < 4:
            print("Usage: blame-propagation.py propagate <hypotheses_dir> <failed_hypothesis_id>", file=sys.stderr)
            sys.exit(1)
        result = propagate_fail(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
        if result.get("errors"):
            sys.exit(1)
        sys.exit(0)

    elif command == "check":
        if len(sys.argv) < 4:
            print("Usage: blame-propagation.py check <hypotheses_dir> <hypothesis_id>", file=sys.stderr)
            sys.exit(1)
        result = check_blocked(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
        if result.get("error"):
            sys.exit(1)
        sys.exit(0)

    else:
        print(f"Unknown command: {command}. Use 'propagate' or 'check'.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
