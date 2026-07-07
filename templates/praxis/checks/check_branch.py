#!/usr/bin/env python3
"""
Praxis check: verify the worker's branch has been pushed to remote.
Without a pushed branch, merge is impossible.
"""
import json, subprocess, sys, os

def main():
    repo_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REPO_DIR", ".")
    bundle_path = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("EVIDENCE_BUNDLE", "")

    if not bundle_path or not os.path.exists(bundle_path):
        print(json.dumps({"check": "branch_pushed", "status": "FAIL",
                          "message": f"Evidence bundle not found: {bundle_path}"}))
        sys.exit(1)

    with open(bundle_path) as f:
        bundle = json.load(f)

    branch = bundle.get("git", {}).get("branch", "")
    if not branch:
        print(json.dumps({"check": "branch_pushed", "status": "FAIL",
                          "message": "No branch in evidence bundle"}))
        sys.exit(1)

    # Check if the branch exists on remote
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            capture_output=True, text=True, cwd=repo_dir, timeout=15
        )
        if branch in result.stdout:
            print(json.dumps({"check": "branch_pushed", "status": "PASS",
                              "detail": {"branch": branch}}))
        else:
            print(json.dumps({"check": "branch_pushed", "status": "FAIL",
                              "message": f"Branch '{branch}' not found on remote origin",
                              "detail": {"branch": branch}}))
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print(json.dumps({"check": "branch_pushed", "status": "WARN",
                          "message": "git ls-remote timed out, cannot verify push"}))
    except Exception as e:
        print(json.dumps({"check": "branch_pushed", "status": "ERROR",
                          "message": str(e)}))

if __name__ == "__main__":
    main()
