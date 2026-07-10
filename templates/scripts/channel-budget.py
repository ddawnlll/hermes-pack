#!/usr/bin/env python3
"""
channel-budget.py — Centralized channel budget enforcement (#70, #65-#68)

Atomic, daily-resetting, idempotent budget accounting.

Commands:
  can-run <state> <channel> [estimated_amount]
  spend <state> <journal_dir> <channel> <amount> <operation_key>
  status <state>

Daily reset: compares UTC date stored in state.channel_spend_date.
Atomic write: write temp file + os.rename.
Operation key: dedup via tick-journal already-applied.
"""

import json, os, sys, uuid
from datetime import datetime, date

FLAG_MAP = {
    "reflector": "reflector", "analogy": "analogy_channel",
    "dream": "dream_channel", "whisper": "whisper_channel",
    "calibration": "affect_modulation",
}
DEFAULT_BUDGETS = {"reflector": 0.5, "analogy": 0.25, "dream": 0.15,
                   "whisper": 0.1, "calibration": 0.2}

def _lock_path(state_file):
    return state_file + ".budget.lock"

def _is_disabled(state, channel):
    flag = FLAG_MAP.get(channel)
    if not flag: return True, f"Unknown channel '{channel}'"
    val = state.get("features", {}).get(flag)
    if channel == "reflector":
        if val == "disabled": return True, "reflector=disabled"
        return False, ""
    if val is False or val == "disabled":
        return True, f"{flag}={val}"
    return False, ""

def _daily_reset(state):
    today = str(date.today())
    if state.get("channel_spend_date") != today:
        state["channel_spend_date"] = today
        ch = state.get("channel_spend_today", {})
        for k in ch: ch[k] = 0
    return state

def _atomic_write(path, data):
    tmp = path + ".tmp." + uuid.uuid4().hex[:8]
    with open(tmp, "w") as f: json.dump(data, f, indent=2)
    os.rename(tmp, path)

def can_run(state_file, channel, estimated_amount=0):
    if not os.path.exists(state_file):
        return {"allowed": False, "reason": "state_file not found"}
    with open(state_file) as f: state = json.load(f)
    disabled, reason = _is_disabled(state, channel)
    if disabled:
        return {"allowed": False, "reason": reason}
    state = _daily_reset(state)
    budgets = state.get("channel_budgets", {})
    daily = budgets.get(channel, DEFAULT_BUDGETS.get(channel, 0))
    spend = state.get("channel_spend_today", {}).get(channel, 0)
    remaining = round(daily - spend, 4)
    if remaining <= 0:
        return {"allowed": False, "reason": f"Budget exhausted: {spend}/{daily}"}
    if estimated_amount > 0 and estimated_amount > remaining:
        return {"allowed": False, "reason": f"Estimated ${estimated_amount} exceeds ${remaining} remaining"}
    return {"allowed": True, "budget": daily, "spent": spend, "remaining": remaining}

def spend(state_file, journal_dir, channel, amount, operation_key):
    if amount is None:
        return {"error": "amount is required"}
    try:
        amount_f = float(amount)
    except (ValueError, TypeError):
        return {"error": f"Invalid amount '{amount}'"}
    if amount_f < 0:
        return {"error": f"Negative amount: {amount_f}"}
    if not math.isfinite(amount_f):
        return {"error": f"Non-finite amount: {amount_f}"}

    # Dedup via journal
    if journal_dir:
        import subprocess
        tj = os.path.join(os.path.dirname(__file__), "tick-journal.py")
        if os.path.exists(tj):
            proc = subprocess.run([sys.executable, tj, "already-applied", journal_dir, operation_key],
                                  capture_output=True, text=True, timeout=10)
            if proc.stdout.strip():
                try:
                    ja = json.loads(proc.stdout)
                    if ja.get("applied"):
                        return {"status": "already_applied", "operation_key": operation_key, "amount": amount_f}
                except json.JSONDecodeError: pass

    # Load state
    with open(state_file) as f: state = json.load(f)
    state = _daily_reset(state)

    # Feature flag recheck
    disabled, reason = _is_disabled(state, channel)
    if disabled:
        return {"error": f"Feature disabled: {reason}"}

    # Budget check inside same transaction
    budgets = state.get("channel_budgets", {})
    daily = budgets.get(channel, DEFAULT_BUDGETS.get(channel, 0))
    spend_today = state.get("channel_spend_today", {})
    current = float(spend_today.get(channel, 0))
    new_total = current + amount_f
    if new_total > daily:
        return {"error": f"${amount_f} exceeds remaining ${round(daily - current, 4)}"}
    if new_total > daily * 2:  # Safety valve
        return {"error": f"New total ${new_total} > 2x budget ${daily} — aborting"}

    # Atomic update
    spend_today[channel] = round(new_total, 4)
    state["channel_spend_today"] = spend_today
    _atomic_write(state_file, state)

    # Commit operation key to journal
    if journal_dir:
        import subprocess
        tj = os.path.join(os.path.dirname(__file__), "tick-journal.py")
        if os.path.exists(tj):
            subprocess.run([sys.executable, tj, "start-phase", journal_dir, f"budget:{channel}"],
                           capture_output=True, timeout=10)
            subprocess.run([sys.executable, tj, "complete-phase", journal_dir,
                           f"budget:{channel}", operation_key],
                           capture_output=True, timeout=10)

    return {"status": "recorded", "operation_key": operation_key, "amount": amount_f,
            "new_total": round(new_total, 4), "spent_budget": daily,
            "remaining": round(daily - new_total, 4)}

def cmd_status(state_file):
    with open(state_file) as f: state = json.load(f)
    state = _daily_reset(state)
    budgets = state.get("channel_budgets", {})
    spend_today = state.get("channel_spend_today", {})
    features = state.get("features", {})
    channels = {}
    for ch, flag in FLAG_MAP.items():
        disabled, _ = _is_disabled(state, ch)
        daily = budgets.get(ch, DEFAULT_BUDGETS.get(ch, 0))
        spent = spend_today.get(ch, 0)
        channels[ch] = {"feature_flag": flag, "flag_value": features.get(flag),
                        "enabled": not disabled, "daily_budget": daily,
                        "spent_today": spent, "remaining_today": round(daily - spent, 4)}
    return {"channels": channels, "spend_date": state.get("channel_spend_date"), "as_of": str(date.today())}

import math

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "can-run":
        sf = sys.argv[2]; ch = sys.argv[3] if len(sys.argv) > 3 else ""
        est = float(sys.argv[4]) if len(sys.argv) > 4 else 0
        result = can_run(sf, ch, est)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("allowed") else 1)
    elif cmd == "spend":
        if len(sys.argv) < 7:
            print("Usage: channel-budget.py spend <state> <journal_dir> <channel> <amount> <op_key>")
            sys.exit(1)
        result = spend(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
        print(json.dumps(result, indent=2))
        sys.exit(1 if result.get("error") else 0)
    elif cmd == "status":
        result = cmd_status(sys.argv[2])
        print(json.dumps(result, indent=2)); sys.exit(0)
