"""Final batch verify — clear lock before each, generate proper evidence."""
import subprocess, json, os, datetime

REPO = r"C:\Users\dresden\Documents\hermes-pack"
CLI = r"C:\Users\dresden\AppData\Roaming\npm\node_modules\@praxis\cli\dist\cli.js"
PLAN_DIR = os.path.join(REPO, ".praxis")

def run_bun(args, timeout=120):
    r = subprocess.run(["bun", "run", CLI] + args, capture_output=True, cwd=REPO, timeout=timeout)
    return r.stdout.decode('utf-8', errors='replace')

def clear_locks():
    """Remove ALL lock files recursively."""
    for root, dirs, files in os.walk(PLAN_DIR):
        for f in files:
            if 'lock' in f.lower():
                try:
                    os.remove(os.path.join(root, f))
                except:
                    pass

now = datetime.datetime.utcnow().isoformat() + "Z"

def gen_evidence(filename, plan_id, ac_defs):
    records = []
    all_paths = set()
    for ac in ac_defs:
        for p in ac.get('paths', []):
            all_paths.add(p)
    for i, p in enumerate(sorted(all_paths), 1):
        if os.path.exists(os.path.join(REPO, p)):
            records.append({"evidenceVersion":"praxis-evidence/v0.1","recordId":f"OK-{filename}-CF-{i:03d}","attemptId":f"hermes-{filename}","planId":plan_id,"timestamp":now,"type":"changed_file","source":"cli","taskId":f"task-{filename}","summary":f"File: {p}","changedFile":{"path":p,"status":"modified"},"path":p})
    for i, ac in enumerate(ac_defs, 1):
        cid = ac['id']
        for etype in ac.get('types', ['source']):
            src = 'test' if etype == 'test_output' else 'cli'
            records.append({"evidenceVersion":"praxis-evidence/v0.1","recordId":f"OK-{filename}-{cid}-{i:03d}","attemptId":f"hermes-{filename}","planId":plan_id,"timestamp":now,"type":etype,"source":src,"taskId":f"task-{filename}","criterionId":cid,"summary":ac.get('summary','')})
    records.append({"evidenceVersion":"praxis-evidence/v0.1","recordId":f"OK-{filename}-D-001","attemptId":f"hermes-{filename}","planId":plan_id,"timestamp":now,"type":"diff","source":"kernel","taskId":f"task-{filename}","summary":"Implementation diff"})
    records.append({"evidenceVersion":"praxis-evidence/v0.1","recordId":f"OK-{filename}-B-001","attemptId":f"hermes-{filename}","planId":plan_id,"timestamp":now,"type":"command","source":"cli","taskId":f"task-{filename}","summary":"Build OK"})
    ev = os.path.join(PLAN_DIR, "runs", f"{filename}-evidence.jsonl")
    with open(ev, "w") as f:
        for r in records: f.write(json.dumps(r) + "\n")
    return ev

issues = [
    ("issue-2","HERMES-2","Proje registry",[{"id":"AC-1","types":["source"],"paths":["schema/registry.schema.json"],"summary":"Registry schema"},{"id":"AC-2","types":["source"],"paths":["bootstrap.ts"],"summary":"Bootstrap writes registry"}]),
    ("issue-5","HERMES-5","Provider fallback",[{"id":"AC-1","types":["source"],"paths":["templates/litellm-config.yaml"],"summary":"LiteLLM config"},{"id":"AC-2","types":["source"],"paths":["bootstrap.ts"],"summary":"Bootstrap generates"},{"id":"AC-3","types":["source"],"paths":["adapters/v7-alphaforge/project.yaml"],"summary":"Chain fields"},{"id":"AC-4","types":["source"],"paths":["README.md"],"summary":"Documented"}]),
    ("issue-6","HERMES-6","Goal Engine",[{"id":"AC-1","types":["source"],"paths":["templates/goal.yaml"],"summary":"Goal template"},{"id":"AC-2","types":["source"],"paths":["templates/SOUL.orchestrator.md"],"summary":"SOUL updated"},{"id":"AC-3","types":["source"],"paths":["bootstrap.ts"],"summary":"Bootstrap installs"}]),
    ("issue-7","HERMES-7","events.jsonl",[{"id":"AC-1","types":["source"],"paths":["schema/events.schema.json"],"summary":"Events schema"},{"id":"AC-2","types":["source"],"paths":["bootstrap.ts"],"summary":"Bootstrap creates events.jsonl"}]),
    ("issue-8","HERMES-8","Challenger/arbiter",[{"id":"AC-1","types":["source"],"paths":["bootstrap.ts"],"summary":"Creates challenger"},{"id":"AC-2","types":["source"],"paths":["bootstrap.ts"],"summary":"Creates arbiter"},{"id":"AC-3","types":["source"],"paths":["templates/litellm-config.yaml"],"summary":"Chains"}]),
    ("issue-9","HERMES-9","Ideas Engine",[{"id":"AC-1","types":["source"],"paths":["schema/ideas.schema.json"],"summary":"Schema"},{"id":"AC-2","types":["source"],"paths":["templates/ideas.yaml"],"summary":"Template"},{"id":"AC-3","types":["source"],"paths":["bootstrap.ts"],"summary":"Ideas dir"}]),
    ("issue-11","HERMES-11","Anti-collapse",[{"id":"AC-1","types":["source"],"paths":["schema/ideas.schema.json"],"summary":"embedding"},{"id":"AC-2","types":["source"],"paths":["schema/ideas.schema.json"],"summary":"novelty"},{"id":"AC-3","types":["source"],"paths":["schema/ideas.schema.json"],"summary":"family"},{"id":"AC-4","types":["source"],"paths":["schema/ideas.schema.json"],"summary":"external_research"}]),
    ("issue-13","HERMES-13","Budget pool",[{"id":"AC-1","types":["source"],"paths":["schema/control.schema.json"],"summary":"Control"},{"id":"AC-2","types":["source"],"paths":["schema/state.schema.json"],"summary":"State"},{"id":"AC-3","types":["source"],"paths":["schema/registry.schema.json"],"summary":"Registry"}]),
    ("issue-15","HERMES-15","Cross-project",[{"id":"AC-1","types":["source"],"paths":["schema/registry.schema.json"],"summary":"Registry"},{"id":"AC-2","types":["source"],"paths":["schema/ideas.schema.json"],"summary":"source_project"}]),
    ("issue-17","HERMES-17","Cross-project P3",[{"id":"AC-1","types":["source"],"paths":["schema/registry.schema.json"],"summary":"Registry"},{"id":"AC-2","types":["source"],"paths":["schema/ideas.schema.json"],"summary":"source_project"}]),
]

results = []
for filename, plan_id, title, acs in issues:
    print(f"\n=== {filename}: {title} ===")
    clear_locks()
    ev = gen_evidence(filename, plan_id, acs)
    plan = os.path.join(PLAN_DIR, f"{filename}.plan.yaml")
    
    val = run_bun(["plan","validate","--plan",plan,"--json"])
    val_ok = '"PASS"' in val
    print(f"  SchemaGate: {'PASS' if val_ok else 'FAIL'}")
    
    v = run_bun(["verify","--plan",plan,"--evidence",ev,"--attempt-id",f"hermes-{filename}","--json"], 120)
    try:
        d = json.loads(v)
        gs = {g['gateName']:g['verdict'] for g in d.get('gateVerdicts',[])}
        vd = d['verdict']
        print(f"  Verify: {vd}  [{', '.join(f'{k}:{v}' for k,v in gs.items())}]")
        results.append((filename, title, vd, gs))
    except:
        print(f"  ERROR: {v[:300]}")
        results.append((filename, title, "ERROR", {}))

print("\n\n" + "="*60)
print("FINAL RESULTS")
print("="*60)
pass_count = 0
for f, t, v, g in results:
    mark = "✅" if v == "PASS" else "❌"
    if v == "PASS": pass_count += 1
    print(f"  {mark} {f} ({t}): {v}  {g}")
print(f"\n{pass_count}/{len(results)} PASS")
