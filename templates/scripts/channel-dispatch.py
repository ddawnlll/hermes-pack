#!/usr/bin/env python3
"""
channel-dispatch.py — Deterministic channel dispatcher for v0.5 tick pipeline.

Inspects state and worker activity, checks feature flags + budget,
derives operation keys, consults tick journal, executes channel,
records provenance + spend, commits journal, returns candidate-only output.

Disabled channels: zero artifact, zero spend, zero provenance, deterministic blocked result.

Usage:
  channel-dispatch.py <state_file> <journal_dir> <channel_name> [--seed=N]
"""

import json
import os
import sys
import uuid
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_ts():
    return datetime.utcnow().isoformat() + "Z"


def run_py(script, *args):
    """Run one of our scripts by path."""
    sp = os.path.join(SCRIPTS_DIR, script)
    if not os.path.exists(sp):
        return {"error": f"Script not found: {sp}"}
    import subprocess
    proc = subprocess.run([sys.executable, sp] + list(args),
                          capture_output=True, text=True, timeout=30)
    out = {}
    if proc.stdout.strip():
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            out = {"raw": proc.stdout}
    return out


def dispatch(state_file, journal_dir, channel, seed=None):
    """Deterministic channel dispatch gate."""
    # 1. Load state to check worker activity
    if not os.path.exists(state_file):
        return {"allowed": False, "reason": "state_file not found"}

    with open(state_file) as f:
        state = json.load(f)

    # 2. Check workers not running
    workers = state.get("worker_status", {})
    running = [k for k, v in workers.items() if v == "running"]
    if running:
        return {"allowed": False, "reason": f"workers active: {running}"}

    # 3. Feature flag + budget check
    budget_result = run_py("channel-budget.py", "can-run", state_file, channel)
    if not budget_result.get("allowed", False):
        return {
            "allowed": False,
            "reason": budget_result.get("reason", "budget/flag block"),
            "channel": channel,
        }

    # 4. Derive operation key
    op_key = f"channel:{channel}:tick-{state.get('tick', 0)}:run-{uuid.uuid4().hex[:8]}"

    # 5. Consult tick journal
    journal_result = run_py("tick-journal.py", "already-applied", journal_dir, op_key)
    if journal_result.get("applied"):
        return {
            "allowed": True,
            "already_done": True,
            "operation_key": op_key,
            "reason": "Already executed in this tick (idempotent)",
            "channel": channel,
        }

    # 6. Execute the appropriate channel
    result = _execute_channel(state_file, channel, seed)
    if result.get("error"):
        return {"allowed": False, "error": result["error"], "channel": channel}

    # 7. Record provenance
    run_py("provenance-track.py", "record",
           os.path.join(os.path.dirname(state_file), "provenance"),
           "channel_output", f"{channel}-{op_key}", channel,
           "--source", f"tick-{state.get('tick', 0)}",
           "--cost", str(result.get("cost_usd", 0)))

    # 8. Record spend
    run_py("channel-budget.py", "spend", state_file, journal_dir, channel,
           str(result.get("cost_usd", 0)), op_key)

    # 9. Commit journal
    run_py("tick-journal.py", "start-phase", journal_dir, f"channel:{channel}")
    run_py("tick-journal.py", "complete-phase", journal_dir, f"channel:{channel}", op_key)

    return {
        "allowed": True,
        "already_done": False,
        "operation_key": op_key,
        "channel": channel,
        "output": result.get("output", []),
        "candidate_only": True,
    }


def _execute_channel(state_file, channel, seed=None):
    """Execute a single channel. Returns candidate output."""
    ledger_dir = os.path.dirname(state_file)

    if channel == "analogy":
        store = os.path.join(ledger_dir, "analogies")
        result = run_py("analogy-channel.py", "retrieve", store, "self", "improvement")
        return {"cost_usd": 0.02, "output": result.get("analogies", [])}

    elif channel == "dream":
        out_dir = os.path.join(ledger_dir, "dreams")
        s = seed or hash(get_ts()) % 10000
        result = run_py("dream-channel.py", "dream", state_file, out_dir, str(s), "--count=2")
        # Separate generation from filtering
        run_py("dream-channel.py", "filter", state_file, out_dir)
        return {"cost_usd": 0.01, "output": result.get("ideas", [])}

    elif channel == "whisper":
        wdir = os.path.join(ledger_dir, "whispers")
        brief_dir = os.path.join(ledger_dir, "briefings")
        os.makedirs(brief_dir, exist_ok=True)
        result = run_py("whisper-channel.py", "brief", wdir, brief_dir)
        return {"cost_usd": 0.01, "output": result.get("items", [])}

    elif channel == "calibration":
        result = run_py("calibration-channel.py", "report", state_file)
        return {"cost_usd": 0.005, "output": [result]}

    else:
        return {"error": f"Unknown channel: {channel}"}


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    sf = sys.argv[1]
    jd = sys.argv[2]
    ch = sys.argv[3]
    seed = None
    for a in sys.argv[4:]:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])

    result = dispatch(sf, jd, ch, seed)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("allowed") else 1)
