#!/usr/bin/env python3
"""
Praxis check: verify data lineage integrity.
Ensures OOS window > train_end, checks for synthetic data, and validates
that the run doesn't exhibit obvious leakage.
"""
import json, sys, os
from datetime import datetime

def main():
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("EVIDENCE_BUNDLE", "")
    if not bundle_path or not os.path.exists(bundle_path):
        print(json.dumps({"check": "data_lineage", "status": "FAIL",
                          "message": f"Evidence bundle not found: {bundle_path}"}))
        sys.exit(1)

    with open(bundle_path) as f:
        bundle = json.load(f)

    lineage = bundle.get("data_lineage", {})
    controls = bundle.get("controls", {})

    errors = []

    # Check OOS window integrity
    train_end = lineage.get("train_end", "")
    oos_start = lineage.get("oos_start", "")
    if train_end and oos_start:
        try:
            train_dt = datetime.strptime(train_end, "%Y-%m-%d")
            oos_dt = datetime.strptime(oos_start, "%Y-%m-%d")
            if oos_dt <= train_dt:
                errors.append(f"OOS window ({oos_start}) does not start after train_end ({train_end})")
        except ValueError:
            errors.append(f"Cannot parse dates: train_end={train_end}, oos_start={oos_start}")
    else:
        if not train_end:
            errors.append("Missing train_end in data_lineage")
        if not oos_start:
            errors.append("Missing oos_start in data_lineage")

    # Check leakage gate
    if controls.get("leakage_check_passed") is not True:
        errors.append("leakage_check_passed is not true")

    # Check synthetic flag
    is_synthetic = lineage.get("is_synthetic", False)
    if is_synthetic:
        errors.append("Run uses synthetic data — requires label and must not be promoted")

    if errors:
        print(json.dumps({"check": "data_lineage", "status": "FAIL",
                          "message": "; ".join(errors),
                          "detail": {"errors": errors, "lineage": lineage}}))
        sys.exit(1)

    print(json.dumps({"check": "data_lineage", "status": "PASS",
                      "detail": {"train_end": train_end, "oos_start": oos_start}}))

if __name__ == "__main__":
    main()
