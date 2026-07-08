"""Run verify with properly formatted evidence, removing stale locks first."""
import subprocess, json, os

REPO = r"C:\Users\dresden\Documents\hermes-pack"
CLI = r"C:\Users\dresden\AppData\Roaming\npm\node_modules\@praxis\cli\dist\cli.js"
PLAN = os.path.join(REPO, ".praxis", "issue-001.plan.yaml")
EVIDENCE = os.path.join(REPO, ".praxis", "runs", "issue-001-evidence.jsonl")

# Remove stale locks
praxis_dir = os.path.join(REPO, ".praxis")
if os.path.isdir(praxis_dir):
    for f in os.listdir(praxis_dir):
        if f.endswith(".lock"):
            os.remove(os.path.join(praxis_dir, f))
            print(f"Removed stale lock: {f}")

# Run verify
result = subprocess.run(
    ["bun", "run", CLI, "verify", "--plan", PLAN, "--evidence", EVIDENCE, "--attempt-id", "hermes-issue-001", "--json"],
    capture_output=True, cwd=REPO, timeout=120
)
out = result.stdout.decode('utf-8', errors='replace')
err = result.stderr.decode('utf-8', errors='replace')

try:
    data = json.loads(out)
    for gv in data.get("gateVerdicts", []):
        rc = ', '.join(gv['reasonCodes'])
        print(f"  {gv['gateName']}: {gv['verdict']}  ({rc})")
    print(f"\nOverall: {data['verdict']}")
except:
    print(f"Parse error: {out[:500]}")
    print(f"Stderr: {err[:500]}")
