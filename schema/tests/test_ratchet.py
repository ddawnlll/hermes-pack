#!/usr/bin/env python3
"""
Issue #26 — Adaptive Ratchet Test
Tests the Python ratchet-update.py directly (bash script has Windows compat issues).
"""
import json, os, sys, tempfile, shutil

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "templates", "scripts")
PASS_COUNT = 0
FAIL_COUNT = 0

def pass_(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"[TEST] PASS: {msg}")

def fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"[TEST] FAIL: {msg}")

# Import the ratchet update function
sys.path.insert(0, SCRIPTS_DIR)
from importlib.machinery import SourceFileLoader
mod = SourceFileLoader("ratchet_update", os.path.join(SCRIPTS_DIR, "ratchet-update.py")).load_module()
update_ratchet = mod.update_ratchet

# ── Test 1: ratchet-update.py exists
print("[TEST] Test 1: ratchet-update.py exists")
py_path = os.path.join(SCRIPTS_DIR, "ratchet-update.py")
sh_path = os.path.join(SCRIPTS_DIR, "ratchet-update.sh")
if os.path.exists(py_path):
    pass_("ratchet-update.py exists")
else:
    fail("ratchet-update.py NOT found")
if os.path.exists(sh_path):
    pass_("ratchet-update.sh exists")
else:
    fail("ratchet-update.sh NOT found")

# ── Test 2: ratchet.json template
print("[TEST] Test 2: ratchet.json template")
template_path = os.path.join(REPO_ROOT, "templates", "ratchet.json")
if os.path.exists(template_path):
    with open(template_path) as f:
        r = json.load(f)
    for field in ["schema_version", "level", "blocking_ratio", "window_size", "history"]:
        if field in r:
            pass_(f"ratchet.json has '{field}'")
        else:
            fail(f"ratchet.json missing '{field}'")
    if r.get("schema_version") == 1:
        pass_("schema_version=1")
    else:
        fail(f"schema_version={r.get('schema_version')}, expected 1")
else:
    fail("ratchet.json template NOT found")

# ── Test 3: Tighten on low blocking ratio (ratio < 0.20)
print("[TEST] Test 3: Simulate tighten (ratio < 0.20)")
tmpdir = tempfile.mkdtemp()
try:
    ledger_dir = os.path.join(tmpdir, "ledger")
    os.makedirs(os.path.join(ledger_dir, "redteam"))
    with open(os.path.join(ledger_dir, "redteam", "objections.jsonl"), "w") as f:
        for i in range(9):
            f.write(json.dumps({"verdict": "SUSTAIN", "tick": i}) + "\n")
        f.write(json.dumps({"verdict": "BLOCK", "tick": 10}) + "\n")
    # Init
    update_ratchet(ledger_dir)
    with open(os.path.join(ledger_dir, "ratchet.json")) as f:
        r = json.load(f)
    if r["level"] == 0:
        pass_("Initial level=0")
    else:
        fail(f"Initial level={r['level']}, expected 0")
    # Update → should tighten
    update_ratchet(ledger_dir)
    with open(os.path.join(ledger_dir, "ratchet.json")) as f:
        r = json.load(f)
    if r["level"] == 1:
        pass_("Tightened to level=1 (ratio=0.10 < 0.20)")
    else:
        fail(f"Level={r['level']}, expected 1 (tighten)")
    if abs(r["blocking_ratio"] - 0.1) < 0.01:
        pass_("blocking_ratio=0.10 correct")
    else:
        fail(f"blocking_ratio={r['blocking_ratio']}, expected 0.10")
finally:
    shutil.rmtree(tmpdir)

# ── Test 4: Loosen on high blocking ratio (ratio > 0.80)
print("[TEST] Test 4: Simulate loosen (ratio > 0.80)")
tmpdir = tempfile.mkdtemp()
try:
    ledger_dir = os.path.join(tmpdir, "ledger")
    os.makedirs(os.path.join(ledger_dir, "redteam"))
    with open(os.path.join(ledger_dir, "redteam", "objections.jsonl"), "w") as f:
        for i in range(1):
            f.write(json.dumps({"verdict": "SUSTAIN", "tick": i}) + "\n")
        for i in range(9):
            f.write(json.dumps({"verdict": "BLOCK", "tick": i + 2}) + "\n")
    update_ratchet(ledger_dir)
    update_ratchet(ledger_dir)
    with open(os.path.join(ledger_dir, "ratchet.json")) as f:
        r = json.load(f)
    if r["level"] == -1:
        pass_("Loosened to level=-1 (ratio=0.90 > 0.80)")
    else:
        fail(f"Level={r['level']}, expected -1 (loosen)")
finally:
    shutil.rmtree(tmpdir)

# ── Test 5: Level clamping [-3, 5]
print("[TEST] Test 5: Level clamping")
tmpdir = tempfile.mkdtemp()
try:
    ledger_dir = os.path.join(tmpdir, "ledger")
    os.makedirs(os.path.join(ledger_dir, "redteam"))
    with open(os.path.join(ledger_dir, "ratchet.json"), "w") as f:
        json.dump({"schema_version": 1, "level": 5, "blocking_ratio": 0.0, "window_size": 20, "history": [], "last_updated": None}, f)
    with open(os.path.join(ledger_dir, "redteam", "objections.jsonl"), "w") as f:
        for i in range(10):
            f.write(json.dumps({"verdict": "SUSTAIN", "tick": i}) + "\n")
    update_ratchet(ledger_dir)
    with open(os.path.join(ledger_dir, "ratchet.json")) as f:
        r = json.load(f)
    if r["level"] <= 5:
        pass_(f"Level clamped at {r['level']} (max=5)")
    else:
        fail(f"Level={r['level']}, exceeds max=5")
finally:
    shutil.rmtree(tmpdir)

# ── Test 6: Level floor at -3
print("[TEST] Test 6: Level floor at -3")
tmpdir = tempfile.mkdtemp()
try:
    ledger_dir = os.path.join(tmpdir, "ledger")
    os.makedirs(os.path.join(ledger_dir, "redteam"))
    with open(os.path.join(ledger_dir, "ratchet.json"), "w") as f:
        json.dump({"schema_version": 1, "level": -3, "blocking_ratio": 1.0, "window_size": 20, "history": [], "last_updated": None}, f)
    with open(os.path.join(ledger_dir, "redteam", "objections.jsonl"), "w") as f:
        for i in range(10):
            f.write(json.dumps({"verdict": "BLOCK", "tick": i}) + "\n")
    update_ratchet(ledger_dir)
    with open(os.path.join(ledger_dir, "ratchet.json")) as f:
        r = json.load(f)
    if r["level"] >= -3:
        pass_(f"Level floored at {r['level']} (min=-3)")
    else:
        fail(f"Level={r['level']}, below min=-3")
finally:
    shutil.rmtree(tmpdir)

# ── Test 7: Balanced ratio no change
print("[TEST] Test 7: Balanced ratio (0.20-0.80) no change")
tmpdir = tempfile.mkdtemp()
try:
    ledger_dir = os.path.join(tmpdir, "ledger")
    os.makedirs(os.path.join(ledger_dir, "redteam"))
    with open(os.path.join(ledger_dir, "redteam", "objections.jsonl"), "w") as f:
        for i in range(5):
            f.write(json.dumps({"verdict": "SUSTAIN", "tick": i}) + "\n")
        for i in range(5):
            f.write(json.dumps({"verdict": "BLOCK", "tick": i + 5}) + "\n")
    update_ratchet(ledger_dir)
    update_ratchet(ledger_dir)
    with open(os.path.join(ledger_dir, "ratchet.json")) as f:
        r = json.load(f)
    if r["level"] == 0:
        pass_("Level unchanged at 0 (ratio=0.50 in balanced zone)")
    else:
        fail(f"Level={r['level']}, expected 0 (balanced)")
finally:
    shutil.rmtree(tmpdir)

# ── Test 8: SOUL.redteam.md references ratchet
print("[TEST] Test 8: SOUL.redteam.md references ratchet")
soul_path = os.path.join(REPO_ROOT, "templates", "SOUL.redteam.md")
if os.path.exists(soul_path):
    with open(soul_path, encoding="utf-8", errors="replace") as f:
        soul = f.read()
    if "ratchet" in soul.lower():
        pass_("SOUL.redteam.md references ratchet")
    else:
        fail("SOUL.redteam.md missing ratchet reference")
else:
    fail("SOUL.redteam.md NOT found")

# ── Summary
print()
print("=" * 60)
print(f"  Adaptive Ratchet Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 60)
sys.exit(1 if FAIL_COUNT > 0 else 0)
