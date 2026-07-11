#!/usr/bin/env python3
"""
whisper-channel.py — Context channel: whisper inbox + briefing + regime (#68)

Untrusted whisper inbox with bounded briefing.
Sanitizes or structurally isolates prompt-like external content.
External input may suggest candidates but may NOT issue system instructions.
Regime-change detection based on deterministic inputs.

Commands:
  whisper <whisper_dir> <external_input>
      — Submit external input as untrusted whisper
  brief <whisper_dir> <output_dir>
      — Generate bounded briefing from recent whispers
  detect-regime <state_file> <ledger_dir>
      — Detect regime changes from deterministic signals

Feature flag: whisper_channel
Default: disabled
"""

import json
import os
import sys
import uuid
from datetime import datetime


SYSTEM_INSTRUCTION_MARKERS = [
    "you are now", "ignore previous", "system instruction", "system prompt",
    "override", "you must act as", "forget all", "new instructions",
    "your new role", "disregard",
]


def get_ts():
    return datetime.utcnow().isoformat() + "Z"


def sanitize_input(text):
    """Detect and isolate prompt-like content. Return sanitized version."""
    text_lower = text.lower()
    warnings = []
    for marker in SYSTEM_INSTRUCTION_MARKERS:
        if marker in text_lower:
            warnings.append(f"Detected potential system instruction marker: '{marker}'")

    return {
        "original_length": len(text),
        "sanitized": text[:2000],  # Truncate to bounded length
        "markers_detected": warnings,
        "is_safe": len(warnings) == 0,
    }


def whisper(whisper_dir, external_input):
    """Submit external input as untrusted whisper."""
    os.makedirs(whisper_dir, exist_ok=True)

    sanitized = sanitize_input(external_input)

    entry = {
        "whisper_id": f"WSP-{uuid.uuid4().hex[:8].upper()}",
        "received_at": get_ts(),
        "original_length": sanitized["original_length"],
        "content_excerpt": sanitized["sanitized"][:200],
        "markers_detected": sanitized["markers_detected"],
        "is_trusted": False,
        "is_safe": sanitized["is_safe"],
        "status": "received",
    }

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = os.path.join(whisper_dir, f"whispers-{date_str}.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return {
        "status": "whisper_received",
        "whisper_id": entry["whisper_id"],
        "is_safe": sanitized["is_safe"],
        "warnings": sanitized["markers_detected"],
    }


def brief(whisper_dir, output_dir):
    """Generate bounded briefing from recent whispers."""
    os.makedirs(output_dir, exist_ok=True)

    brief_items = []
    if os.path.isdir(whisper_dir):
        for fname in sorted(os.listdir(whisper_dir), reverse=True)[:3]:
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(whisper_dir, fname)
            with open(fpath) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("is_safe", False):
                        brief_items.append({
                            "whisper_id": entry.get("whisper_id"),
                            "content": entry.get("content_excerpt", ""),
                            "received_at": entry.get("received_at"),
                        })

    briefing = {
        "generated_at": get_ts(),
        "item_count": len(brief_items),
        "items": brief_items[-10:],  # Last 10 safe whispers
        "note": "External input is UNTRUSTED. These are candidate suggestions only. "
                "They do NOT modify canonical beliefs or control files.",
    }

    out_file = os.path.join(output_dir, f"briefing-{datetime.utcnow().strftime('%Y-%m-%d')}.json")
    with open(out_file, "w") as f:
        json.dump(briefing, f, indent=2)

    return briefing


def detect_regime(state_file, ledger_dir):
    """Detect regime changes from deterministic signals."""
    signals = {}

    if os.path.exists(state_file):
        with open(state_file) as f:
            state = json.load(f)
        signals["stagnation"] = state.get("stagnation", 0)
        signals["momentum"] = state.get("momentum", 0)
        signals["tick"] = state.get("tick", 0)

    # Detect regime based on signals
    if signals.get("stagnation", 0) > 10:
        regime = "stagnant"
    elif signals.get("momentum", 0) > 1.0:
        regime = "high_momentum"
    elif signals.get("momentum", 0) < -0.5:
        regime = "declining"
    else:
        regime = "normal"

    return {
        "regime": regime,
        "signals": signals,
        "detected_at": get_ts(),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "whisper":
        if len(sys.argv) < 4:
            print("Usage: whisper-channel.py whisper <whisper_dir> <external_input>")
            sys.exit(1)
        result = whisper(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))

    elif cmd == "brief":
        if len(sys.argv) < 4:
            print("Usage: whisper-channel.py brief <whisper_dir> <output_dir>")
            sys.exit(1)
        result = brief(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))

    elif cmd == "detect-regime":
        if len(sys.argv) < 4:
            print("Usage: whisper-channel.py detect-regime <state_file> <ledger_dir>")
            sys.exit(1)
        result = detect_regime(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
