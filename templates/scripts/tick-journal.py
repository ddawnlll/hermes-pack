#!/usr/bin/env python3
"""
tick-journal.py — Durable transaction journal for crash recovery (#71)

Stable tick_id, run_id, phase status, operation keys.
Atomic write-and-rename. Integrity checking. Stale-lock recovery.
Bounded timeout. Resume from last committed phase.

Idempotent for: worker dispatch, blame propagation, merges, lessons,
provenance, spend accounting, channel output, reflector consolidation.

Commands:
  init <journal_dir> <tick_id>
      — Initialize a new tick journal with tick_id and run_id.
  start-phase <journal_dir> <phase_name>
      — Start a phase. Records timestamp.
  complete-phase <journal_dir> <phase_name> [operation_key...]
      — Complete a phase. Records operation keys for idempotency.
  already-applied <journal_dir> <operation_key>
      — Check if operation was already committed (idempotency gate).
  status <journal_dir>
      — Show current journal status.
  recover <journal_dir>
      — Detect crashes, recover from last committed phase.
      Uses stale-lock detection with bounded timeout.
  integrity <journal_dir>
      — Check journal integrity.
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime


JOURNAL_VERSION = 1
STALE_LOCK_TIMEOUT_S = 300  # 5 minutes


def get_ts():
    return datetime.utcnow().isoformat() + "Z"


def _atomic_write(path, data):
    """Atomic write: write to temp, then rename."""
    tmp = path + ".tmp." + uuid.uuid4().hex[:8]
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.rename(tmp, path)


def init_journal(journal_dir, tick_id=None):
    """Initialize a new tick journal."""
    os.makedirs(journal_dir, exist_ok=True)

    if tick_id is None:
        tick_id = f"TICK-{uuid.uuid4().hex[:12].upper()}"

    run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"

    journal = {
        "journal_version": JOURNAL_VERSION,
        "tick_id": tick_id,
        "run_id": run_id,
        "phases": [],
        "status": "initialized",
        "operation_keys": [],
        "created_at": get_ts(),
        "updated_at": get_ts(),
    }

    journal_file = os.path.join(journal_dir, f"{tick_id}.journal.json")
    _atomic_write(journal_file, journal)

    # Write lock file
    lock_file = os.path.join(journal_dir, f"{tick_id}.lock")
    with open(lock_file, "w") as f:
        f.write(json.dumps({
            "tick_id": tick_id,
            "locked_at": get_ts(),
            "pid": os.getpid(),
        }))

    return {
        "status": "initialized",
        "tick_id": tick_id,
        "run_id": run_id,
        "journal_file": journal_file,
    }


def load_journal(journal_dir, tick_id=None):
    """Load journal by tick_id or latest."""
    if tick_id:
        jf = os.path.join(journal_dir, f"{tick_id}.journal.json")
    else:
        # Find latest
        candidates = []
        for fname in os.listdir(journal_dir):
            if fname.endswith(".journal.json"):
                candidates.append(fname)
        if not candidates:
            return None
        # Sort by tick number (desc)
        candidates.sort(reverse=True)
        jf = os.path.join(journal_dir, candidates[0])

    if not os.path.exists(jf):
        return None
    with open(jf) as f:
        return json.load(f)


def start_phase(journal_dir, phase_name):
    """Start a phase. Records timestamp."""
    j = load_journal(journal_dir)
    if j is None:
        return {"error": "No journal found. Call init first."}

    j["phases"].append({
        "phase": phase_name,
        "status": "running",
        "started_at": get_ts(),
        "completed_at": None,
        "operation_keys": [],
    })
    j["status"] = f"running:{phase_name}"
    j["updated_at"] = get_ts()

    jf = os.path.join(journal_dir, f"{j['tick_id']}.journal.json")
    _atomic_write(jf, j)

    return {"status": f"phase_started:{phase_name}", "tick_id": j["tick_id"], "run_id": j["run_id"]}


def complete_phase(journal_dir, phase_name, operation_keys=None):
    """Complete a phase with operation keys for idempotency."""
    j = load_journal(journal_dir)
    if j is None:
        return {"error": "No journal found."}

    if operation_keys is None:
        operation_keys = []

    # Find and update the phase
    for phase in j["phases"]:
        if phase["phase"] == phase_name and phase["status"] == "running":
            phase["status"] = "completed"
            phase["completed_at"] = get_ts()
            for op_key in operation_keys:
                if op_key not in phase.get("operation_keys", []):
                    phase.setdefault("operation_keys", []).append(op_key)
                if op_key not in j["operation_keys"]:
                    j["operation_keys"].append(op_key)
            break

    j["status"] = f"completed:{phase_name}"
    j["updated_at"] = get_ts()

    jf = os.path.join(journal_dir, f"{j['tick_id']}.journal.json")
    _atomic_write(jf, j)

    return {
        "status": f"phase_completed:{phase_name}",
        "operation_keys_added": len(operation_keys),
        "total_operation_keys": len(j["operation_keys"]),
    }


def already_applied(journal_dir, operation_key):
    """Idempotency gate: check if operation was already committed."""
    j = load_journal(journal_dir)
    if j is None:
        return {"applied": False, "reason": "No journal"}

    applied = operation_key in j.get("operation_keys", [])
    return {
        "applied": applied,
        "operation_key": operation_key,
        "tick_id": j.get("tick_id"),
        "run_id": j.get("run_id"),
    }


def journal_status(journal_dir):
    """Show current journal status."""
    j = load_journal(journal_dir)
    if j is None:
        return {"error": "No journal found"}

    # Check for stale lock
    lock_file = os.path.join(journal_dir, f"{j.get('tick_id')}.lock")
    stale = False
    if os.path.exists(lock_file):
        with open(lock_file) as f:
            lock_data = json.load(f)
        if time.time() - os.path.getmtime(lock_file) > STALE_LOCK_TIMEOUT_S:
            stale = True

    return {
        "tick_id": j.get("tick_id"),
        "run_id": j.get("run_id"),
        "status": j.get("status"),
        "phases": j.get("phases", []),
        "total_operation_keys": len(j.get("operation_keys", [])),
        "stale_lock": stale,
        "created_at": j.get("created_at"),
        "updated_at": j.get("updated_at"),
    }


def recover_journal(journal_dir):
    """Detect crashes, recover from last committed phase."""
    j = load_journal(journal_dir)
    if j is None:
        return {"error": "No journal to recover"}

    # Find the last non-completed phase
    running_phase = None
    for phase in j.get("phases", []):
        if phase.get("status") == "running":
            running_phase = phase
            break

    if running_phase:
        # Crash detected: this phase was running but never completed
        running_phase["status"] = "crashed"
        running_phase["crashed_at"] = get_ts()

        # Resume from previous completed phase
        completed_phases = [p for p in j.get("phases", [])
                           if p.get("status") == "completed"]
        resume_phase = completed_phases[-1]["phase"] if completed_phases else "init"

        j["status"] = f"recovered:resume_from_{resume_phase}"
        j["recovered_at"] = get_ts()
    else:
        j["status"] = "recovered:no_crash_detected"
        resume_phase = j.get("phases", [])[-1]["phase"] if j.get("phases") else "init"

    # Clean up stale lock
    lock_file = os.path.join(journal_dir, f"{j.get('tick_id')}.lock")
    if os.path.exists(lock_file):
        if time.time() - os.path.getmtime(lock_file) > STALE_LOCK_TIMEOUT_S:
            os.remove(lock_file)

    jf = os.path.join(journal_dir, f"{j['tick_id']}.journal.json")
    _atomic_write(jf, j)

    return {
        "status": j["status"],
        "tick_id": j.get("tick_id"),
        "run_id": j.get("run_id"),
        "resume_phase": resume_phase,
        "crashed_phase": running_phase["phase"] if running_phase else None,
    }


def check_integrity(journal_dir):
    """Check journal integrity."""
    issues = []
    j = load_journal(journal_dir)
    if j is None:
        return {"error": "No journal found"}

    # Check version
    if j.get("journal_version") != JOURNAL_VERSION:
        issues.append(f"Version mismatch: {j.get('journal_version')} != {JOURNAL_VERSION}")

    # Check phase ordering
    phase_names = [p.get("phase") for p in j.get("phases", [])]
    for pname in phase_names:
        if phase_names.count(pname) > 1:
            issues.append(f"Duplicate phase: {pname}")

    # Check operation key uniqueness
    op_keys = j.get("operation_keys", [])
    if len(op_keys) != len(set(op_keys)):
        issues.append("Duplicate operation keys found")

    return {
        "integrity_ok": len(issues) == 0,
        "issues": issues,
        "tick_id": j.get("tick_id"),
        "phase_count": len(j.get("phases", [])),
        "operation_key_count": len(op_keys),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "init":
        jd = sys.argv[2]
        tid = sys.argv[3] if len(sys.argv) > 3 else None
        result = init_journal(jd, tid)
        print(json.dumps(result, indent=2))

    elif cmd == "start-phase":
        if len(sys.argv) < 4:
            print("Usage: tick-journal.py start-phase <journal_dir> <phase_name>")
            sys.exit(1)
        result = start_phase(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))

    elif cmd == "complete-phase":
        if len(sys.argv) < 4:
            print("Usage: tick-journal.py complete-phase <journal_dir> <phase_name> [op_keys...]")
            sys.exit(1)
        jd, pn = sys.argv[2], sys.argv[3]
        ops = sys.argv[4:]
        result = complete_phase(jd, pn, ops)
        print(json.dumps(result, indent=2))

    elif cmd == "already-applied":
        if len(sys.argv) < 4:
            print("Usage: tick-journal.py already-applied <journal_dir> <operation_key>")
            sys.exit(1)
        result = already_applied(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))

    elif cmd == "status":
        result = journal_status(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "recover":
        result = recover_journal(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "integrity":
        result = check_integrity(sys.argv[2])
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
