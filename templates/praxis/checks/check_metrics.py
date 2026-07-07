#!/usr/bin/env python3
"""
Praxis check: verify the worker's metrics pass sanity bounds.
Domain-agnostic validation of numeric metrics to catch obvious
hallucinations or impossible values.
"""
import json, sys, os

# Default sanity bounds (adapter can override)
DEFAULT_BOUNDS = {
    "sharpe": {"min": -5.0, "max": 15.0},
    "profit_factor": {"min": 0.0, "max": 100.0},
    "max_drawdown": {"min": 0.0, "max": 1.0},
    "oos_robustness": {"min": 0.0, "max": 5.0},
    "win_rate": {"min": 0.0, "max": 1.0},
    "total_trades": {"min": 0, "max": 100000},
}

def main():
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("EVIDENCE_BUNDLE", "")
    bounds_path = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("METRICS_BOUNDS", "")

    if not bundle_path or not os.path.exists(bundle_path):
        print(json.dumps({"check": "metrics_sanity", "status": "FAIL",
                          "message": f"Evidence bundle not found: {bundle_path}"}))
        sys.exit(1)

    with open(bundle_path) as f:
        bundle = json.load(f)

    metrics = bundle.get("metrics", {})
    if not metrics:
        print(json.dumps({"check": "metrics_sanity", "status": "WARN",
                          "message": "No metrics in evidence bundle"}))
        sys.exit(0)

    # Load custom bounds if provided
    bounds = DEFAULT_BOUNDS.copy()
    if bounds_path and os.path.exists(bounds_path):
        with open(bounds_path) as f:
            custom = json.load(f)
            bounds.update(custom)

    errors = []
    for key, value in metrics.items():
        if key in bounds:
            b = bounds[key]
            if not isinstance(value, (int, float)):
                continue
            if value < b["min"] or value > b["max"]:
                errors.append(f"metric '{key}' = {value} outside sane range [{b['min']}, {b['max']}]")

    if errors:
        print(json.dumps({"check": "metrics_sanity", "status": "FAIL",
                          "message": "; ".join(errors),
                          "detail": {"errors": errors, "metrics": metrics}}))
        sys.exit(1)

    print(json.dumps({"check": "metrics_sanity", "status": "PASS", "detail": {"metrics_checked": list(metrics.keys())}}))

if __name__ == "__main__":
    main()
