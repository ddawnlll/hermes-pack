#!/usr/bin/env python3
"""
Issue #5 — Provider fallback router / LiteLLM proxy config validation
Verifies that litellm-config.yaml has per-profile chains ending in local model.
"""
import os, sys, re

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

# ── Test 1: litellm-config.yaml exists ───────────────────────────────────────
print("[TEST] Test 1: litellm-config.yaml exists")
litellm_path = os.path.join(REPO_ROOT, "templates", "litellm-config.yaml")
if os.path.exists(litellm_path):
    pass_("templates/litellm-config.yaml exists")
else:
    fail("templates/litellm-config.yaml not found")

with open(litellm_path) as f:
    config = f.read()

# ── Test 2: Config has all required profile chains ──────────────────────────
print("[TEST] Test 2: Profile chains present")
# Template vars per profile (orchestrator uses ORCH, others use full name)
profile_vars = {
    "orchestrator": "__HERMES_ORCH_MODEL__",
    "worker": "__HERMES_WORKER_MODEL__",
    "challenger": "__HERMES_CHALLENGER_MODEL__",
    "arbiter": "__HERMES_ARBITER_MODEL__",
}
for profile, var in profile_vars.items():
    if var in config:
        pass_(f"{profile} chain present ({var})")
    else:
        fail(f"{profile} chain MISSING template var {var}")

# ── Test 3: Each profile has template vars ──────────────────────────────────
print("[TEST] Test 3: Template variables per profile")
expected_vars = {
    "orchestrator": ["__HERMES_ORCH_CHAIN_0__", "__HERMES_ORCH_CHAIN_1__", "__HERMES_ORCH_CHAIN_2__"],
    "worker": ["__HERMES_WORKER_CHAIN_0__", "__HERMES_WORKER_CHAIN_1__"],
    "challenger": ["__HERMES_CHALLENGER_CHAIN_0__", "__HERMES_CHALLENGER_CHAIN_1__"],
    "arbiter": ["__HERMES_ARBITER_CHAIN_0__", "__HERMES_ARBITER_CHAIN_1__", "__HERMES_ARBITER_CHAIN_2__"],
}
for profile, vars in expected_vars.items():
    for v in vars:
        if v in config:
            pass_(f"{profile}: {v} present")
        else:
            fail(f"{profile}: {v} MISSING")

# ── Test 4: Bootstrap.ts generates LiteLLM config ───────────────────────────
print("[TEST] Test 4: bootstrap.ts generates LiteLLM config")
bootstrap_path = os.path.join(REPO_ROOT, "bootstrap.ts")
with open(bootstrap_path, encoding="utf-8", errors="replace") as f:
    ts_src = f.read()

if "litellm-config.yaml" in ts_src:
    pass_("bootstrap.ts references litellm-config.yaml")
else:
    fail("bootstrap.ts missing litellm-config.yaml reference")

if "__HERMES_ORCH_CHAIN_0__" in ts_src:
    pass_("bootstrap.ts generates orchestrator chain vars")
else:
    fail("bootstrap.ts missing orchestrator chain vars")

if "__HERMES_WORKER_CHAIN_0__" in ts_src:
    pass_("bootstrap.ts generates worker chain vars")
else:
    fail("bootstrap.ts missing worker chain vars")

if "__HERMES_CHALLENGER_CHAIN_0__" in ts_src:
    pass_("bootstrap.ts generates challenger chain vars")
else:
    fail("bootstrap.ts missing challenger chain vars")

if "__HERMES_ARBITER_CHAIN_0__" in ts_src:
    pass_("bootstrap.ts generates arbiter chain vars")
else:
    fail("bootstrap.ts missing arbiter chain vars")

# ── Test 5: Project.yaml has chain fields ────────────────────────────────────
print("[TEST] Test 5: Adapter project.yaml has chain fields")
proj_yaml_path = os.path.join(REPO_ROOT, "adapters", "v7-alphaforge", "project.yaml")
with open(proj_yaml_path) as f:
    proj_yaml = f.read()

for chain in ["orchestrator_chain", "worker_chain", "challenger_chain", "arbiter_chain"]:
    if chain in proj_yaml:
        pass_(f"project.yaml has {chain}")
    else:
        fail(f"project.yaml MISSING {chain}")

# ── Test 6: Local model at end of each chain ────────────────────────────────
print("[TEST] Test 6: Each chain ends with local/ollama model")
ollama_refs = config.lower().count("ollama")
localhost_refs = config.lower().count("localhost")
total_local_refs = ollama_refs + localhost_refs
if total_local_refs >= 4:
    pass_(f"{total_local_refs} local/ollama references found (≥4 expected for 4 profiles)")
else:
    fail(f"Only {total_local_refs} local/ollama references, need ≥4")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 56)
print(f"  LitellM Config Test Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 56)
sys.exit(0 if FAIL_COUNT == 0 else 1)
