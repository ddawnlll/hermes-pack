#!/usr/bin/env python3
"""
provenance-track.py — Provenance tagging and channel hit-rate tracking (#69)

Records provenance for every dispatched hypothesis and every merge.
A merge without provenance fails validation.

Usage:
  provenance-track.py record <provenance_dir> <entity_type> <entity_id> <channel> [--source=...] [--run-id=...] [--hypothesis-id=...] [--relies-on=...] [--cost=...]
  provenance-track.py validate <provenance_dir> <entity_type> <entity_id>
  provenance-track.py report <provenance_dir> [--days=N]

Commands:
  record    — Record a provenance entry
  validate  — Validate that an entity has provenance (fails if missing)
  report    — Generate channel hit-rate report

Output:
  JSON with provenance record or validation result.

Exit codes:
  0 = success / validation passed
  1 = failure / validation failed / error
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta


def get_timestamp():
    return datetime.utcnow().isoformat() + "Z"


def record_provenance(provenance_dir, entity_type, entity_id, channel,
                      source=None, run_id=None, hypothesis_id=None,
                      relies_on=None, cost_usd=0):
    """Record a provenance entry. Idempotent check: deduplicates by entity_id + channel + source."""
    os.makedirs(provenance_dir, exist_ok=True)

    # Idempotency: check if identical record already exists
    existing = find_records(provenance_dir, entity_id=entity_id, channel=channel)
    if existing:
        return {"status": "exists", "provenance_id": existing[0].get("provenance_id")}

    record = {
        "schema_version": 1,
        "provenance_id": f"PRV-{uuid.uuid4().hex[:12].upper()}",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "channel": channel,
        "source": source or channel,
        "timestamp": get_timestamp(),
        "run_id": run_id or "",
        "hypothesis_id": hypothesis_id or "",
        "relies_on": relies_on if relies_on else [],
        "cost_usd": float(cost_usd),
        "metadata": {},
    }

    # Write to daily file for append-only log
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = os.path.join(provenance_dir, f"provenance-{date_str}.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(record) + "\n")

    return {"status": "recorded", "provenance_id": record["provenance_id"], "file": log_file}


def find_records(provenance_dir, entity_id=None, channel=None, entity_type=None, days=None):
    """Find provenance records matching filters."""
    results = []
    if not os.path.isdir(provenance_dir):
        return results

    cutoff = None
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)

    for fname in sorted(os.listdir(provenance_dir)):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(provenance_dir, fname)
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entity_id and rec.get("entity_id") != entity_id:
                    continue
                if channel and rec.get("channel") != channel:
                    continue
                if entity_type and rec.get("entity_type") != entity_type:
                    continue
                if cutoff:
                    ts_str = rec.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass

                results.append(rec)

    return results


def validate_provenance(provenance_dir, entity_type, entity_id):
    """Validate that an entity has provenance. Fails if missing for merges."""
    records = find_records(provenance_dir, entity_id=entity_id, entity_type=entity_type)

    if not records:
        return {
            "verdict": "FAIL",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "error": f"No provenance records found for {entity_type} '{entity_id}'",
        }

    return {
        "verdict": "PASS",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "records": len(records),
        "channels": list(set(r.get("channel", "") for r in records)),
    }


def generate_report(provenance_dir, days=7):
    """Generate channel hit-rate report."""
    records = find_records(provenance_dir, days=days)

    # Aggregate by channel
    channel_stats = {}
    for rec in records:
        ch = rec.get("channel", "unknown")
        if ch not in channel_stats:
            channel_stats[ch] = {
                "total": 0,
                "hypotheses": 0,
                "merges": 0,
                "beliefs": 0,
                "ideas": 0,
                "experiments": 0,
                "total_cost": 0.0,
                "unique_entities": set(),
            }
        stats = channel_stats[ch]
        stats["total"] += 1
        etype = rec.get("entity_type", "")
        if etype == "hypothesis":
            stats["hypotheses"] += 1
        elif etype == "merge":
            stats["merges"] += 1
        elif etype == "belief":
            stats["beliefs"] += 1
        elif etype == "idea":
            stats["ideas"] += 1
        elif etype == "experiment":
            stats["experiments"] += 1
        stats["total_cost"] += float(rec.get("cost_usd", 0))
        stats["unique_entities"].add(rec.get("entity_id", ""))

    # Convert sets to counts
    for ch in channel_stats:
        channel_stats[ch]["unique_entities"] = len(channel_stats[ch]["unique_entities"])

    return {
        "period_days": days,
        "total_events": len(records),
        "channels": channel_stats,
        "generated_at": get_timestamp(),
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    provenance_dir = sys.argv[2]

    if command == "record":
        if len(sys.argv) < 6:
            print("Usage: provenance-track.py record <provenance_dir> <entity_type> <entity_id> <channel> [options]", file=sys.stderr)
            sys.exit(1)
        entity_type = sys.argv[3]
        entity_id = sys.argv[4]
        channel = sys.argv[5]

        # Parse optional flags
        kwargs = {}
        for i in range(6, len(sys.argv)):
            arg = sys.argv[i]
            if arg.startswith("--source="):
                kwargs["source"] = arg.split("=", 1)[1]
            elif arg.startswith("--run-id="):
                kwargs["run_id"] = arg.split("=", 1)[1]
            elif arg.startswith("--hypothesis-id="):
                kwargs["hypothesis_id"] = arg.split("=", 1)[1]
            elif arg.startswith("--relies-on="):
                kwargs["relies_on"] = arg.split("=", 1)[1].split(",")
            elif arg.startswith("--cost="):
                kwargs["cost_usd"] = float(arg.split("=", 1)[1])

        result = record_provenance(provenance_dir, entity_type, entity_id, channel, **kwargs)
        print(json.dumps(result, indent=2))
        sys.exit(0)

    elif command == "validate":
        if len(sys.argv) < 5:
            print("Usage: provenance-track.py validate <provenance_dir> <entity_type> <entity_id>", file=sys.stderr)
            sys.exit(1)
        entity_type = sys.argv[3]
        entity_id = sys.argv[4]
        result = validate_provenance(provenance_dir, entity_type, entity_id)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["verdict"] == "PASS" else 1)

    elif command == "report":
        days = 7
        for i in range(3, len(sys.argv)):
            if sys.argv[i].startswith("--days="):
                days = int(sys.argv[i].split("=", 1)[1])
        result = generate_report(provenance_dir, days=days)
        print(json.dumps(result, indent=2))
        sys.exit(0)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
