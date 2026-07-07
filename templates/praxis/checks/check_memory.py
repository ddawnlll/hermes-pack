#!/usr/bin/env python3
"""
Praxis check: verify no memory writes were attempted by the worker.
Workers are NOT allowed to write to canonical memory — only the orchestrator
may update memory after Praxis PASS + gate verdict.
"""
import json, sys, os

def main():
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("EVIDENCE_BUNDLE", "")

    if not bundle_path or not os.path.exists(bundle_path):
        print(json.dumps({"check": "memory_write", "status": "FAIL",
                          "message": f"Evidence bundle not found: {bundle_path}"}))
        sys.exit(1)

    with open(bundle_path) as f:
        bundle = json.load(f)

    # Check evidence bundle itself doesn't contain memory write claims
    claims = bundle.get("claims", [])
    memory_claims = [c for c in claims if "memory" in c.get("claim", "").lower() and "write" in c.get("claim", "").lower()]
    if memory_claims:
        print(json.dumps({"check": "memory_write", "status": "WARN",
                          "message": f"Worker made {len(memory_claims)} claims involving memory writes — must be rejected by orchestrator",
                          "detail": {"memory_claims": memory_claims}}))

    # Check for any memory_write artifact (forbidden for workers)
    changed_files = bundle.get("diff", {}).get("changed_files", [])
    memory_files = [f for f in changed_files if "memory" in f.lower() or ".hermes" in f]
    if memory_files:
        print(json.dumps({"check": "memory_write", "status": "FAIL",
                          "message": f"Worker modified memory-related files: {memory_files}",
                          "detail": {"memory_files_touched": memory_files}}))
        sys.exit(1)

    print(json.dumps({"check": "memory_write", "status": "PASS",
                      "detail": {"memory_files_touched": [], "worker_memory_claims": len(memory_claims)}}))

if __name__ == "__main__":
    main()
