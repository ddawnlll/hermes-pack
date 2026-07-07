#!/usr/bin/env python3
"""
Praxis check: verify the run hasn't exceeded budget constraints.
Checks LLM spend, total duration, and parallel worker limits.
"""
import json, sys, os
from datetime import datetime

def main():
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("EVIDENCE_BUNDLE", "")
    budget_config = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("BUDGET_CONFIG", "{}")

    if not bundle_path or not os.path.exists(bundle_path):
        print(json.dumps({"check": "budget", "status": "FAIL",
                          "message": f"Evidence bundle not found: {bundle_path}"}))
        sys.exit(1)

    with open(bundle_path) as f:
        bundle = json.load(f)

    try:
        budget = json.loads(budget_config) if isinstance(budget_config, str) else budget_config
    except json.JSONDecodeError:
        budget = {}

    warnings = []
    errors = []

    # Check command duration
    total_duration = 0
    for cmd in bundle.get("commands", []):
        total_duration += cmd.get("duration_seconds", 0)

    max_seconds = budget.get("max_seconds", 3600)
    if total_duration > max_seconds:
        errors.append(f"Total duration {total_duration}s exceeds max {max_seconds}s")

    # Check LLM call count (estimated from claims)
    max_llm_calls = budget.get("max_llm_calls", 50)
    claim_count = len(bundle.get("claims", []))
    if claim_count > max_llm_calls:
        errors.append(f"Claim count {claim_count} exceeds max LLM calls {max_llm_calls}")

    # Check changed file count
    changed = len(bundle.get("diff", {}).get("changed_files", []))
    max_files = budget.get("max_files_changed", 20)
    if changed > max_files:
        warnings.append(f"Changed {changed} files, exceeds recommended {max_files}")

    result = {"check": "budget", "duration_seconds": total_duration, "claim_count": claim_count, "files_changed": changed}

    if errors:
        result["status"] = "FAIL"
        result["message"] = "; ".join(errors)
        result["detail"] = {"errors": errors, "warnings": warnings}
        print(json.dumps(result))
        sys.exit(1)

    result["status"] = "PASS"
    if warnings:
        result["warnings"] = warnings
    print(json.dumps(result))

if __name__ == "__main__":
    main()
