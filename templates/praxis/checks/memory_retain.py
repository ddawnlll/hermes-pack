#!/usr/bin/env python3
"""
Memory Retain Gate — writes verified facts to canonical memory AFTER Praxis PASS + gate verdict.

This script is called by the orchestrator (NOT by workers). It:
1. Reads the gate_result.json (must be PASS)
2. Reads the evidence_bundle.json (must exist)
3. Extracts verified claims from memory_write_candidates
4. Writes structured facts to:
   - .alphaforge/orchestrator/current_state.md (canonical truth)
   - .alphaforge/orchestrator/memory/ (JSON fact store)
   - Hindsight API (if available, via HTTP)

Usage:
  python3 memory-retain.py <run_id> [--hindsight-url http://localhost:9885]

Exit code: 0 = facts retained, 1 = blocked (no PASS verdict)
"""
import json, sys, os, argparse
from datetime import datetime, timezone
from pathlib import Path

def read_json(path):
    with open(path) as f:
        return json.load(f)

def append_to_current_state(state_path, fact_entry):
    """Append a verified fact to current_state.md's Verified Facts section."""
    state_path = Path(state_path)
    if not state_path.exists():
        state_path.write_text("# Current Verified State\n\n## Verified Facts\n\n")
    
    content = state_path.read_text()
    marker = "## Verified Facts"
    if marker not in content:
        content += f"\n{marker}\n\n"
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fact_line = f"- `{fact_entry['source_run_id']}` | {fact_entry['fact']} | confidence={fact_entry['confidence']} | {timestamp}\n"
    
    if fact_line not in content:
        # Insert after marker or at end of Verified Facts section
        lines = content.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if line.startswith("## ") and i > 0 and line != marker:
                insert_idx = i - 1
                break
        if insert_idx is None:
            lines.append(fact_line)
        else:
            lines.insert(insert_idx, fact_line.rstrip())
        
        state_path.write_text("\n".join(lines))
        return True
    return False

def write_fact_to_memory_dir(memory_dir, fact_entry):
    """Write a verified fact as JSON to the memory directory."""
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    fact_file = memory_dir / f"{fact_entry['source_run_id']}.json"
    if fact_file.exists():
        existing = json.loads(fact_file.read_text())
        existing["facts"].append(fact_entry)
        fact_file.write_text(json.dumps(existing, indent=2))
    else:
        fact_file.write_text(json.dumps({
            "source_run_id": fact_entry["source_run_id"],
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "facts": [fact_entry]
        }, indent=2))
    return True

def send_to_hindsight(hindsight_url, fact_entry):
    """Send fact to Hindsight API for persistent memory."""
    if not hindsight_url:
        return False
    try:
        import urllib.request
        payload = json.dumps({
            "type": "verified_research_result",
            "source_run_id": fact_entry["source_run_id"],
            "fact": fact_entry["fact"],
            "confidence": fact_entry["confidence"],
            "evidence_paths": fact_entry.get("evidence_paths", []),
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }).encode()
        req = urllib.request.Request(
            f"{hindsight_url}/retain",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[memory-retain] Hindsight write skipped: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Memory Retain Gate")
    parser.add_argument("run_id", help="Run ID from the evidence bundle")
    parser.add_argument("--ledger-dir", default=None, help="Path to .alphaforge/orchestrator")
    parser.add_argument("--hindsight-url", default=None, help="Hindsight API URL (e.g. http://localhost:9885)")
    args = parser.parse_args()

    # Resolve ledger dir
    if args.ledger_dir:
        ledger = Path(args.ledger_dir)
    else:
        # Try to find from repo layout
        cwd = Path.cwd()
        for p in [cwd, cwd.parent, cwd / ".alphaforge"]:
            candidate = p / ".alphaforge" / "orchestrator"
            if candidate.exists():
                ledger = candidate
                break
        else:
            ledger = Path(".alphaforge/orchestrator")
    
    evidence_dir = ledger / "evidence" / args.run_id
    gate_result_path = evidence_dir / "gate_result.json"
    evidence_bundle_path = evidence_dir / "evidence_bundle.json"
    
    # 1. Read gate_result
    if not gate_result_path.exists():
        print(f"[memory-retain] BLOCKED: gate_result.json not found at {gate_result_path}")
        sys.exit(1)
    
    gate = read_json(gate_result_path)
    if gate.get("status") != "PASS":
        print(f"[memory-retain] BLOCKED: gate status is '{gate.get('status')}', not PASS")
        print(f"[memory-retain] Only verified PASS results can be written to memory.")
        sys.exit(1)
    
    # 2. Read evidence bundle
    if not evidence_bundle_path.exists():
        print(f"[memory-retain] BLOCKED: evidence_bundle.json not found")
        sys.exit(1)
    
    bundle = read_json(evidence_bundle_path)
    
    # 3. Extract memory candidates from gate result
    candidates = gate.get("memory_write_candidates", [])
    if not candidates:
        print(f"[memory-retain] No memory candidates in gate result — nothing to retain.")
        sys.exit(0)
    
    # 4. Write each candidate
    retained = 0
    state_path = ledger / "current_state.md"
    memory_dir = ledger / "memory"
    
    for c in candidates:
        fact_entry = {
            "source_run_id": args.run_id,
            "hypothesis_id": bundle.get("hypothesis_id", "unknown"),
            "task_id": bundle.get("task_id", "unknown"),
            "fact": c.get("fact", ""),
            "confidence": c.get("confidence", 0.7),
            "evidence_paths": [
                str(evidence_bundle_path),
                str(gate_result_path)
            ]
        }
        
        # Skip empty facts
        if not fact_entry["fact"]:
            continue
        
        # Write to current_state.md
        append_to_current_state(state_path, fact_entry)
        
        # Write to memory directory
        write_fact_to_memory_dir(memory_dir, fact_entry)
        
        # Send to Hindsight (optional)
        if args.hindsight_url:
            send_to_hindsight(args.hindsight_url, fact_entry)
        
        retained += 1
        print(f"[memory-retain] ✓ Retained: {fact_entry['fact'][:80]}...")
    
    print(f"[memory-retain] Done: {retained} facts retained to {memory_dir}")
    print(f"[memory-retain] current_state.md updated at {state_path}")
    sys.exit(0)

if __name__ == "__main__":
    main()
