#!/usr/bin/env python3
"""
channel-budget.py — Centralized channel budget enforcement (#70, #65-#68)

Atomic, daily-resetting, idempotent budget accounting.
"""

import json, math, os, subprocess, sys, time, uuid
from datetime import datetime

FLAG_MAP = {"reflector":"reflector","analogy":"analogy_channel","dream":"dream_channel",
            "whisper":"whisper_channel","calibration":"affect_modulation"}
DEFAULT_BUDGETS = {"reflector":0.5,"analogy":0.25,"dream":0.15,"whisper":0.1,"calibration":0.2}

def _lk(state_file): return state_file + ".budget.lock"

def _acq(state_file, to=5):
    lf = _lk(state_file); dl = datetime.utcnow().timestamp() + to
    while True:
        try:
            fd = os.open(lf, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode()); os.close(fd); return True
        except FileExistsError:
            if datetime.utcnow().timestamp() > dl:
                try:
                    if datetime.utcnow().timestamp() - os.path.getmtime(lf) > 10: os.unlink(lf); continue
                except: pass
                return False
            time.sleep(0.1)

def _rel(state_file):
    try: os.unlink(_lk(state_file))
    except: pass

def _is_disabled(state, ch):
    flag = FLAG_MAP.get(ch)
    if not flag: return True, f"Unknown {ch}"
    v = state.get("features", {}).get(flag)
    if ch == "reflector":
        return (True, "reflector=disabled") if v == "disabled" else (False, "")
    return (True, f"{flag}={v}") if (v is False or v == "disabled") else (False, "")

def _daily_reset(state):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if state.get("channel_spend_date") != today:
        state["channel_spend_date"] = today
        for k in state.get("channel_spend_today", {}): state["channel_spend_today"][k] = 0
    return state

def _atomic_write(path, data):
    tmp = path + ".tmp." + uuid.uuid4().hex[:8]
    with open(tmp, "w") as f: json.dump(data, f, indent=2)
    os.rename(tmp, path)

def can_run(state_file, channel, estimated=0):
    if not os.path.exists(state_file): return {"allowed": False, "reason": "state_file not found"}
    with open(state_file) as f: state = json.load(f)
    d, r = _is_disabled(state, channel)
    if d: return {"allowed": False, "reason": r}
    state = _daily_reset(state)
    daily = state.get("channel_budgets", {}).get(channel, DEFAULT_BUDGETS.get(channel, 0))
    spent = state.get("channel_spend_today", {}).get(channel, 0)
    remaining = round(daily - spent, 4)
    if remaining <= 0: return {"allowed": False, "reason": f"Exhausted {spent}/{daily}"}
    if estimated > remaining: return {"allowed": False, "reason": f"Est ${estimated} > ${remaining}"}
    return {"allowed": True, "budget": daily, "spent": spent, "remaining": remaining}

def spend(state_file, journal_dir, channel, amount, operation_key):
    try: amt = float(amount)
    except: return {"error": f"Invalid amount '{amount}'"}
    if amt < 0 or not math.isfinite(amt): return {"error": f"Bad amount: {amount}"}

    # Load state + dedup check
    with open(state_file) as f: state = json.load(f)
    state = _daily_reset(state)
    spent_keys = state.get("spent_operation_keys", {})
    if operation_key in spent_keys:
        return {"status": "already_applied", "operation_key": operation_key, "amount": amt}

    # Locked transaction
    if not _acq(state_file): return {"error": "Could not acquire budget lock"}
    try:
        with open(state_file) as f: state = json.load(f)
        state = _daily_reset(state)
        d, r = _is_disabled(state, channel)
        if d: return {"error": f"Feature disabled: {r}"}
        daily = state.get("channel_budgets", {}).get(channel, DEFAULT_BUDGETS.get(channel, 0))
        st = state.get("channel_spend_today", {})
        cur = float(st.get(channel, 0))
        new_t = cur + amt
        if new_t > daily: return {"error": f"${amt} > ${round(daily-cur,4)} remaining"}
        # Atomic write
        spent_keys = state.get("spent_operation_keys", {})
        spent_keys[operation_key] = round(new_t, 4)
        st[channel] = round(new_t, 4)
        state["spent_operation_keys"] = spent_keys
        state["channel_spend_today"] = st
        _atomic_write(state_file, state)
    finally:
        _rel(state_file)

    # Journal commit (after unlock — acceptable because state is already committed)
    if journal_dir:
        tj = os.path.join(os.path.dirname(__file__), "tick-journal.py")
        if os.path.exists(tj):
            subprocess.run([sys.executable, tj, "start-phase", journal_dir, f"budget:{channel}"],
                           capture_output=True, timeout=10)
            subprocess.run([sys.executable, tj, "complete-phase", journal_dir, f"budget:{channel}", operation_key],
                           capture_output=True, timeout=10)

    return {"status": "recorded", "operation_key": operation_key, "amount": amt,
            "new_total": round(new_t, 4), "spent_budget": daily, "remaining": round(daily - new_t, 4)}

def cmd_status(state_file):
    with open(state_file) as f: state = json.load(f)
    state = _daily_reset(state)
    budgets = state.get("channel_budgets", {})
    st = state.get("channel_spend_today", {})
    feats = state.get("features", {})
    chs = {}
    for ch, flag in FLAG_MAP.items():
        d, _ = _is_disabled(state, ch)
        daily = budgets.get(ch, DEFAULT_BUDGETS.get(ch, 0))
        sp = st.get(ch, 0)
        chs[ch] = {"flag": flag, "val": feats.get(flag), "enabled": not d,
                    "daily": daily, "spent": sp, "remaining": round(daily - sp, 4)}
    return {"channels": chs, "spend_date": state.get("channel_spend_date"),
            "as_of": datetime.utcnow().strftime("%Y-%m-%d")}

if __name__ == "__main__":
    if len(sys.argv) < 3: print(__doc__, file=sys.stderr); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "can-run":
        sf, ch = sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""
        est = float(sys.argv[4]) if len(sys.argv) > 4 else 0
        r = can_run(sf, ch, est)
        print(json.dumps(r, indent=2)); sys.exit(0 if r.get("allowed") else 1)
    elif cmd == "spend":
        if len(sys.argv) < 7: print("Usage: ... spend <state> <journal> <ch> <amt> <opkey>"); sys.exit(1)
        r = spend(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
        print(json.dumps(r, indent=2)); sys.exit(1 if r.get("error") else 0)
    elif cmd == "status":
        r = cmd_status(sys.argv[2]); print(json.dumps(r, indent=2)); sys.exit(0)
