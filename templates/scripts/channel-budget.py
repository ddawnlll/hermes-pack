#!/usr/bin/env python3
"""
channel-budget.py — Centralized channel budget enforcement (#70, #65-#68)

Checks feature flags and daily budgets before any channel executes.
Disabled channels spend ZERO and produce ZERO artifacts.

Commands:
  can-run <state_file> <channel_name>
      — Check if a channel may run (flag enabled + budget remaining).
      Returns {allowed: bool, reason: str, budget_remaining: float}
  spend <state_file> <channel_name> <amount>
      — Record channel spend. Updates channel_spend_today.
      Fails if would exceed daily budget.
  status <state_file>
      — Show all channel budgets and remaining spend capacity.

Channel budgets defined in state.channel_budgets (defaults):
  reflector: 0.50, analogy: 0.25, dream: 0.15,
  whisper: 0.10, calibration: 0.20
"""

import json
import os
import sys
from datetime import datetime, date


FLAG_MAP = {
    "reflector": "reflector",
    "analogy": "analogy_channel",
    "dream": "dream_channel",
    "whisper": "whisper_channel",
    "calibration": "affect_modulation",
}

# Channels are disabled if their feature flag is False or "disabled"
# exception: reflector="shadow" is allowed (not disabled)
def _is_disabled(state, channel):
    flag = FLAG_MAP.get(channel)
    if not flag:
        return True, f"Unknown channel '{channel}'"
    features = state.get("features", {})
    val = features.get(flag)
    if channel == "reflector":
        if val == "disabled":
            return True, "reflector=disabled"
        return False, ""  # shadow or active = allowed
    if val is False or val == "disabled":
        return True, f"{flag}={val}"
    return False, ""


def can_run(state_file, channel):
    """Check if channel may run today."""
    if not os.path.exists(state_file):
        return {"allowed": False, "reason": "state_file not found"}

    with open(state_file) as f:
        state = json.load(f)

    # Feature flag check
    disabled, reason = _is_disabled(state, channel)
    if disabled:
        return {"allowed": False, "reason": reason, "channel": channel}

    # Budget check
    budgets = state.get("channel_budgets", {})
    daily_budget = budgets.get(channel, 0)
    if daily_budget <= 0:
        return {"allowed": False, "reason": f"channel_budgets.{channel}=0 (no budget allocated)"}

    spend_today = state.get("channel_spend_today", {}).get(channel, 0)
    remaining = daily_budget - spend_today

    if remaining <= 0:
        return {
            "allowed": False,
            "reason": f"Daily budget exhausted for '{channel}' "
                      f"(budget={daily_budget}, spent={spend_today})",
            "budget": daily_budget,
            "spent": spend_today,
            "remaining": remaining,
        }

    return {
        "allowed": True,
        "reason": "Feature enabled + budget available",
        "budget": daily_budget,
        "spent": spend_today,
        "remaining": round(remaining, 4),
        "channel": channel,
    }


def spend(state_file, channel, amount):
    """Record channel spend. Fail-closed if budget would be exceeded."""
    if not os.path.exists(state_file):
        return {"error": "state_file not found"}

    with open(state_file) as f:
        state = json.load(f)

    budgets = state.get("channel_budgets", {})
    daily_budget = budgets.get(channel, 0)
    spend_today = state.get("channel_spend_today", {})
    current = spend_today.get(channel, 0)
    new_total = current + float(amount)

    if new_total > daily_budget:
        return {
            "error": f"Spend ${amount} would exceed daily budget ${daily_budget} for '{channel}' "
                     f"(already spent ${current})",
            "allowed": False,
        }

    # Atomic update
    spend_today[channel] = round(new_total, 4)
    state["channel_spend_today"] = spend_today

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    return {
        "status": "recorded",
        "channel": channel,
        "amount": float(amount),
        "new_total": round(new_total, 4),
        "budget": daily_budget,
        "remaining": round(daily_budget - new_total, 4),
    }


def status(state_file):
    """Show all channel budgets and remaining spend."""
    if not os.path.exists(state_file):
        return {"error": "state_file not found"}

    with open(state_file) as f:
        state = json.load(f)

    budgets = state.get("channel_budgets", {})
    spend_today = state.get("channel_spend_today", {})
    features = state.get("features", {})

    channels = {}
    for ch, flag in FLAG_MAP.items():
        flag_val = features.get(flag)
        is_disabled, reason = _is_disabled(state, ch)
        daily = budgets.get(ch, 0)
        spent = spend_today.get(ch, 0)
        remaining = round(daily - spent, 4)
        channels[ch] = {
            "feature_flag": flag,
            "flag_value": flag_val,
            "enabled": not is_disabled,
            "daily_budget": daily,
            "spent_today": spent,
            "remaining_today": remaining,
        }

    return {"channels": channels, "as_of": str(date.today())}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "can-run":
        if len(sys.argv) < 4:
            print("Usage: channel-budget.py can-run <state_file> <channel>")
            sys.exit(1)
        result = can_run(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("allowed") else 1)

    elif cmd == "spend":
        if len(sys.argv) < 5:
            print("Usage: channel-budget.py spend <state_file> <channel> <amount>")
            sys.exit(1)
        result = spend(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps(result, indent=2))
        sys.exit(1 if result.get("error") else 0)

    elif cmd == "status":
        result = status(sys.argv[2])
        print(json.dumps(result, indent=2))
        sys.exit(0)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
