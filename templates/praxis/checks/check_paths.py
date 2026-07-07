#!/usr/bin/env python3
"""
Praxis check: verify worker did not touch forbidden paths.
Uses the diff metadata from the evidence bundle.
Fail-closed: any forbidden file touch = FAIL.
"""
import json, sys, os

def main():
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("EVIDENCE_BUNDLE", "")
    forbidden_config = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("FORBIDDEN_PATHS", "")

    if not bundle_path or not os.path.exists(bundle_path):
        print(json.dumps({"check": "forbidden_paths", "status": "FAIL",
                          "message": f"Evidence bundle not found: {bundle_path}"}))
        sys.exit(1)

    with open(bundle_path) as f:
        bundle = json.load(f)

    forbidden_list = []
    if forbidden_config:
        # Support comma-separated or file-based config
        if os.path.exists(forbidden_config):
            with open(forbidden_config) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        forbidden_list.append(line)
        else:
            forbidden_list = [p.strip() for p in forbidden_config.split(",") if p.strip()]

    worker_forbidden = bundle.get("diff", {}).get("forbidden_files_touched", [])

    if worker_forbidden:
        print(json.dumps({"check": "forbidden_paths", "status": "FAIL",
                          "message": f"Worker touched forbidden files: {worker_forbidden}",
                          "detail": {"forbidden_files_touched": worker_forbidden}}))
        sys.exit(1)

    # Also check changed files against the forbidden list
    changed = bundle.get("diff", {}).get("changed_files", [])
    violations = []
    for f in changed:
        for pattern in forbidden_list:
            if pattern in f or f.startswith(pattern.rstrip("/")):
                violations.append(f)

    if violations:
        print(json.dumps({"check": "forbidden_paths", "status": "FAIL",
                          "message": f"Changed files match forbidden patterns: {violations}",
                          "detail": {"violations": violations}}))
        sys.exit(1)

    print(json.dumps({"check": "forbidden_paths", "status": "PASS"}))

if __name__ == "__main__":
    main()
