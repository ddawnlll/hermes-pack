#!/usr/bin/env python3
"""
Executive Packet generator (BE-4, #83).

After T3 Arbiter decision, the Orchestrator generates a structured Executive
Packet — the bounded input for T4 (human or autonomous). This prevents
T4 from re-reading the full tick history (avoiding duplicate reasoning /
context bloat).

The packet is JSON-serialized (per schema/executive-packet.schema.json) and
appended to tick-journal.py for replay (Gate #7: Executive replay).

CLI:
    executive-packet.py --input <t123_inputs.json> --output <packet.json> [--journal <tick_journal_path>]

Inputs (--input JSON) carry the T1/T2/T3 outputs and supporting context:
  {
    "tick_id": int,
    "objective": str,
    "active_frame": str,
    "relevant_beliefs": [...],
    "suspect_beliefs": [...],
    "hypothesis": str,
    "worker_result": {...} | null,
    "praxis_verdict": "PASS" | "FAIL" | "INCONCLUSIVE",
    "evidence_pointers": [...],
    "t1_recommendation": str,
    "t2_objection": str,
    "t3_adjudication": str,
    "unresolved_uncertainties": [...],
    "expected_gain": {"magnitude": str, "confidence": float},
    "blast_radius": str,
    "candidate_scope": str,
    "shadow_plan": {...},
    "rollback_plan": {...},
    "historical_precedents": [...],
  }

Invariants:
  - One packet per tick. Re-generating a packet for the same tick is a no-op
    (idempotency via journal check; duplicate packet rejected).
  - The packet is appended to the journal BEFORE T4 starts; replay uses
    the journal copy, not the live pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PACKET_SCHEMA_VERSION = 1


def build_packet(inputs: dict) -> dict:
    """Build an Executive Packet from the T1/T2/T3 inputs.

    The packet is a strict dict matching schema/executive-packet.schema.json.
    All required fields are present; no defaults are filled in silently —
    the caller is expected to provide a complete input or the build is
    rejected.
    """
    required = (
        "tick_id", "objective", "active_frame", "hypothesis",
        "praxis_verdict", "t1_recommendation", "t2_objection",
        "t3_adjudication", "expected_gain", "blast_radius",
        "candidate_scope", "shadow_plan", "rollback_plan",
    )
    missing = [k for k in required if k not in inputs]
    if missing:
        raise ValueError(f"Missing required input fields: {missing}")

    return {
        "schema_version": PACKET_SCHEMA_VERSION,
        "tick_id": inputs["tick_id"],
        "objective": inputs["objective"],
        "active_frame": inputs["active_frame"],
        "relevant_beliefs": inputs.get("relevant_beliefs", []),
        "suspect_beliefs": inputs.get("suspect_beliefs", []),
        "hypothesis": inputs["hypothesis"],
        "worker_result": inputs.get("worker_result"),
        "praxis_verdict": inputs["praxis_verdict"],
        "evidence_pointers": inputs.get("evidence_pointers", []),
        "t1_recommendation": inputs["t1_recommendation"],
        "t2_objection": inputs["t2_objection"],
        "t3_adjudication": inputs["t3_adjudication"],
        "unresolved_uncertainties": inputs.get("unresolved_uncertainties", []),
        "expected_gain": inputs["expected_gain"],
        "blast_radius": inputs["blast_radius"],
        "candidate_scope": inputs["candidate_scope"],
        "shadow_plan": inputs["shadow_plan"],
        "rollback_plan": inputs["rollback_plan"],
        "historical_precedents": inputs.get("historical_precedents", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def append_to_journal(packet: dict, journal_path: Path) -> None:
    """Append the packet to tick-journal.py. Idempotent per tick_id.

    The journal is the canonical replay source (Gate #7: Executive replay);
    T4 reads the journal copy, not the live pipeline.
    """
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    # Idempotency: if a packet for this tick_id already exists in the journal,
    # do not append. We assume the journal is JSONL (one packet per line).
    tick_id = packet["tick_id"]
    if journal_path.exists():
        with journal_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if existing.get("tick_id") == tick_id:
                    # Already in journal — duplicate packet rejected.
                    return

    with journal_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(packet, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate an Executive Packet (BE-4, #83) for T4 consumption."
    )
    parser.add_argument(
        "--input", required=True, type=Path,
        help="Path to a JSON file with T1/T2/T3 outputs and supporting context."
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Path to write the generated packet (JSON)."
    )
    parser.add_argument(
        "--journal", type=Path, default=None,
        help="Optional path to tick-journal.py for replay append. "
             "Default: templates/scripts/tick-journal.py."
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1

    inputs = json.loads(args.input.read_text(encoding="utf-8"))
    try:
        packet = build_packet(inputs)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")

    if args.journal is not None:
        append_to_journal(packet, args.journal)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
