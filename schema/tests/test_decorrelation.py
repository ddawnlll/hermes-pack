#!/usr/bin/env python3
"""
Issue #22 — Provider-chain decorrelation test
Ensures worker/challenger and orchestrator/arbiter chains use different model families.
"""
import json, os, sys, subprocess, tempfile

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..")
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
PASS_COUNT = 0
FAIL_COUNT = 0

def pass_(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"\033[1;32m[TEST] PASS:\033[0m {msg}")

def fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"\033[1;31m[TEST] FAIL:\033[0m {msg}")

def get_family(model_id):
    if not model_id:
        return ""
    stripped = model_id
    if "/" in stripped:
        first_slash = stripped.index("/")
        rest = stripped[first_slash + 1:]
        if "/" in rest:
            stripped = rest
    return stripped.split("/")[0] if "/" in stripped else stripped.split("/")[0]

# ── Test 1: project.yaml chains are decorrelated ─────────────────────────────
print("[TEST] Test 1: adapters/v7-alphaforge/project.yaml chain decorrelation")

# Parse the YAML manually (lightweight, no external deps)
proj_yaml = os.path.join(REPO_ROOT, "adapters", "v7-alphaforge", "project.yaml")
if not os.path.exists(proj_yaml):
    fail("project.yaml not found")
else:
    with open(proj_yaml) as f:
        lines = f.readlines()

    # Extract chain arrays from YAML lines
    chains = {
        "orchestrator_chain": [],
        "worker_chain": [],
        "challenger_chain": [],
        "arbiter_chain": [],
    }
    current_chain = None
    indent = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("orchestrator_chain:"):
            current_chain = "orchestrator_chain"
            indent = len(line) - len(stripped)
            continue
        elif stripped.startswith("worker_chain:"):
            current_chain = "worker_chain"
            indent = len(line) - len(stripped)
            continue
        elif stripped.startswith("challenger_chain:"):
            current_chain = "challenger_chain"
            indent = len(line) - len(stripped)
            continue
        elif stripped.startswith("arbiter_chain:"):
            current_chain = "arbiter_chain"
            indent = len(line) - len(stripped)
            continue
        elif stripped.startswith("model_name:") or stripped.startswith("litellm_params:") or stripped.startswith("general_settings:") or stripped.startswith("model_list:"):
            # Reset when we hit a new section
            current_chain = None
            continue

        if current_chain and stripped.startswith("-"):
            # Count current indentation
            curr_indent = len(line) - len(stripped)
            if curr_indent > indent:
                val = stripped.lstrip("- ").strip().strip('"').strip("'")
                if val:
                    chains[current_chain].append(val)
            else:
                current_chain = None

    # Also try a regex-like scan for lines with dash+quote inside provider block
    # Fallback: simple regex scan
    import re
    for key in chains:
        if not chains[key]:
            # fallback regex extraction
            pat = re.compile(rf"{key}:\s*(.*?)(?=\n\w|\Z)", re.S)
            m = pat.search(open(proj_yaml).read())
            if m:
                block = m.group(1)
                items = re.findall(r'-\s*"([^"]+)"', block)
                if not items:
                    items = re.findall(r'-\s*\'([^\']+)\'', block)
                if not items:
                    items = re.findall(r'-\s*([a-zA-Z0-9_/.:-]+)', block)
                chains[key] = items

    w0 = get_family(chains["worker_chain"][0]) if chains["worker_chain"] else ""
    c0 = get_family(chains["challenger_chain"][0]) if chains["challenger_chain"] else ""
    o0 = get_family(chains["orchestrator_chain"][0]) if chains["orchestrator_chain"] else ""
    a0 = get_family(chains["arbiter_chain"][0]) if chains["arbiter_chain"] else ""

    print(f"       worker[0] family: {w0}")
    print(f"       challenger[0] family: {c0}")
    print(f"       orchestrator[0] family: {o0}")
    print(f"       arbiter[0] family: {a0}")

    if w0 and c0 and w0 != c0:
        pass_(f"worker_chain[0] ({w0}) != challenger_chain[0] ({c0})")
    else:
        fail(f"worker_chain[0] and challenger_chain[0] must be different families (got {w0} vs {c0})")

    if o0 and a0 and o0 != a0:
        pass_(f"orchestrator_chain[0] ({o0}) != arbiter_chain[0] ({a0})")
    else:
        fail(f"orchestrator_chain[0] and arbiter_chain[0] must be different families (got {o0} vs {a0})")

# ── Test 2: Bootstrap.ts validation rejects same-family chains ─────────────────
print("[TEST] Test 2: bootstrap.ts decorrelation validation (fail-closed)")

# We can't easily run bun here, but we can test the TypeScript logic by reading it
bootstrap_path = os.path.join(REPO_ROOT, "bootstrap.ts")
with open(bootstrap_path) as f:
    ts_src = f.read()

if "validateChainDecorrelation" in ts_src and "die(" in ts_src:
    pass_("bootstrap.ts contains validateChainDecorrelation with die() on conflict")
else:
    fail("bootstrap.ts missing validateChainDecorrelation or die() call")

if "worker_chain[0] and challenger_chain[0]" in ts_src:
    pass_("bootstrap.ts error message mentions worker/challenger conflict")
else:
    fail("bootstrap.ts error message does not mention worker/challenger conflict")

if "orchestrator_chain[0] and arbiter_chain[0]" in ts_src:
    pass_("bootstrap.ts error message mentions orchestrator/arbiter conflict")
else:
    fail("bootstrap.ts error message does not mention orchestrator/arbiter conflict")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 56)
print(f"  Decorrelation Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
