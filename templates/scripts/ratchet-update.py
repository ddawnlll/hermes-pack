#!/usr/bin/env python3
"""
Adaptive Ratchet — Red Team bar adjustment based on pass/block ratio
Issue #26: Red Team'in çıtası pass-rate'e göre yükselsin/alçalsın

RATCHET RULES:
  blocking_ratio < 0.20  → TOO EASY  → tighten (more OOS folds, stricter controls)
  blocking_ratio > 0.80  → TOO HARD  → loosen  (fewer folds, wider embargo)
  0.20 <= ratio <= 0.80  → BALANCED  → no change

Level range: [-3, 5] (monotonic quality axis)
"""
import json, os, sys
from datetime import datetime, timezone

def update_ratchet(ledger_dir):
    ratchet_file = os.path.join(ledger_dir, "ratchet.json")
    objections_file = os.path.join(ledger_dir, "redteam", "objections.jsonl")
    history_window = 20

    os.makedirs(os.path.dirname(ratchet_file), exist_ok=True)

    # Initialize if missing
    if not os.path.exists(ratchet_file):
        ratchet = {
            "schema_version": 1,
            "level": 0,
            "blocking_ratio": 0.0,
            "window_size": 20,
            "history": [],
            "last_updated": None
        }
        with open(ratchet_file, "w") as f:
            json.dump(ratchet, f, indent=2)
        print(json.dumps({"action": "init", "level": 0}))
        return

    # Read objections
    if not os.path.exists(objections_file):
        print(json.dumps({"action": "skip", "reason": "no objections file"}))
        return

    with open(objections_file) as f:
        lines = f.readlines()

    if not lines:
        print(json.dumps({"action": "skip", "reason": "empty objections"}))
        return

    # Last N lines
    recent = lines[-history_window:]
    total = len(recent)
    blocking = sum(1 for l in recent if '"BLOCK"' in l)
    ratio = blocking / total if total > 0 else 0.0

    # Read current
    with open(ratchet_file) as f:
        ratchet = json.load(f)

    old_level = ratchet.get("level", 0)
    action = "maintain"

    if ratio < 0.20:
        ratchet["level"] = min(ratchet["level"] + 1, 5)
        action = "tighten"
    elif ratio > 0.80:
        ratchet["level"] = max(ratchet["level"] - 1, -3)
        action = "loosen"

    ratchet["blocking_ratio"] = ratio
    ratchet["window_size"] = total
    ratchet["last_updated"] = datetime.now(timezone.utc).isoformat()

    ratchet["history"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "blocking": blocking,
        "total": total,
        "ratio": ratio,
        "old_level": old_level,
        "new_level": ratchet["level"],
        "action": action
    })
    ratchet["history"] = ratchet["history"][-50:]

    with open(ratchet_file, "w") as f:
        json.dump(ratchet, f, indent=2)

    print(json.dumps({
        "action": action,
        "old_level": old_level,
        "new_level": ratchet["level"],
        "blocking_ratio": ratio,
        "blocking": blocking,
        "total": total
    }))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ratchet-update.py <ledger_dir>", file=sys.stderr)
        sys.exit(1)
    update_ratchet(sys.argv[1])
