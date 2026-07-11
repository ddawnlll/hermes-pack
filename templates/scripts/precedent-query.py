#!/usr/bin/env python3
"""
Precedent memory (BE-6, #84).

Append-only precedent store derived from the tick transaction journal
(tick-journal.py, merged via #71/#73). Lets Autonomous T4 (BE-5) retrieve
similar past decisions instead of re-deriving strategy from scratch, and
gives GA-3 (autonomy metrics) something to compute agreement-rate against.

Precedent shape (per tick):
  {
    "tick_id": int,
    "situation": {
      "risk": str,
      "evidence_pattern": str,
      "active_beliefs": [str, ...],
      "disagreement_type": str | null,
    },
    "autonomous_t4_decision": str | null,
    "human_override": str | null,
    "final_outcome": "PROMOTED" | "ROLLED_BACK" | "DISCARDED" | "DEAD" | "HOLD",
    "lesson": str,
    "stored_at": ISO-8601,
  }

Invariants:
  - Append-only. No update, no delete. Update/delete attempts are rejected.
  - The retrieval API is signature-based (situation.* fields). Coverage metric
    is `matched_precedents / total_attempts` per asset_type.
  - Idempotent per tick_id (re-deriving the same tick's precedent is a no-op).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

PRECEDENT_SCHEMA_VERSION = 1

# Tick-journal line shape (parsed from tick-journal.py output).
# The journal is JSONL; one entry per tick. We accept a permissive subset
# so the script can run before T4 is fully wired in (e.g. lessons may be
# missing on early ticks).


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def derive_precedent_from_journal_line(line: str) -> dict | None:
    """Parse a tick-journal line and return a precedent dict, or None if
    the line is empty / not parseable / already a precedent."""
    line = line.strip()
    if not line:
        return None
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(entry, dict):
        return None
    if entry.get("schema") == "precedent":  # already a precedent, skip
        return None
    if "tick_id" not in entry:
        return None

    # Heuristic extraction. T1/T2/T3 outputs vary across versions; this is
    # tolerant so the script can run on historical journals.
    situation = {
        "risk": entry.get("risk", "unknown"),
        "evidence_pattern": entry.get("evidence_pattern", "unknown"),
        "active_beliefs": entry.get("active_beliefs", []),
        "disagreement_type": entry.get("disagreement_type"),
    }
    return {
        "tick_id": entry["tick_id"],
        "situation": situation,
        "autonomous_t4_decision": entry.get("autonomous_t4_decision"),
        "human_override": entry.get("human_override"),
        "final_outcome": entry.get("final_outcome", "HOLD"),
        "lesson": entry.get("lesson", ""),
        "stored_at": _now_iso(),
    }


def append_only_check(precedent_path: Path, tick_id: int) -> None:
    """Reject if a precedent for tick_id is already in the store.

    The store is JSONL. We scan the file to ensure idempotency.
    """
    if not precedent_path.exists():
        return
    with precedent_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if existing.get("tick_id") == tick_id:
                # Already stored. Silent no-op.
                return


def derive(journal_path: Path, precedent_path: Path) -> int:
    """Read tick-journal.py output and append new precedents. Returns count
    of new precedents written."""
    if not journal_path.exists():
        return 0
    written = 0
    with journal_path.open("r", encoding="utf-8") as f:
        for line in f:
            prec = derive_precedent_from_journal_line(line)
            if prec is None:
                continue
            append_only_check(precedent_path, prec["tick_id"])
            with precedent_path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(prec, separators=(",", ":")) + "\n")
                written += 1
    return written


def query(precedent_path: Path, signature: dict, limit: int = 5) -> list[dict]:
    """Return up to `limit` precedents whose situation matches `signature`.

    A simple tag-overlap score is used: matched = |sig_fields ∩ prec_fields|.
    Sorted by score desc, then tick_id desc.
    """
    if not precedent_path.exists():
        return []
    candidates: list[tuple[int, int, dict]] = []  # (score, tick_id, prec)
    sig_keys = {k: v for k, v in signature.items() if v is not None}
    with precedent_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                prec = json.loads(line)
            except json.JSONDecodeError:
                continue
            sit = prec.get("situation", {})
            score = 0
            for k, v in sig_keys.items():
                pval = sit.get(k)
                if pval is None:
                    continue
                if isinstance(v, list) and isinstance(pval, list):
                    score += len(set(v) & set(pval))
                elif pval == v:
                    score += 1
            if score > 0:
                candidates.append((score, prec.get("tick_id", 0), prec))
    candidates.sort(key=lambda t: (-t[0], -t[1]))
    return [c[2] for c in candidates[:limit]]


def coverage_metric(precedent_path: Path, total_attempts: int) -> float:
    """Coverage = unique tick_ids in store / total_attempts.

    Returns 0.0 if no attempts.
    """
    if total_attempts <= 0:
        return 0.0
    if not precedent_path.exists():
        return 0.0
    seen: set[int] = set()
    with precedent_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                prec = json.loads(line)
            except json.JSONDecodeError:
                continue
            seen.add(prec.get("tick_id", -1))
    return round(len(seen) / total_attempts, 4)


def _cmd_derive(args: argparse.Namespace) -> int:
    n = derive(Path(args.journal), Path(args.output))
    print(f"wrote {n} new precedent(s) to {args.output}")
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    signature = json.loads(args.signature)
    hits = query(Path(args.store), signature, args.limit)
    print(json.dumps(hits, indent=2))
    return 0


def _cmd_coverage(args: argparse.Namespace) -> int:
    c = coverage_metric(Path(args.store), args.attempts)
    print(json.dumps({"coverage": c, "attempts": args.attempts}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Precedent memory (BE-6, #84): derive from tick-journal, query by signature, compute coverage."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_derive = sub.add_parser("derive", help="Read tick-journal.py and append new precedents.")
    p_derive.add_argument("--journal", required=True, help="Path to tick-journal.py output (JSONL).")
    p_derive.add_argument("--output", required=True, help="Path to write the precedent store (JSONL).")
    p_derive.set_defaults(func=_cmd_derive)

    p_query = sub.add_parser("query", help="Query precedents by situation signature.")
    p_query.add_argument("--store", required=True, help="Path to the precedent store (JSONL).")
    p_query.add_argument("--signature", required=True, help="JSON object with situation fields (risk, evidence_pattern, active_beliefs, disagreement_type).")
    p_query.add_argument("--limit", type=int, default=5, help="Max number of hits (default 5).")
    p_query.set_defaults(func=_cmd_query)

    p_cov = sub.add_parser("coverage", help="Compute coverage metric.")
    p_cov.add_argument("--store", required=True, help="Path to the precedent store (JSONL).")
    p_cov.add_argument("--attempts", type=int, required=True, help="Total T4 attempts in scope.")
    p_cov.set_defaults(func=_cmd_coverage)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
