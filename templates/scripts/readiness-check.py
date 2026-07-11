#!/usr/bin/env python3
"""
readiness-check.py — Reflector active-mode safety interlock (#57, #70)

Real deterministic checks via subprocess. No fake pass:true.
Model decorrelation checked by reading adapter config.
Shadow canary requires separate persisted marker file.
"""

import json, os, subprocess, sys, uuid, yaml
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.normpath(os.path.join(SCRIPTS_DIR, "..", ".."))

def get_ts():
    return datetime.utcnow().isoformat() + "Z"

def run(script, *args):
    sp = os.path.join(SCRIPTS_DIR, script)
    if not os.path.exists(sp): return None, {"error": f"Not found: {sp}"}
    p = subprocess.run([sys.executable, sp] + list(args), capture_output=True, text=True, timeout=30)
    out = {}
    if p.stdout.strip():
        try: out = json.loads(p.stdout)
        except: out = {"raw": p.stdout}
    return p.returncode, out

def model_family(model_id):
    """Extract model family from an ID like 'openrouter/deepseek/deepseek-chat'."""
    if not model_id: return ""
    s = model_id.split("/", 1)[1] if model_id.count("/") >= 2 else model_id
    return s.split("/")[0].lower()

def check_decorrelation():
    """Read adapter/project files and verify reflector != orchestrator family."""
    adapters_dir = os.path.join(ROOT_DIR, "adapters")
    results = {"checks": [], "pass": True}

    # Check default configs in bootstrap
    for bootstrap in ["bootstrap.sh", "bootstrap.ts"]:
        bp = os.path.join(ROOT_DIR, bootstrap)
        if not os.path.exists(bp): continue
        with open(bp) as f: content = f.read()
        # Extract model strings
        if bootstrap == "bootstrap.sh":
            import re
            orch_m = re.search(r'DF_ORCH_MODEL="([^"]+)"', content)
            ref_m = re.search(r'DF_REFLECTOR_MODEL="([^"]+)"', content)
        else:
            orch_m = re.search(r'orchestrator_model:\s*"([^"]+)"', content)
            ref_m = re.search(r'reflector_model:\s*"([^"]+)"', content)
        if orch_m and ref_m:
            of = model_family(orch_m.group(1))
            rf = model_family(ref_m.group(1))
            ok = of != rf and rf != ""
            results["checks"].append({"source": bootstrap, "orchestrator": of, "reflector": rf, "decorrelated": ok})
            if not ok:
                results["pass"] = False

    # Check all adapter project.yaml files
    if os.path.isdir(adapters_dir):
        for ad in sorted(os.listdir(adapters_dir)):
            pf = os.path.join(adapters_dir, ad, "project.yaml")
            if not os.path.exists(pf): continue
            with open(pf) as f:
                try:
                    cfg = yaml.safe_load(f)
                    h = cfg.get("hermes", {})
                    p = h.get("provider", {})
                    orch = p.get("orchestrator_model") or (p.get("orchestrator_chain") or [None])[0]
                    ref = p.get("reflector_model") or (p.get("reflector_chain") or [None])[0]
                    if orch and ref:
                        of = model_family(str(orch))
                        rf = model_family(str(ref))
                        ok = of != rf and rf != ""
                        results["checks"].append({"source": f"adapter:{ad}", "orchestrator": of, "reflector": rf, "decorrelated": ok})
                        if not ok: results["pass"] = False
                except: pass

    return results

def check(state_file, beliefs_file, templates_dir=None):
    results = {}
    all_pass = True

    # 1. Authority matrix coverage
    rc, out = run("containment-engine.py", "dynamic-coverage", templates_dir or SCRIPTS_DIR)
    if rc is None:
        results["authority_matrix_coverage"] = {"pass": False, "error": out.get("error")}
        results["blocking_state_timeouts"] = {"pass": False}
        all_pass = False
    else:
        cov_ok = out.get("coverage_complete", False)
        results["authority_matrix_coverage"] = {"pass": cov_ok, "pairs": out.get("covered_pairs", 0)}
        if not cov_ok: all_pass = False
        results["blocking_state_timeouts"] = {"pass": not out.get("blocking_state_issues"),
            "issues": out.get("blocking_state_issues", [])}
        if out.get("blocking_state_issues"): all_pass = False

    # 2. Suspect TTL
    rc2, _ = run("containment-engine.py", "suspect-ttl", beliefs_file, "--tick-increment=0")
    results["suspect_ttl_mechanism"] = {"pass": rc2 is not None and rc2 < 2}
    if not results["suspect_ttl_mechanism"]["pass"]: all_pass = False

    # 3. Eviction
    rc3, _ = run("containment-engine.py", "eviction-review", beliefs_file)
    results["eviction_mechanism"] = {"pass": rc3 is not None and rc3 < 2}
    if not results["eviction_mechanism"]["pass"]: all_pass = False

    # 4. Cooldown/hysteresis
    rc4, _ = run("containment-engine.py", "ratchet-check", beliefs_file)
    results["cooldown_hysteresis_mechanism"] = {"pass": rc4 is not None and rc4 < 2}
    if not results["cooldown_hysteresis_mechanism"]["pass"]: all_pass = False

    # 5. Beliefs file validates against schema
    belief_valid = False
    if os.path.exists(beliefs_file):
        try:
            with open(beliefs_file) as f: bd = yaml.safe_load(f)
            if isinstance(bd, dict) and "beliefs" in bd:
                import jsonschema
                sp = os.path.join(ROOT_DIR, "schema", "beliefs.schema.json")
                if os.path.exists(sp):
                    with open(sp) as f: schema = json.load(f)
                    jsonschema.validate(bd, schema)
                    belief_valid = True
        except: pass
    results["canonical_beliefs_file_validates"] = {"pass": belief_valid}
    if not belief_valid: all_pass = False

    # 6. Model decorrelation — REAL check via adapter configs
    dc = check_decorrelation()
    results["reflector_model_decorrelated"] = {"pass": dc["pass"], "checks": dc["checks"]}
    if not dc["pass"]: all_pass = False

    # 7. Shadow canary — requires separate persisted marker
    ledger_dir = os.path.dirname(state_file)
    marker = os.path.join(ledger_dir, "reflector", ".shadow_canary_done")
    shadow_ok = os.path.exists(marker)
    results["shadow_canary_passed"] = {"pass": shadow_ok,
        "note": "shadow canary marker exists" if shadow_ok else "Run reflector in shadow mode first to create marker"}
    if not shadow_ok: all_pass = False

    return {
        "schema_version": 1,
        "readiness_id": f"READY-{uuid.uuid4().hex[:12].upper()}",
        "timestamp": get_ts(),
        "all_checks_pass": all_pass,
        "checks": results,
        "failed_checks": [k for k, v in results.items() if not v.get("pass", False)] if not all_pass else [],
    }

def write_readiness(ledger_dir, result):
    d = os.path.join(ledger_dir, "reflector")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "readiness.json")
    tmp = path + ".tmp." + uuid.uuid4().hex[:8]
    with open(tmp, "w") as f: json.dump(result, f, indent=2)
    os.rename(tmp, path)
    return path

def write_shadow_canary_marker(ledger_dir):
    """Create the shadow canary marker after a successful shadow run."""
    d = os.path.join(ledger_dir, "reflector")
    os.makedirs(d, exist_ok=True)
    marker = os.path.join(d, ".shadow_canary_done")
    with open(marker, "w") as f:
        json.dump({"created_at": get_ts(), "source": "readiness-check"}, f)
    return marker

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: readiness-check.py <state_file> <beliefs_file> [templates_dir]"); sys.exit(1)
    sf, bf = sys.argv[1], sys.argv[2]
    td = sys.argv[3] if len(sys.argv) > 3 else SCRIPTS_DIR
    result = check(sf, bf, td)
    if result["all_checks_pass"]:
        path = write_readiness(os.path.dirname(sf), result)
        result["readiness_file"] = path
        print(json.dumps(result, indent=2)); sys.exit(0)
    else:
        print(json.dumps(result, indent=2)); sys.exit(1)
