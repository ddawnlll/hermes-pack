#!/usr/bin/env python3
"""
tick-runtime.py — Deterministic tick orchestration wrapper (#71)

Owns journal phase transitions, invokes deterministic gates.
Recovers existing interrupted journals — does NOT create new ones blindly.
"""

import json, os, sys, uuid, subprocess
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def _tj(*a):
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS_DIR, "tick-journal.py")] + list(a),
                       capture_output=True, text=True, timeout=15)
    out = {}
    if p.stdout.strip():
        try: out = json.loads(p.stdout)
        except: out = {"raw": p.stdout}
    return p.returncode, out, p.stderr

def _atomic_write(path, data):
    tmp = path + ".tmp." + uuid.uuid4().hex[:8]
    with open(tmp, "w") as f: json.dump(data, f, indent=2)
    os.rename(tmp, path)

def init_tick(state_file, journal_dir):
    """Initialize or RECOVER existing tick journal."""
    os.makedirs(journal_dir, exist_ok=True)

    # Look for EXISTING journals first
    existing = [f for f in os.listdir(journal_dir) if f.endswith(".journal.json")]
    existing.sort(reverse=True)

    tick_id = None
    if existing:
        # Load latest existing journal — recover it
        latest_jf = os.path.join(journal_dir, existing[0])
        try:
            with open(latest_jf) as f: j = json.load(f)
            tick_id = j.get("tick_id")
            if tick_id:
                rc, out, _ = _tj("integrity", journal_dir)
                if out.get("integrity_ok") == False:
                    pass  # log but try recovery anyway
                rc2, out2, _ = _tj("recover", journal_dir)
                # Continue with existing journal
                run_id = out2.get("run_id") or j.get("run_id")
                _tj("start-phase", journal_dir, "tick_resume")
                with open(state_file) as f: state = json.load(f)
                state["tick"] = state.get("tick", 0) + 1
                state["run_id"] = run_id
                state["phase"] = "running"
                _atomic_write(state_file, state)
                return {"tick_id": tick_id, "run_id": run_id, "phase": "running", "recovered": True}
        except (json.JSONDecodeError, IOError):
            pass  # Corrupted journal — create new

    # No existing journal — create fresh
    tick_id = f"TICK-{uuid.uuid4().hex[:12].upper()}"
    rc, out, _ = _tj("init", journal_dir, tick_id)
    run_id = out.get("run_id", tick_id)
    _tj("start-phase", journal_dir, "tick_start")
    with open(state_file) as f: state = json.load(f)
    state["tick"] = state.get("tick", 0) + 1
    state["run_id"] = run_id
    state["phase"] = "running"
    _atomic_write(state_file, state)
    return {"tick_id": tick_id, "run_id": run_id, "phase": "running", "recovered": False}

def can_dispatch(state_file, journal_dir, worker_id):
    op_key = f"dispatch:{worker_id}"
    _, out, _ = _tj("already-applied", journal_dir, op_key)
    if out.get("applied"):
        return {"can_dispatch": False, "reason": "Already dispatched", "operation_key": op_key}
    return {"can_dispatch": True, "operation_key": op_key}

def commit_dispatch(state_file, journal_dir, worker_id, operation_key):
    _tj("start-phase", journal_dir, f"dispatch:{worker_id}")
    _tj("complete-phase", journal_dir, f"dispatch:{worker_id}", operation_key)
    with open(state_file) as f: state = json.load(f)
    state["phase"] = "dispatch"
    _atomic_write(state_file, state)
    return {"committed": True, "operation_key": operation_key}

def commit_blame(state_file, journal_dir, blame_key):
    op_key = f"blame:{blame_key}"
    _, out, _ = _tj("already-applied", journal_dir, op_key)
    if not out.get("applied"):
        _tj("start-phase", journal_dir, f"blame:{blame_key}")
        _tj("complete-phase", journal_dir, f"blame:{blame_key}", op_key)
    return {"operation_key": op_key}

def commit_merge(state_file, journal_dir, merge_key):
    op_key = f"merge:{merge_key}"
    _, out, _ = _tj("already-applied", journal_dir, op_key)
    if not out.get("applied"):
        _tj("start-phase", journal_dir, f"merge:{merge_key}")
        _tj("complete-phase", journal_dir, f"merge:{merge_key}", op_key)
    return {"operation_key": op_key}

def commit_provenance(state_file, journal_dir, prov_key):
    op_key = f"provenance:{prov_key}"
    _, out, _ = _tj("already-applied", journal_dir, op_key)
    if not out.get("applied"):
        _tj("start-phase", journal_dir, f"prov:{prov_key}")
        _tj("complete-phase", journal_dir, f"prov:{prov_key}", op_key)
    return {"operation_key": op_key}

def commit_channel(state_file, journal_dir, channel):
    op_key = f"channel:{channel}:tick-{_get_tick(state_file)}"
    _, out, _ = _tj("already-applied", journal_dir, op_key)
    if not out.get("applied"):
        _tj("start-phase", journal_dir, f"channel:{channel}")
        _tj("complete-phase", journal_dir, f"channel:{channel}", op_key)
    return {"operation_key": op_key}

def _get_tick(state_file):
    try:
        with open(state_file) as f: return json.load(f).get("tick", 0)
    except: return 0

def tick_end(state_file, journal_dir):
    _tj("start-phase", journal_dir, "tick_end")
    _tj("complete-phase", journal_dir, "tick_end")
    with open(state_file) as f: state = json.load(f)
    state["phase"] = "idle"
    _atomic_write(state_file, state)
    return {"phase": "idle"}

if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__, file=sys.stderr); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "init":
        if len(sys.argv) < 4: print("Usage: tick-runtime.py init <state_file> <journal_dir>"); sys.exit(1)
        r = init_tick(sys.argv[2], sys.argv[3])
    elif cmd == "can-dispatch":
        if len(sys.argv) < 5: print("Usage: tick-runtime.py can-dispatch <state> <journal_dir> <worker_id>"); sys.exit(1)
        r = can_dispatch(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "commit-dispatch":
        if len(sys.argv) < 6: print("Usage: tick-runtime.py commit-dispatch <state> <journal_dir> <worker_id> <op_key>"); sys.exit(1)
        r = commit_dispatch(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "commit-blame":
        if len(sys.argv) < 4: print("Usage: tick-runtime.py commit-blame <state> <journal_dir> <blame_key>"); sys.exit(1)
        r = commit_blame(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "commit-merge":
        if len(sys.argv) < 4: print("Usage: tick-runtime.py commit-merge <state> <journal_dir> <merge_key>"); sys.exit(1)
        r = commit_merge(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "commit-provenance":
        if len(sys.argv) < 4: print("Usage: tick-runtime.py commit-provenance <state> <journal_dir> <prov_key>"); sys.exit(1)
        r = commit_provenance(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "commit-channel":
        if len(sys.argv) < 5: print("Usage: tick-runtime.py commit-channel <state> <journal_dir> <channel>"); sys.exit(1)
        r = commit_channel(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "tick-end":
        if len(sys.argv) < 4: print("Usage: tick-runtime.py tick-end <state_file> <journal_dir>"); sys.exit(1)
        r = tick_end(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown: {cmd}", file=sys.stderr); sys.exit(1)
    print(json.dumps(r, indent=2))
    sys.exit(1 if r.get("error") else 0)
