#!/usr/bin/env python3
"""
Issue #29 — ROI/Exploitation Throttle Gate
Only throttles RE-MINING of REFUTED hypothesis families.
New/novel hypotheses are NEVER throttled — they use curiosity budget (#30).

INVARIANT: A hypothesis family can only be throttled when:
  1. It has been refuted before (exists in scar-tissue/objections.jsonl as BLOCK)
  2. It is being attempted again (same family_id in the current tick)
  3. The consecutive unproductive re-mining streak >= K

ROI ledger: {ledger}/roi/ledger.jsonl — per-tick spend + value
"""
import json, os, sys
from datetime import datetime, timezone

DEFAULT_STREAK_THRESHOLD = 3  # K: consecutive unproductive re-minings before throttle


def load_objections(objections_path):
    """Load scar-tissue objections — list of refuted family IDs."""
    refuted_families = set()
    if not os.path.exists(objections_path):
        return refuted_families
    with open(objections_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("verdict") == "BLOCK" and rec.get("family_id"):
                    refuted_families.add(rec["family_id"])
            except json.JSONDecodeError:
                continue
    return refuted_families


def load_roi_ledger(ledger_path):
    """Load ROI ledger — list of tick records."""
    records = []
    if not os.path.exists(ledger_path):
        return records
    with open(ledger_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_family_streak(records, family_id):
    """Count consecutive unproductive re-minings for a family (most recent first)."""
    streak = 0
    for rec in reversed(records):
        if rec.get("family_id") != family_id:
            continue
        if rec.get("value", 0) > 0:
            break  # productive run resets streak
        streak += 1
    return streak


def check_roi_gate(hypothesis_family_id, refuted_families, roi_records, streak_threshold=None):
    """
    Check if a hypothesis family should be throttled.
    
    Returns:
        dict with keys:
            - throttled: bool
            - reason: str
            - family_id: str
            - streak: int
    """
    K = streak_threshold or DEFAULT_STREAK_THRESHOLD

    # NEW/NOVEL hypothesis → NEVER throttle
    if hypothesis_family_id not in refuted_families:
        return {
            "throttled": False,
            "reason": "novel_hypothesis",
            "family_id": hypothesis_family_id,
            "streak": 0,
        }

    # REFUTED family → check streak
    streak = get_family_streak(roi_records, hypothesis_family_id)

    if streak >= K:
        return {
            "throttled": True,
            "reason": f"refuted_family_streak_{streak}_gte_{K}",
            "family_id": hypothesis_family_id,
            "streak": streak,
        }

    return {
        "throttled": False,
        "reason": "refuted_but_streak_below_threshold",
        "family_id": hypothesis_family_id,
        "streak": streak,
    }


def append_to_roi_ledger(ledger_path, tick_id, family_id, spend_usd, value):
    """Append a tick record to the ROI ledger."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tick_id": tick_id,
        "family_id": family_id,
        "spend_usd": spend_usd,
        "value": value,
    }
    os.makedirs(os.path.dirname(ledger_path) or ".", exist_ok=True)
    with open(ledger_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: roi-gate.py <ledger_dir> <family_id>", file=sys.stderr)
        sys.exit(1)

    ledger_dir = sys.argv[1]
    family_id = sys.argv[2]

    objections_path = os.path.join(ledger_dir, "scar-tissue", "objections.jsonl")
    roi_ledger_path = os.path.join(ledger_dir, "roi", "ledger.jsonl")

    refuted = load_objections(objections_path)
    records = load_roi_ledger(roi_ledger_path)
    result = check_roi_gate(family_id, refuted, records)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["throttled"] else 0)
