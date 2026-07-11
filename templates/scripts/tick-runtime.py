#!/usr/bin/env python3
"""
tick-runtime.py — Deterministic tick orchestration wrapper (#71)

Owns journal phase transitions, invokes deterministic gates.
ONLY resumes INTERRUPTED journals (not completed ones).
Corrupt journals → FAIL CLOSED.
Side effects + operation keys → journal-gated.
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
    return p.returncode, out

def _atomic_write(path, data):
    tmp = path + ".tmp." + uuid.uuid4().hex[:8]
    with open(tmp, "w") as f: json.dump(data, f, indent=2)
    os.rename(tmp, path)

def init_tick(state_file, journal_dir):
    os.makedirs(journal_dir, exist_ok=True)

    # Look for EXISTING journals
    existing = sorted([f for f in os.listdir(journal_dir) if f.endswith(".journal.json")], reverse=True)

    if existing:
        jf = os.path.join(journal_dir, existing[0])
        try:
            with open(jf) as f: j = json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"error": f"Cannot parse existing journal: {existing[0]}"}

        # Integrity check — fail closed if corrupt
        _, out = _tj("integrity", journal_dir)
        if out.get("integrity_ok") == False:
            return {"error": f"Journal integrity FAILED: {out.get('issues', 'unknown')}"}

        # Only resume if journal was INTERRUPTED (has running phase)
        phases = j.get("phases", [])
        running_phases = [p for p in phases if p.get("status") == "running" or p.get("status") == "crashed"]
        completed_phases = [p for p in phases if p.get("status") == "completed"]

        if not running_phases and completed_phases:
            # All phases completed — this is a DONE tick. Create NEW journal.
            tick_id = f"TICK-{uuid.uuid4().hex[:12].upper()}"
            _tj("init", journal_dir, tick_id)
            _, out2 = _tj("status", journal_dir)
            run_id = out2.get("run_id", tick_id)
            _tj("start-phase", journal_dir, "tick_start")
            with open(state_file) as f: state = json.load(f)
            state["tick"] = state.get("tick", 0) + 1
            state["run_id"] = run_id
            state["phase"] = "running"
            _atomic_write(state_file, state)
            return {"tick_id": tick_id, "run_id": run_id, "phase": "running", "recovered": False}

        # Has running phases — it's interrupted, recover it
        _, out2 = _tj("recover", journal_dir)
        run_id = out2.get("run_id") or j.get("run_id")
        _tj("start-phase", journal_dir, "tick_resume")
        with open(state_file) as f: state = json.load(f)
        state["tick"] = state.get("tick", 0) + 1
        state["run_id"] = run_id
        state["phase"] = "running"
        _atomic_write(state_file, state)
        return {"tick_id": j.get("tick_id"), "run_id": run_id, "phase": "running", "recovered": True}

    # No existing journal — create fresh
    tick_id = f"TICK-{uuid.uuid4().hex[:12].upper()}"
    _tj("init", journal_dir, tick_id)
    _, out = _tj("status", journal_dir)
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
    _, out = _tj("already-applied", journal_dir, op_key)
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

def commit_side_effect(state_file, journal_dir, kind, key, runner_func=None):
    """
    Generic journal-gated side effect commit.
    If runner_func is provided, it runs BEFORE commit (reservation pattern).
    If runner_func fails, commit is skipped.
    Both journal and side effect are in same function — caller must handle.
    """
    op_key = f"{kind}:{key}"
    _, out = _tj("already-applied", journal_dir, op_key)
    if out.get("applied"):
        return {"operation_key": op_key, "applied": True}

    # Run side effect first (reservation pattern)
    if runner_func:
        try:
            runner_func()
        except Exception as e:
            return {"error": f"Side effect failed: {e}", "operation_key": op_key}

    # Then commit operation key
    _tj("start-phase", journal_dir, f"{kind}:{key}")
    _tj("complete-phase", journal_dir, f"{kind}:{key}", op_key)
    return {"operation_key": op_key, "applied": False}

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
        if len(sys.argv) < 4: print("Usage: tick-runtime.py init <state> <journal_dir>"); sys.exit(1)
        r = init_tick(sys.argv[2], sys.argv[3])
    elif cmd == "can-dispatch":
        if len(sys.argv) < 5: print("Usage: tick-runtime.py can-dispatch <state> <journal_dir> <worker>"); sys.exit(1)
        r = can_dispatch(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "commit-dispatch":
        if len(sys.argv) < 6: print("Usage: tick-runtime.py commit-dispatch <state> <journal_dir> <worker> <op_key>"); sys.exit(1)
        r = commit_dispatch(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "commit-side-effect":
        if len(sys.argv) < 6: print("Usage: tick-runtime.py commit-side-effect <state> <journal_dir> <kind> <key>"); sys.exit(1)
        r = commit_side_effect(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "tick-end":
        if len(sys.argv) < 4: print("Usage: tick-runtime.py tick-end <state> <journal_dir>"); sys.exit(1)
        r = tick_end(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown: {cmd}", file=sys.stderr); sys.exit(1)
    print(json.dumps(r, indent=2))
    sys.exit(1 if r.get("error") else 0)
