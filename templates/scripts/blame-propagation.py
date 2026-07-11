#!/usr/bin/env python3
"""
blame-propagation.py — Deterministic blame propagation for hypothesis FAIL (#58)

CANONICAL MODE (default):
  A failed hypothesis adds blame ONLY to the beliefs explicitly listed in that
  hypothesis's `relies_on`. Propagation is DIRECT only — it does NOT transitively
  chase hypothesis-to-hypothesis chains for canonical mutation.

  Idempotent: re-running adds no duplicate blame (blamed_by is a set).

DIAGNOSTIC MODE (read-only):
  `trace` — shows the full transitive dependency chain without mutating anything.
  Has cycle detection and bounded depth.

Commands:
  propagate <hypotheses_dir> <failed_hypothesis_id> [beliefs_file]
      — Direct canonical blame: mark beliefs listed in relies_on as suspect.
        ONLY adds blame to beliefs, does NOT transitively chase hypotheses.
        Idempotent: blamed_by list deduplicates.
  check <hypotheses_dir> <hypothesis_id>
      — Check if a hypothesis's direct dependency beliefs are suspect.
  trace <hypotheses_dir> <hypothesis_id> [--max-depth=10]
      — READ-ONLY. Show transitive dependency chain. Does NOT mutate anything.
        Has cycle detection. Bounded by max-depth (default 10).

Output:
  JSON with affected belief IDs or dependency chain.

Exit codes:
  0 = success
  1 = error
"""

import json
import os
import sys

import yaml


def datetime_utcnow():
    return __import__("datetime").datetime.utcnow().isoformat() + "Z"


def load_hypothesis(hypotheses_dir, hid):
    for prefix in ["", "H-", "hypothesis-"]:
        for ext in [".yaml", ".yml", ".json"]:
            path = os.path.join(hypotheses_dir, f"{prefix}{hid}{ext}")
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f) if ext == ".json" else yaml.safe_load(f)
    return None


def find_all_hypotheses(hypotheses_dir):
    results = []
    if not os.path.isdir(hypotheses_dir):
        return results
    for fname in os.listdir(hypotheses_dir):
        if fname.endswith((".yaml", ".yml", ".json")):
            try:
                with open(os.path.join(hypotheses_dir, fname)) as f:
                    data = json.load(f) if fname.endswith(".json") else yaml.safe_load(f)
                if isinstance(data, dict) and "id" in data:
                    results.append(data)
            except (yaml.YAMLError, json.JSONDecodeError):
                pass
    return results


def load_beliefs(beliefs_file):
    """Load beliefs.yaml and return (data, beliefs_list)."""
    if not os.path.exists(beliefs_file):
        return None, []
    with open(beliefs_file) as f:
        data = yaml.safe_load(f)
    return data, data.get("beliefs", [])


def save_beliefs(beliefs_file, data):
    with open(beliefs_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


# ── Direct Canonical Blame ─────────────────────────────────────────────────

def propagate_direct_blame(hypotheses_dir, failed_id, beliefs_file=None):
    """
    Canonical blame propagation: DIRECT only.
    
    1. Find the failed hypothesis.
    2. Read its relies_on — these are BELIEF IDs, not hypothesis IDs.
    3. For each belief in relies_on, append failed_id to blamed_by (idempotent).
    4. Set the belief status to 'suspect' if not already suspect/refuted/evicted.
    
    Does NOT transitively chase hypothesis-to-hypothesis chains.
    """
    if not os.path.isdir(hypotheses_dir):
        return {"error": f"Hypotheses directory not found: {hypotheses_dir}"}

    h = load_hypothesis(hypotheses_dir, failed_id)
    if not h:
        return {"error": f"Hypothesis {failed_id} not found"}

    relies_on = h.get("relies_on", [])
    if not isinstance(relies_on, list):
        relies_on = [relies_on]

    if not beliefs_file or not os.path.exists(beliefs_file):
        return {
            "action": "noop",
            "failed_hypothesis": failed_id,
            "relies_on_beliefs": relies_on,
            "note": "No beliefs file provided. Blame targets recorded but no beliefs mutated.",
            "target_beliefs": relies_on,
        }

    data, beliefs = load_beliefs(beliefs_file)
    if data is None:
        return {"error": f"Beliefs file not found: {beliefs_file}"}

    affected = []
    already_blamed = []
    not_found = []

    for belief_id in relies_on:
        found = False
        for belief in beliefs:
            if belief.get("id") == belief_id:
                found = True
                blamed_by = belief.get("blamed_by", [])
                if not isinstance(blamed_by, list):
                    blamed_by = []

                # Idempotency: skip if already blamed by this hypothesis
                if failed_id in blamed_by:
                    already_blamed.append(belief_id)
                    continue

                # Append blame (idempotent)
                blamed_by.append(failed_id)
                belief["blamed_by"] = blamed_by

                # Set status to suspect if not already suspect/refuted/evicted
                old_status = belief.get("status", "active")
                if old_status not in ("suspect", "refuted", "evicted"):
                    belief["status"] = "suspect"
                    belief["suspect_age"] = 0
                    belief["updated_at"] = datetime_utcnow()
                    affected.append({
                        "belief_id": belief_id,
                        "old_status": old_status,
                        "new_status": "suspect",
                        "blamed_by": [failed_id],
                        "blamed_by_total": len(blamed_by),
                    })
                else:
                    affected.append({
                        "belief_id": belief_id,
                        "old_status": old_status,
                        "new_status": old_status,
                        "blamed_by": [failed_id],
                        "blamed_by_total": len(blamed_by),
                        "note": f"Belief already {old_status}, blame recorded but status unchanged",
                    })
                break

        if not found:
            not_found.append(belief_id)

    save_beliefs(beliefs_file, data)

    return {
        "action": "direct_blame",
        "failed_hypothesis": failed_id,
        "target_beliefs": relies_on,
        "affected_beliefs": affected,
        "already_blamed": already_blamed,
        "not_found_beliefs": not_found,
        "total_affected": len(affected),
    }


# ── Check — Read-only ──────────────────────────────────────────────────────

def check_blocked(hypotheses_dir, hypothesis_id, beliefs_file=None):
    """Check if hypothesis is blocked by suspect/refuted beliefs in its relies_on."""
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
            "reason": "No dependency beliefs",
        }

    if not beliefs_file or not os.path.exists(beliefs_file):
        return {
            "hypothesis_id": hypothesis_id,
            "blocked": "unknown",
            "relies_on": relies_on,
            "reason": "No beliefs file, cannot check belief status",
        }

    _, beliefs = load_beliefs(beliefs_file)
    belief_map = {b.get("id", ""): b for b in beliefs}

    blocked_by = []
    for bid in relies_on:
        b = belief_map.get(bid)
        if b and b.get("status") in ("suspect", "refuted", "evicted"):
            blocked_by.append({
                "belief_id": bid,
                "status": b.get("status"),
            })

    return {
        "hypothesis_id": hypothesis_id,
        "blocked": len(blocked_by) > 0,
        "blocked_by": blocked_by,
        "relies_on": relies_on,
    }


# ── Trace — Read-only transitive diagnostic ────────────────────────────────

def trace_chain(hypotheses_dir, hypothesis_id, beliefs_file=None, max_depth=10):
    """
    READ-ONLY transitive dependency trace. Does NOT mutate anything.
    Has cycle detection. Bounded by max_depth.
    """
    all_h = find_all_hypotheses(hypotheses_dir)
    h_map = {h.get("id", ""): h for h in all_h if h.get("id")}

    _, beliefs = load_beliefs(beliefs_file) if beliefs_file and os.path.exists(beliefs_file) else (None, [])
    belief_map = {b.get("id", ""): b for b in beliefs}

    visited = set()
    chain = []

    def _trace(hid, depth):
        if depth > max_depth:
            chain.append({"hypothesis_id": hid, "_truncated": True, "reason": "max_depth exceeded"})
            return
        if hid in visited:
            chain.append({"hypothesis_id": hid, "_cycle": True})
            return
        visited.add(hid)

        h = h_map.get(hid)
        if not h:
            chain.append({"hypothesis_id": hid, "_not_found": True})
            return

        status = h.get("status", "unknown")
        relies_on_beliefs = h.get("relies_on", [])
        if not isinstance(relies_on_beliefs, list):
            relies_on_beliefs = [relies_on_beliefs]

        belief_statuses = {}
        for bid in relies_on_beliefs:
            b = belief_map.get(bid)
            belief_statuses[bid] = b.get("status", "unknown") if b else "not_found"

        entry = {
            "hypothesis_id": hid,
            "status": status,
            "relies_on_beliefs": relies_on_beliefs,
            "belief_statuses": belief_statuses,
        }
        chain.append(entry)

        # Find hypotheses that depend on this hypothesis's beliefs
        for other_hid, other_h in h_map.items():
            if other_hid in visited:
                continue
            other_relies = other_h.get("relies_on", [])
            if not isinstance(other_relies, list):
                other_relies = [other_relies]
            if any(bid in other_relies for bid in relies_on_beliefs):
                _trace(other_hid, depth + 1)

    _trace(hypothesis_id, 0)
    return {
        "chain": chain,
        "depth": len(chain),
        "max_depth": max_depth,
        "note": "READ-ONLY diagnostic. Does not mutate any state.",
    }


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "propagate":
        if len(sys.argv) < 4:
            print("Usage: blame-propagation.py propagate <hypotheses_dir> <failed_hypothesis_id> [beliefs_file]", file=sys.stderr)
            sys.exit(1)
        hyps_dir = sys.argv[2]
        failed_id = sys.argv[3]
        beliefs_file = sys.argv[4] if len(sys.argv) > 4 else None
        result = propagate_direct_blame(hyps_dir, failed_id, beliefs_file)
        print(json.dumps(result, indent=2))
        sys.exit(1 if result.get("error") else 0)

    elif command == "check":
        if len(sys.argv) < 4:
            print("Usage: blame-propagation.py check <hypotheses_dir> <hypothesis_id> [beliefs_file]", file=sys.stderr)
            sys.exit(1)
        hyps_dir = sys.argv[2]
        hid = sys.argv[3]
        beliefs_file = sys.argv[4] if len(sys.argv) > 4 else None
        result = check_blocked(hyps_dir, hid, beliefs_file)
        print(json.dumps(result, indent=2))
        sys.exit(1 if result.get("error") else 0)

    elif command == "trace":
        if len(sys.argv) < 4:
            print("Usage: blame-propagation.py trace <hypotheses_dir> <hypothesis_id> [--max-depth=N] [beliefs_file]", file=sys.stderr)
            sys.exit(1)
        hyps_dir = sys.argv[2]
        hid = sys.argv[3]
        max_depth = 10
        beliefs_file = None
        for arg in sys.argv[4:]:
            if arg.startswith("--max-depth="):
                max_depth = int(arg.split("=", 1)[1])
            elif not arg.startswith("--"):
                beliefs_file = arg
        result = trace_chain(hyps_dir, hid, beliefs_file, max_depth)
        print(json.dumps(result, indent=2))
        sys.exit(0)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
