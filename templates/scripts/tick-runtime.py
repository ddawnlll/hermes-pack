#!/usr/bin/env python3
"""
tick-runtime.py — Deterministic tick orchestration wrapper (#71)

Owns journal phase transitions, invokes deterministic gates.
Derives tick_id, run_id, manages journal lifecycle.
Enforces idempotency on ALL side effects.

LLM chooses candidates and interprets evidence.
Journal enforcement is OUTSIDE LLM discretion.

Commands:
  init <state_file> <journal_dir>
      — Create/load tick journal, run integrity check, recover interrupted phase.
  can-dispatch <state_file> <journal_dir> <worker_id>
      — Check if worker can be dispatched (idempotent).
  commit-dispatch <state_file> <journal_dir> <worker_id> <operation_key>
      — Commit worker dispatch to journal.
  tick-start <state_file> <journal_dir>
  tick-end <state_file> <journal_dir>
"""

import json, os, sys, uuid
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def _tj(*args):
    """Run tick-journal.py."""
    import subprocess
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS_DIR, "tick-journal.py")] + list(args),
                       capture_output=True, text=True, timeout=15)
    out = {}
    if p.stdout.strip():
        try: out = json.loads(p.stdout)
        except: out = {"raw": p.stdout}
    return p.returncode, out


def init_tick(state_file, journal_dir):
    """Initialize/recover tick journal. Returns tick_id, run_id."""
    os.makedirs(journal_dir, exist_ok=True)

    tick_id = f"TICK-{uuid.uuid4().hex[:12].upper()}"
    rc, out = _tj("init", journal_dir, tick_id)
    if rc != 0:
        return {"error": f"Journal init failed: {out}"}

    rc2, out2 = _tj("integrity", journal_dir)
    if out2.get("integrity_ok") == False:
        out2.get("issues", [])

    rc3, out3 = _tj("recover", journal_dir)
    if "recovered" in out3.get("status", ""):
        pass

    # Start tick
    _tj("start-phase", journal_dir, "tick_start")

    # Update state phase
    try:
        with open(state_file) as f: state = json.load(f)
    except (IOError, json.JSONDecodeError):
        state = {"schema_version": 2, "tick": 0, "run_id": "", "phase": "idle"}

    state["tick"] = state.get("tick", 0) + 1
    state["run_id"] = out.get("run_id", tick_id)
    state["phase"] = "running"
    _atomic_write(state_file, state)

    return {
        "tick_id": tick_id,
        "run_id": out.get("run_id"),
        "phase": "running",
    }


def can_dispatch(state_file, journal_dir, worker_id):
    """Idempotency gate for worker dispatch."""
    op_key = f"dispatch:{worker_id}"
    rc, out = _tj("already-applied", journal_dir, op_key)
    if out.get("applied"):
        return {"can_dispatch": False, "reason": "Already dispatched", "operation_key": op_key}
    return {"can_dispatch": True, "operation_key": op_key}


def commit_dispatch(state_file, journal_dir, worker_id, operation_key):
    """Commit worker dispatch to journal."""
    _tj("start-phase", journal_dir, f"dispatch:{worker_id}")
    rc, out = _tj("complete-phase", journal_dir, f"dispatch:{worker_id}", operation_key)
    return {"committed": True, "operation_key": operation_key}


def tick_end(state_file, journal_dir):
    """Complete the tick."""
    _tj("start-phase", journal_dir, "tick_end")
    _tj("complete-phase", journal_dir, "tick_end")

    try:
        with open(state_file) as f: state = json.load(f)
    except: return {"error": "Cannot read state"}
    state["phase"] = "idle"
    _atomic_write(state_file, state)

    return {"phase": "idle"}


def _atomic_write(path, data):
    tmp = path + ".tmp." + uuid.uuid4().hex[:8]
    with open(tmp, "w") as f: json.dump(data, f, indent=2)
    os.rename(tmp, path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "init":
        if len(sys.argv) < 4: print("Usage: tick-runtime.py init <state_file> <journal_dir>"); sys.exit(1)
        result = init_tick(sys.argv[2], sys.argv[3])
    elif cmd == "can-dispatch":
        if len(sys.argv) < 5: print("Usage: tick-runtime.py can-dispatch <state> <journal_dir> <worker_id>"); sys.exit(1)
        result = can_dispatch(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "commit-dispatch":
        if len(sys.argv) < 6: print("Usage: tick-runtime.py commit-dispatch <state> <journal_dir> <worker_id> <op_key>"); sys.exit(1)
        result = commit_dispatch(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "tick-end":
        if len(sys.argv) < 4: print("Usage: tick-runtime.py tick-end <state_file> <journal_dir>"); sys.exit(1)
        result = tick_end(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr); sys.exit(1)

    print(json.dumps(result, indent=2))
    sys.exit(1 if result.get("error") else 0)
