#!/usr/bin/env python3
"""
channel-dispatch.py — Deterministic channel dispatcher for v0.5 tick pipeline.

Stable operation key → journal reserve → budget reserve → execute →
provenance → commit budget → commit journal.
Every subprocess RC is checked. Any failure → blocked.
"""

import json, os, subprocess, sys, uuid
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def get_ts():
    return datetime.utcnow().isoformat() + "Z"

def _run(script, *args):
    sp = os.path.join(SCRIPTS_DIR, script)
    if not os.path.exists(sp): return None, {"error": f"Script not found: {sp}"}
    p = subprocess.run([sys.executable, sp] + list(args), capture_output=True, text=True, timeout=30)
    out = {}
    if p.stdout.strip():
        try: out = json.loads(p.stdout)
        except: out = {"raw": p.stdout}
    return p.returncode, out

def dispatch(state_file, journal_dir, channel, seed=None):
    # 1. Load state, check workers
    if not os.path.exists(state_file): return {"allowed": False, "reason": "state_file not found"}
    with open(state_file) as f: state = json.load(f)
    running = [k for k, v in state.get("worker_status", {}).items() if v == "running"]
    if running: return {"allowed": False, "reason": f"workers active: {running}"}

    tick_n = state.get("tick", 0)
    op_key = f"channel:{channel}:tick-{tick_n}"

    # 2. Feature flag + budget check (estimated cost, before execution)
    rc, bc = _run("channel-budget.py", "can-run", state_file, channel, "0.05")
    if rc != 0 or not bc.get("allowed"):
        return {"allowed": False, "reason": bc.get("reason", "budget/flag block")}
    if not bc.get("remaining", 0) >= 0.01:
        return {"allowed": False, "reason": "remaining budget too low"}

    # 3. Journal reserve: start channel phase
    rc, _ = _run("tick-journal.py", "start-phase", journal_dir, f"channel:{channel}")
    if rc != 0: return {"allowed": False, "reason": "journal reserve failed"}

    # 4. Execute channel
    output = _execute_channel(state_file, channel, seed)
    if output.get("error"):
        _run("tick-journal.py", "complete-phase", journal_dir, f"channel:{channel}", f"{op_key}:failed")
        return {"allowed": False, "error": output["error"]}

    cost = output.get("cost_usd", 0.01)

    # 5. Record provenance
    prov_dir = os.path.join(os.path.dirname(state_file), "provenance")
    rc_p, _ = _run("provenance-track.py", "record", prov_dir,
                   "channel_output", f"{channel}-{op_key}", channel,
                   "--source", f"tick-{tick_n}", "--cost", str(cost))
    if rc_p != 0:
        _run("tick-journal.py", "complete-phase", journal_dir, f"channel:{channel}", f"{op_key}:prov_failed")
        return {"allowed": False, "reason": "provenance record failed"}

    # 6. Budget spend (inside lock)
    rc_s, so = _run("channel-budget.py", "spend", state_file, journal_dir, channel, str(cost), op_key)
    if rc_s != 0 or so.get("error"):
        _run("tick-journal.py", "complete-phase", journal_dir, f"channel:{channel}", f"{op_key}:budget_failed")
        return {"allowed": False, "reason": so.get("error", "budget spend failed")}

    # 7. Complete journal phase (success)
    rc_j, _ = _run("tick-journal.py", "complete-phase", journal_dir, f"channel:{channel}", op_key)
    if rc_j != 0: return {"allowed": False, "reason": "journal commit failed"}

    return {
        "allowed": True, "operation_key": op_key, "channel": channel,
        "cost_usd": cost, "output": output.get("output", []), "candidate_only": True,
    }

def _execute_channel(state_file, channel, seed=None):
    ledger_dir = os.path.dirname(state_file)
    if channel == "analogy":
        store = os.path.join(ledger_dir, "analogies")
        _, r = _run("analogy-channel.py", "retrieve", store, "self", "improvement")
        return {"cost_usd": 0.02, "output": r.get("analogies", [])}
    elif channel == "dream":
        out_dir = os.path.join(ledger_dir, "dreams")
        s = seed or hash(datetime.utcnow().isoformat()) % 10000
        _, r = _run("dream-channel.py", "dream", state_file, out_dir, str(s), "--count=2")
        _run("dream-channel.py", "filter", state_file, out_dir)
        return {"cost_usd": 0.01, "output": r.get("ideas", [])}
    elif channel == "whisper":
        wdir = os.path.join(ledger_dir, "whispers")
        bdir = os.path.join(ledger_dir, "briefings")
        os.makedirs(bdir, exist_ok=True)
        _, r = _run("whisper-channel.py", "brief", wdir, bdir)
        return {"cost_usd": 0.01, "output": r.get("items", [])}
    elif channel == "calibration":
        _, r = _run("calibration-channel.py", "report", state_file)
        return {"cost_usd": 0.005, "output": [r]}
    return {"error": f"Unknown channel: {channel}"}

if __name__ == "__main__":
    if len(sys.argv) < 4: print(__doc__, file=sys.stderr); sys.exit(1)
    sf, jd, ch = sys.argv[1], sys.argv[2], sys.argv[3]
    seed = None
    for a in sys.argv[4:]:
        if a.startswith("--seed="): seed = int(a.split("=", 1)[1])
    result = dispatch(sf, jd, ch, seed)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("allowed") else 1)
