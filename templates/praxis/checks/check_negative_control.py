#!/usr/bin/env python3
"""
Praxis check: verify the worker has included a negative control run.
High-risk tasks require a negative control to detect false positives.
Fail-closed for high-risk tasks without control.
"""
import json, sys, os

def main():
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("EVIDENCE_BUNDLE", "")
    risk_level = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("RISK_LEVEL", "low")

    if not bundle_path or not os.path.exists(bundle_path):
        print(json.dumps({"check": "negative_control", "status": "FAIL",
                          "message": f"Evidence bundle not found: {bundle_path}"}))
        sys.exit(1)

    with open(bundle_path) as f:
        bundle = json.load(f)

    controls = bundle.get("controls", {})

    if risk_level in ("high", "critical") and controls.get("negative_control_run") is not True:
        print(json.dumps({"check": "negative_control", "status": "FAIL",
                          "message": f"negative_control_run=false for {risk_level} risk task — required",
                          "detail": {"risk_level": risk_level, "negative_control_run": controls.get("negative_control_run")}}))
        sys.exit(1)

    if risk_level == "medium" and controls.get("negative_control_run") is not True:
        print(json.dumps({"check": "negative_control", "status": "WARN",
                          "message": "negative_control_run not set — recommended for medium risk"}))
        sys.exit(0)

    print(json.dumps({"check": "negative_control", "status": "PASS",
                      "detail": {"negative_control_run": controls.get("negative_control_run")}}))

if __name__ == "__main__":
    main()
