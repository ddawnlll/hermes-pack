#!/usr/bin/env python3
"""
Praxis → Hindsight Memory Bridge
Writes a Praxis Truth Kernel verdict to Hindsight memory.

Usage:
  python3 tools/praxis-hindsight-bridge.py <run_id> [--hindsight-url http://localhost:9885] [--bank-id hermes]

Called by orchestrator after Praxis verdict.
Writes PASS verdicts as verified_research_result.
Writes FAIL verdicts as refuted_hypothesis (scar-tissue memory, issue #23).
"""
import json, sys, os, argparse, urllib.request

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", help="Praxis run ID")
    parser.add_argument("--hindsight-url", default=os.environ.get("HINDSIGHT_URL", "http://localhost:9885"))
    parser.add_argument("--bank-id", default="hermes")
    args = parser.parse_args()

    # Locate the verdict file
    praxis_dir = os.path.join(".praxis", "runs", args.run_id)
    verdict_path = os.path.join(praxis_dir, "verdict.json")
    if not os.path.exists(verdict_path):
        # Also check absolute ledger path
        ledger = os.environ.get("LEDGER_DIR", ".alphaforge/orchestrator")
        verdict_path = os.path.join(ledger, "evidence", args.run_id, "gate_result.json")
        if not os.path.exists(verdict_path):
            print(f"[praxis-hindsight] No verdict found at {praxis_dir} or {verdict_path}")
            sys.exit(1)

    with open(verdict_path) as f:
        verdict = json.load(f)

    verdict_status = verdict.get("verdict", verdict.get("status", "UNKNOWN"))
    is_pass = verdict_status == "PASS"
    is_fail = verdict_status in ("FAIL", "HOLD")

    # Issue #23: write FAIL verdicts as refuted_hypothesis (scar-tissue memory)
    if not is_pass and not is_fail:
        print(f"[praxis-hindsight] Skipping: verdict is '{verdict_status}', not PASS/FAIL/HOLD")
        sys.exit(0)

    # Extract facts from gate result
    facts = []
    candidates = verdict.get("memory_write_candidates", verdict.get("gateVerdicts", []))

    for c in (candidates if isinstance(candidates, list) else []):
        if isinstance(c, dict):
            fact_text = c.get("fact", c.get("gateName", ""))
            if fact_text:
                facts.append(fact_text)

    if not facts:
        # Fallback: write gate summary
        gates = verdict.get("gateVerdicts", [])
        for g in gates:
            if isinstance(g, dict) and g.get("verdict") == "PASS":
                facts.append(f"Gate {g.get('gateName','?')}: PASS")

    if not facts:
        facts.append(f"Praxis verification PASS for {args.run_id}")

    # Build Hindsight items
    items = []
    if is_pass:
        for fact in facts[:5]:  # limit to 5
            items.append({
                "content": f"[Praxis] {fact}",
                "source": "praxis_truth_kernel",
                "metadata": {
                    "run_id": args.run_id,
                    "verdict": verdict_status,
                    "type": "verified_research_result",
                    "confidence": "0.95"
                }
            })
    else:
        # FAIL / HOLD → refuted_hypothesis (scar-tissue, issue #23)
        for fact in facts[:5]:
            items.append({
                "content": f"[Praxis REFUTED] {fact}",
                "source": "praxis_truth_kernel",
                "metadata": {
                    "run_id": args.run_id,
                    "verdict": verdict_status,
                    "type": "refuted_hypothesis",
                    "confidence": "0.3"
                }
            })

    # Send to Hindsight
    url = f"{args.hindsight_url}/v1/default/banks/{args.bank_id}/memories"
    payload = json.dumps({"items": items}).encode()

    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json"
    }, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode()
            print(f"[praxis-hindsight] Retained {len(items)} facts to Hindsight ({url})")
            print(f"[praxis-hindsight] Response: {result[:200]}")
            sys.exit(0)
    except urllib.error.HTTPError as e:
        print(f"[praxis-hindsight] HTTP {e.code}: {e.read().decode()[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"[praxis-hindsight] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
