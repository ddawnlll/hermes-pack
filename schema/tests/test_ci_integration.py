#!/usr/bin/env python3
"""CI integration checks: budget, journal, interlock."""
import json, os, subprocess, sys, tempfile, yaml
SD = "templates/scripts"
FAIL = 0

def ok(m): print(f"  PASS {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  FAIL {m}")

def run(s, *a):
    p = subprocess.run([sys.executable, f"{SD}/{s}"] + list(a), capture_output=True, text=True, timeout=30)
    o = {}
    if p.stdout.strip():
        try: o = json.loads(p.stdout)
        except: o = {"raw": p.stdout}
    return p.returncode, o, p.stderr

# Budget idempotency
with tempfile.TemporaryDirectory() as td:
    sf = f"{td}/s.json"
    with open(sf, "w") as f: json.dump({"schema_version":2,"tick":0,"features":{"analogy_channel":True},
        "channel_budgets":{"analogy":0.25},"channel_spend_today":{},"channel_spend_date":""}, f)
    jd = f"{td}/j"; os.makedirs(jd)
    r, o, _ = run("channel-budget.py", "can-run", sf, "analogy")
    ok("can-run") if o.get("allowed") else fail(f"can-run: {o}")
    r, o, _ = run("channel-budget.py", "spend", sf, jd, "analogy", "0.10", "op-1")
    ok("spend recorded") if o.get("status")=="recorded" else fail(f"spend: {o}")
    r, o, _ = run("channel-budget.py", "spend", sf, jd, "analogy", "0.10", "op-1")
    ok("dedup") if o.get("status")=="already_applied" else fail(f"dedup: {o}")

# Journal crash/replay
with tempfile.TemporaryDirectory() as td:
    sf = f"{td}/s.json"
    with open(sf, "w") as f: json.dump({"schema_version":2,"tick":0,"phase":"idle"}, f)
    def tk(*a):
        r, o, _ = run("tick-runtime.py", *a)
        return o
    jd = f"{td}/j"
    r = tk("init", sf, jd)
    ok("tick init") if r.get("tick_id") else fail(f"init: {r}")
    r2 = tk("can-dispatch", sf, jd, "w-1")
    ok("can dispatch") if r2.get("can_dispatch") else fail(f"dispatch: {r2}")
    tk("commit-dispatch", sf, jd, "w-1", r2["operation_key"])
    r3 = tk("can-dispatch", sf, jd, "w-1")
    ok("redispatch blocked") if not r3.get("can_dispatch") else fail(f"redispatch: {r3}")
    r4 = tk("init", sf, jd)
    ok("recovery") if r4.get("recovered") else fail(f"recovery: {r4}")
    tk("tick-end", sf, jd)

# Active-mode interlock
with tempfile.TemporaryDirectory() as td:
    sf = f"{td}/s.json"
    bf = f"{td}/beliefs.yaml"
    with open(sf, "w") as f: json.dump({"schema_version":2,"tick":0,"features":{"reflector":"active"}}, f)
    with open(bf, "w") as f: yaml.dump({"schema_version":1,"beliefs":[]}, f)
    p = subprocess.run([sys.executable, f"{SD}/feature-flags.py", "set", sf, "reflector", "active"],
        capture_output=True, text=True, timeout=30)
    ok("active blocked without readiness") if p.returncode != 0 else fail(f"set active: {p.stdout[:200]}")

print(f"\nCI integration tests: {FAIL} failure(s)")
sys.exit(FAIL)
