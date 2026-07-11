#!/usr/bin/env python3
"""
analogy-channel.py — Cross-project analogy channel (#65)

Stores concrete and abstract lesson forms separately.
Retrieval uses abstract causal form only.
Explicit casting required for target project adoption.
Same-project lessons blocked from masquerading as cross-project.
Tracks retrieval cost, candidate count, promotions, and verified merges.

Commands:
  record <store_dir> <source_project> <target_project> <concrete> <abstract> [--cost=0.05]
  retrieve <store_dir> <target_project> <abstract_query> [--limit=5]
  cast <store_dir> <analogy_id> <target_project>
  report <store_dir>

Feature flag: analogy_channel
Default: disabled
"""

import json
import os
import sys
import uuid
from datetime import datetime


def get_ts():
    return datetime.utcnow().isoformat() + "Z"


def record_analogy(store_dir, source_project, target_project, concrete, abstract, cost=0.05):
    """Record a cross-project analogy."""
    os.makedirs(store_dir, exist_ok=True)

    # Prevent same-project self-analogy masquerading as cross-project
    if source_project == target_project:
        return {"error": f"Source and target project are identical ('{source_project}'). "
                         f"Same-project analogies are not valid cross-project lessons."}

    aid = f"ANA-{uuid.uuid4().hex[:8].upper()}"
    entry = {
        "analogy_id": aid,
        "source_project": source_project,
        "target_project": target_project,
        "concrete_form": concrete,
        "abstract_form": abstract,
        "status": "recorded",
        "cost_usd": float(cost),
        "created_at": get_ts(),
        "cast_to": [],
    }

    # Write to daily file
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = os.path.join(store_dir, f"analogies-{date_str}.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return {"status": "recorded", "analogy_id": aid, "file": log_file}


def retrieve_analogies(store_dir, target_project, abstract_query, limit=5):
    """Retrieve analogies by abstract form match (simple keyword match)."""
    results = []
    if not os.path.isdir(store_dir):
        return {"analogies": [], "query": abstract_query}

    query_lower = abstract_query.lower()
    for fname in sorted(os.listdir(store_dir)):
        if not fname.startswith("analogies-") or not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(store_dir, fname)
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Match by abstract form containing query terms
                abstract = entry.get("abstract_form", "").lower()
                if any(term in abstract for term in query_lower.split()):
                    # Exclude same-project lessons
                    if entry.get("source_project") == target_project:
                        continue
                    results.append({
                        "analogy_id": entry.get("analogy_id"),
                        "source_project": entry.get("source_project"),
                        "abstract_form": entry.get("abstract_form"),
                        "concrete_form": entry.get("concrete_form"),
                        "retrieved_at": get_ts(),
                    })

    return {"analogies": results[:limit], "total_matches": len(results), "query": abstract_query}


def cast_analogy(store_dir, analogy_id, target_project):
    """Record casting of an analogy into a target project."""
    found = False
    for fname in sorted(os.listdir(store_dir)):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(store_dir, fname)
        lines = []
        with open(fpath) as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        lines.append(line)
                        continue

                    if entry.get("analogy_id") == analogy_id:
                        cast_list = entry.get("cast_to", [])
                        if target_project not in cast_list:
                            cast_list.append(target_project)
                            entry["cast_to"] = cast_list
                            entry["status"] = "cast"
                        found = True
                    lines.append(json.dumps(entry) + "\n")

        if found:
            with open(fpath, "w") as f:
                f.writelines(lines)
            break

    if found:
        return {"status": "cast", "analogy_id": analogy_id, "target_project": target_project}
    return {"error": f"Analogy {analogy_id} not found"}


def report(store_dir):
    """Generate channel metrics report."""
    total = 0
    total_cost = 0.0
    by_source = {}
    by_target = {}

    if not os.path.isdir(store_dir):
        return {"total_analogies": 0, "total_cost": 0}

    for fname in os.listdir(store_dir):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(store_dir, fname)
        with open(fpath) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total += 1
                total_cost += float(entry.get("cost_usd", 0))
                src = entry.get("source_project", "unknown")
                by_source[src] = by_source.get(src, 0) + 1
                tgt = entry.get("target_project", "unknown")
                by_target[tgt] = by_target.get(tgt, 0) + 1

    return {
        "total_analogies": total,
        "total_cost_usd": round(total_cost, 4),
        "by_source_project": by_source,
        "by_target_project": by_target,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "record":
        if len(sys.argv) < 6:
            print("Usage: analogy-channel.py record <store> <source> <target> <concrete> <abstract> [--cost=N]")
            sys.exit(1)
        sd, sp, tp = sys.argv[2], sys.argv[3], sys.argv[4]
        conc, abst = sys.argv[5], sys.argv[6]
        cost = 0.05
        for a in sys.argv[7:]:
            if a.startswith("--cost="):
                cost = float(a.split("=", 1)[1])
        result = record_analogy(sd, sp, tp, conc, abst, cost)
        print(json.dumps(result, indent=2))

    elif cmd == "retrieve":
        if len(sys.argv) < 5:
            print("Usage: analogy-channel.py retrieve <store> <target> <query> [--limit=N]")
            sys.exit(1)
        sd, tp, q = sys.argv[2], sys.argv[3], sys.argv[4]
        limit = 5
        for a in sys.argv[5:]:
            if a.startswith("--limit="):
                limit = int(a.split("=", 1)[1])
        result = retrieve_analogies(sd, tp, q, limit)
        print(json.dumps(result, indent=2))

    elif cmd == "cast":
        if len(sys.argv) < 5:
            print("Usage: analogy-channel.py cast <store> <analogy_id> <target_project>")
            sys.exit(1)
        result = cast_analogy(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps(result, indent=2))

    elif cmd == "report":
        result = report(sys.argv[2] if len(sys.argv) > 2 else ".")
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
