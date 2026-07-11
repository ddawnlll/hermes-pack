#!/usr/bin/env python3
"""
calibration-channel.py — Affect/calibration channel (#67)

Tracks probabilistic predictions and Brier score.
Rewards calibration, not agreement.
Affect values modulate bounded parameters only.
Affect never directly authorizes merge, reject, spending, or belief mutation.
Hard min/max bounds for every modulated parameter.

Commands:
  record-prediction <state_file> <prediction_id> <confidence> <outcome>
      — Record a probabilistic prediction (confidence 0.0-1.0, outcome True/False)
  brier-score <state_file>
      — Calculate current Brier score
  affect <state_file> [--frustration=0.0] [--confidence=0.5] [--boredom=0.0]
      — Set affect values within hard bounds, return modulated parameters
  report <state_file>
      — Show calibration report

Feature flag: affect_modulation
Default: disabled

Hard bounds:
  frustration: [0.0, 1.0] -> modulates sampling_temperature [0.5, 1.5]
  confidence:  [0.0, 1.0] -> modulates min_evidence_threshold [1, 10]
  boredom:     [0.0, 1.0] -> modulates novelty_bonus [0.0, 0.5]
"""

import json
import math
import os
import sys
from datetime import datetime


def get_ts():
    return datetime.utcnow().isoformat() + "Z"


# ── Hard bounds for affected parameters ─────────────────────────────────────
AFFECT_BOUNDS = {
    "frustration": {"min": 0.0, "max": 1.0, "default": 0.0},
    "confidence": {"min": 0.0, "max": 1.0, "default": 0.5},
    "boredom": {"min": 0.0, "max": 1.0, "default": 0.0},
}

# Parameter modulation tables: affect value -> modulated parameter
MODULATION = {
    "frustration": {
        "param": "sampling_temperature",
        "min_out": 0.5,
        "max_out": 1.5,
        "default_out": 0.8,
    },
    "confidence": {
        "param": "min_evidence_threshold",
        "min_out": 1,
        "max_out": 10,
        "default_out": 3,
    },
    "boredom": {
        "param": "novelty_bonus",
        "min_out": 0.0,
        "max_out": 0.5,
        "default_out": 0.0,
    },
}


def load_state(state_file):
    with open(state_file) as f:
        return json.load(f)


def save_state(state_file, state):
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def record_prediction(state_file, prediction_id, confidence, outcome):
    """Record a probabilistic prediction. Rewards calibration, not agreement."""
    confidence = max(0.0, min(1.0, float(confidence)))
    outcome = bool(outcome)

    state = load_state(state_file)

    cal = state.get("calibration", {})
    predictions = cal.get("predictions", [])

    predictions.append({
        "prediction_id": prediction_id,
        "confidence": confidence,
        "outcome": outcome,
        "timestamp": get_ts(),
    })

    cal["predictions_total"] = len(predictions)
    state["calibration"] = cal
    save_state(state_file, state)

    # Brier score contribution
    brier_contrib = (confidence - (1.0 if outcome else 0.0)) ** 2
    return {
        "status": "recorded",
        "prediction_id": prediction_id,
        "brier_contribution": round(brier_contrib, 6),
        "total_predictions": len(predictions),
    }


def brier_score(state_file):
    """Calculate Brier score (0=perfect, 1=worst). Rewards calibration, not agreement."""
    state = load_state(state_file)
    cal = state.get("calibration", {})
    predictions = cal.get("predictions", [])

    if not predictions:
        return {"brier_score": None, "total": 0, "note": "No predictions recorded"}

    total = 0
    for p in predictions:
        conf = max(0.0, min(1.0, float(p.get("confidence", 0.5))))
        outcome = 1.0 if p.get("outcome", False) else 0.0
        total += (conf - outcome) ** 2

    score = total / len(predictions)

    # Update calibration curve (binned)
    bins = {}
    for p in predictions:
        conf = int(float(p.get("confidence", 0.5)) * 10)  # 0-9
        outcome = p.get("outcome", False)
        if conf not in bins:
            bins[conf] = {"count": 0, "correct": 0}
        bins[conf]["count"] += 1
        if outcome:
            bins[conf]["correct"] += 1

    curve = []
    for bin_idx in sorted(bins.keys()):
        b = bins[bin_idx]
        acc = b["correct"] / b["count"] if b["count"] > 0 else 0
        curve.append({"bin": bin_idx, "count": b["count"], "accuracy": round(acc, 4)})

    # Save to state
    cal = state.get("calibration", {})
    cal["brier_score"] = round(score, 6)
    cal["calibration_curve"] = curve
    cal["predictions_total"] = len(predictions)
    state["calibration"] = cal
    save_state(state_file, state)

    return {
        "brier_score": round(score, 6),
        "total_predictions": len(predictions),
        "calibration_curve": curve,
    }


def affect(state_file, frustration=None, confidence=None, boredom=None):
    """Set affect values within hard bounds. Returns modulated parameters."""
    state = load_state(state_file)
    affect_data = state.get("affect", {})

    modulated = {}
    for affect_name, bounds in AFFECT_BOUNDS.items():
        value = locals().get(affect_name)
        if value is not None:
            value = max(bounds["min"], min(bounds["max"], float(value)))
        else:
            value = affect_data.get(affect_name, bounds["default"])

        affect_data[affect_name] = value

        # Calculate modulated parameter
        mod = MODULATION[affect_name]
        # Linear interpolation: affect_value -> modulated param
        range_in = bounds["max"] - bounds["min"]
        range_out = mod["max_out"] - mod["min_out"]
        if range_in > 0:
            ratio = (value - bounds["min"]) / range_in
        else:
            ratio = 0
        param_value = mod["min_out"] + ratio * range_out
        param_value = max(mod["min_out"], min(mod["max_out"], param_value))

        if mod["param"] == "min_evidence_threshold":
            param_value = int(round(param_value))

        modulated[mod["param"]] = {
            "value": param_value,
            "affect_source": affect_name,
            "affect_value": value,
            "bounds": [mod["min_out"], mod["max_out"]],
        }

    state["affect"] = affect_data
    save_state(state_file, state)

    return {
        "affect": affect_data,
        "modulated_parameters": modulated,
        "note": "Affect modulates bounded parameters only. "
                "Affect NEVER directly authorizes merge, reject, spending, or belief mutation.",
    }


def report(state_file):
    """Show calibration report."""
    state = load_state(state_file)
    cal = state.get("calibration", {})
    affect_data = state.get("affect", {})

    return {
        "calibration": {
            "brier_score": cal.get("brier_score"),
            "total_predictions": cal.get("predictions_total", 0),
            "curve": cal.get("calibration_curve", []),
        },
        "affect": affect_data,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "record-prediction":
        if len(sys.argv) < 5:
            print("Usage: calibration-channel.py record-prediction <state_file> <prediction_id> <confidence> <outcome>")
            sys.exit(1)
        result = record_prediction(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        print(json.dumps(result, indent=2))

    elif cmd == "brier-score":
        if len(sys.argv) < 3:
            print("Usage: calibration-channel.py brier-score <state_file>")
            sys.exit(1)
        result = brier_score(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "affect":
        if len(sys.argv) < 3:
            print("Usage: calibration-channel.py affect <state_file> [--frustration=N] [--confidence=N] [--boredom=N]")
            sys.exit(1)
        sf = sys.argv[2]
        kwargs = {}
        for a in sys.argv[3:]:
            if a.startswith("--frustration="):
                kwargs["frustration"] = float(a.split("=", 1)[1])
            elif a.startswith("--confidence="):
                kwargs["confidence"] = float(a.split("=", 1)[1])
            elif a.startswith("--boredom="):
                kwargs["boredom"] = float(a.split("=", 1)[1])
        result = affect(sf, **kwargs)
        print(json.dumps(result, indent=2))

    elif cmd == "report":
        result = report(sys.argv[2] if len(sys.argv) > 2 else ".")
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
