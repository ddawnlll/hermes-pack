#!/usr/bin/env python3
"""
Issue #30 — Curiosity Budget: Protected Discovery Budget
Minimum 20% of total budget_usd is reserved as curiosity_budget_usd.
ROI gate (#29) and self-grade gate (#28) CANNOT touch this slice.
Explorer (#25) consumes from this budget primarily.

Adaptive growth: can grow above 20% based on Explorer hit rate,
but NEVER drops below 20%.
"""
import json, os, sys

MIN_CURIOSITY_RATIO = 0.20  # 20% floor
MAX_CURIOSITY_RATIO = 0.50  # 50% ceiling (adaptive growth limit)
DEFAULT_BUDGET_USD = 25.0


def compute_curiosity_budget(budget_usd, explorer_hit_rate=0.0):
    """
    Compute curiosity budget from total budget.
    
    Base: 20% of total.
    Adaptive: if explorer_hit_rate > 0 (hits/total), can grow up to 50%.
    Formula: min(0.20 + 0.30 * hit_rate, 0.50)
    
    Args:
        budget_usd: total daily budget
        explorer_hit_rate: 0.0 to 1.0, Explorer's recent hit rate
    
    Returns:
        dict with curiosity_usd, ratio, base_ratio, adaptive_boost
    """
    if budget_usd <= 0:
        return {
            "curiosity_usd": 0.0,
            "ratio": 0.0,
            "base_ratio": MIN_CURIOSITY_RATIO,
            "adaptive_boost": 0.0,
        }

    # Clamp hit rate
    hit_rate = max(0.0, min(1.0, explorer_hit_rate))

    # Adaptive ratio: base 20% + up to 30% bonus based on hit rate
    adaptive_boost = min(MAX_CURIOSITY_RATIO - MIN_CURIOSITY_RATIO, 0.30 * hit_rate)
    ratio = min(MIN_CURIOSITY_RATIO + adaptive_boost, MAX_CURIOSITY_RATIO)

    curiosity_usd = round(budget_usd * ratio, 4)

    return {
        "curiosity_usd": curiosity_usd,
        "ratio": ratio,
        "base_ratio": MIN_CURIOSITY_RATIO,
        "adaptive_boost": adaptive_boost,
    }


def update_state_curiosity_budget(state_path):
    """
    Update state.json with curiosity_budget_usd.
    Reads budget_usd and optional explorer_hit_rate from state.
    """
    if not os.path.exists(state_path):
        return {"error": "state.json not found"}

    with open(state_path) as f:
        state = json.load(f)

    budget_usd = state.get("budget_usd", DEFAULT_BUDGET_USD)
    explorer_hit_rate = state.get("explorer_hit_rate", 0.0)

    result = compute_curiosity_budget(budget_usd, explorer_hit_rate)
    state["curiosity_budget_usd"] = result["curiosity_usd"]
    state["curiosity_ratio"] = result["ratio"]

    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    return result


def validate_curiosity_budget_in_schema(schema_path):
    """Check that state.schema.json includes curiosity_budget_usd."""
    if not os.path.exists(schema_path):
        return False, "schema file not found"
    with open(schema_path) as f:
        schema = json.load(f)
    props = schema.get("properties", {})
    if "curiosity_budget_usd" in props:
        return True, "curiosity_budget_usd found in schema"
    return False, "curiosity_budget_usd missing from schema"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: curiosity-budget.py <command> [args]", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  compute <budget_usd> [hit_rate]   Compute curiosity budget", file=sys.stderr)
        print("  update <state_path>                Update state.json", file=sys.stderr)
        print("  validate <schema_path>             Validate schema", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "compute":
        budget = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BUDGET_USD
        rate = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
        print(json.dumps(compute_curiosity_budget(budget, rate), indent=2))
    elif cmd == "update":
        path = sys.argv[2] if len(sys.argv) > 2 else "state.json"
        print(json.dumps(update_state_curiosity_budget(path), indent=2))
    elif cmd == "validate":
        path = sys.argv[2] if len(sys.argv) > 2 else "schema/state.schema.json"
        ok, msg = validate_curiosity_budget_in_schema(path)
        print(json.dumps({"valid": ok, "message": msg}))
        sys.exit(0 if ok else 1)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
