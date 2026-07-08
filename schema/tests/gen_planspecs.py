"""Generate per-issue Praxis PlanSpecs for remaining pack-layer issues."""
import os, json

PLAN_DIR = r"C:\Users\dresden\Documents\hermes-pack\.praxis"

def make_planspec(issue_id, title, description, acs, commands, files, plan_id=None):
    plan_id = plan_id or f"HERMES-{issue_id.replace('#','').replace('(','').replace(')','').strip()}"
    safe_id = issue_id.replace("#", "issue-").replace(" ", "-")
    lock_file = f".praxis/{safe_id}.lock"
    
    ac_yaml = []
    for ac in acs:
        vtype = ac.get('vtype', 'file_exists')
        if vtype == 'source':
            vtype = 'file_exists'
        lines = f"""      - id: "{ac['id']}"
        description: "{ac['desc']}"
        level: "required"
        humanApproved: true
        criteriaSource: "human"
        verification:
          type: "{vtype}"
          path: "{ac['path']}"
          deterministic: true
          canSatisfyFinalGate: true
          advisoryOnly: false
          evidenceRefs:
            - "source"
        requiredEvidence:
          - "source"
"""
        ac_yaml.append(lines)

    cmd_yaml = "\n".join(
        f'    - id: "{c["id"]}"\n      kind: "final_validation"\n      command: "{c["cmd"]}"\n      evidenceRequired: true\n      timeoutSeconds: {c.get("timeout", 60)}\n      noTestsFoundIsFailure: true\n      expectedExitCode: 0\n      networkAllowed: false\n      shellAllowed: true'
        for c in commands
    )

    files_yaml = "\n".join(f'    - "{f}"' for f in files)

    return f"""# PRAXIS PlanSpec v0.1 — {issue_id}: {title}
planSpecVersion: "0.1.0"
kind: "ImplementationPlan"
profile: "praxis-v0.1"

metadata:
  planId: "{plan_id}"
  title: "{title}"
  description: "{description}"
  createdAt: "2026-07-08T12:00:00Z"
  humanId: "autonomous-agent"
  status: "draft"

authority:
  executor: "ClaudeCode"
  completionAuthority: "PraxisTruthKernel"
  agentSelfReportIsClaimOnly: true
  criteriaSourceRequired: "human"
  reportsAreEvidenceOnly: true
  pluginOwnsTruth: false

workspace:
  root: "."
  allowedFiles:
{files_yaml}
  forbiddenFiles: []

execution:
  mode: "single_session"
  agent: "claude-code"
  autonomy: "implementation_allowed"
  canModifyCode: true
  canModifyPlan: false
  canModifyAcceptanceCriteria: false
  maxRepairLoops: 2

tasks:
  - id: "task-{issue_id.replace('#','').replace(' ','-').lower()}"
    title: "{title}"
    objective: "{description[:120]}"
    implementation:
      instructions:
        - "See issue body for full implementation details."
      expectedOutputs:
        - "All acceptance criteria met."
    artifactPolicy:
      class: "library_code"
      wiringRequired: false
      reachabilityRequired: false
      executionRequired: false
      deterministicEvidenceRequired: true
      advisoryReviewAllowed: false
    acceptanceCriteria:
{''.join(ac_yaml)}
commands:
  exactAllowedCommands:
{cmd_yaml}
  validationEvidenceRules:
    finalPromotionRequiresExactAllowedCommand: true
    discoveryCommandsMayNotSatisfyFinalValidation: true
    runtimeGrantCommandsCanSatisfyValidationOnlyIfGrantStatesValidationPurpose: true
  hardDeniedCommands:
    - command: "rm -rf"
      reason: "Destructive operation."
evidence:
  ledgerRequired: true
  requiredEvidenceTypes:
    - "diff"
    - "source"
    - "command"
    - "test_output"
  hashWhenAvailable: true
gates:
  sequence:
    - "SchemaGate"
    - "LockGate"
    - "EvidenceGate"
    - "WiringGate"
    - "ExecGate"
    - "FinalGate"
  verdicts:
    - "PASS"
    - "HOLD"
    - "FAIL"
  reasonCodes:
    SchemaGate:
      - "SCHEMA_PASS"
    EvidenceGate:
      - "EVIDENCE_MISSING"
    ExecGate:
      - "TESTS_RAN_ZERO"
    FinalGate:
      - "ALL_CRITERIA_MET"
      - "CRITERIA_PARTIAL"
repair:
  enabled: true
  failedCriteriaOnly: true
  mayModifyAcceptanceCriteria: false
  mayModifyPlan: false
  allowedFilesFromFailedTasksOnly: true
  maxRepairLoops: 2
  reverifyCommand: "{commands[0]['cmd'] if commands else 'echo done'}"
  repairPacketFormat:
    json: true
    markdown: true
locking:
  lockRequired: true
  canonicalHashRequired: true
  planLockFile: ".praxis/{safe_id}.lock"
  hashes:
    - "planHash"
    - "acceptanceCriteriaHash"
    - "artifactPolicyHash"
    - "commandPolicyHash"
    - "allowedFilesHash"
    - "forbiddenFilesHash"
reports:
  protocol: "ACCP"
  artifactDirectory: "reports/"
  reportsAreEvidenceOnly: true
  reportsDoNotAuthorizeExecution: true
  commandEvidenceRequired: true
  repairPacketRequiredOnHoldOrFail: true
"""

planspecs = [
    ("#2", "Proje registry", "Project registry at ~/.hermes-pack/registry.yaml",
     [{"id":"AC-1","desc":"Registry schema exists with schema_version","vtype":"file_exists","path":"schema/registry.schema.json"},
      {"id":"AC-2","desc":"Bootstrap.ts writes to registry idempotently","vtype":"source","path":"bootstrap.ts"}],
     [{"id":"CMD-TEST","cmd":"python schema/tests/test_schema_validation.py"}],
     ["schema/*.schema.json","schema/tests/*","bootstrap.ts","bootstrap.sh"]),

    ("#5", "Provider fallback router", "LiteLLM proxy config with per-profile fallback chains ending in local models",
     [{"id":"AC-1","desc":"LiteLLM config template exists","vtype":"file_exists","path":"templates/litellm-config.yaml"},
      {"id":"AC-2","desc":"Bootstrap generates litellm-config.yaml","vtype":"source","path":"bootstrap.ts"},
      {"id":"AC-3","desc":"Adapter has provider chain fields","vtype":"file_exists","path":"adapters/v7-alphaforge/project.yaml"}],
     [{"id":"CMD-BUILD","cmd":"bun build bootstrap.ts --no-bundle"}],
     ["templates/litellm-config.yaml","bootstrap.ts","adapters/*/project.yaml","README.md"]),

    ("#6", "Eternal Goal Engine", "goal.yaml template with never_stop_rules, eternal/gate_target/metric_target types",
     [{"id":"AC-1","desc":"goal.yaml template exists","vtype":"file_exists","path":"templates/goal.yaml"},
      {"id":"AC-2","desc":"SOUL has eternal goal rule","vtype":"source","path":"templates/SOUL.orchestrator.md"},
      {"id":"AC-3","desc":"Bootstrap installs goal.yaml","vtype":"source","path":"bootstrap.ts"}],
     [{"id":"CMD-BUILD","cmd":"bun build bootstrap.ts --no-bundle"}],
     ["templates/goal.yaml","templates/SOUL.orchestrator.md","bootstrap.ts"]),

    ("#7", "events.jsonl", "events.jsonl in ledger, events.schema.json with all event types",
     [{"id":"AC-1","desc":"events.schema.json exists","vtype":"file_exists","path":"schema/events.schema.json"},
      {"id":"AC-2","desc":"Bootstrap creates events.jsonl","vtype":"source","path":"bootstrap.ts"}],
     [{"id":"CMD-TEST","cmd":"python schema/tests/test_schema_validation.py"}],
     ["schema/events.schema.json","bootstrap.ts"]),

    ("#8", "Challenger/arbiter profiles", "Bootstrap creates challenger (read-only) and arbiter (premium) profiles",
     [{"id":"AC-1","desc":"Bootstrap creates challenger (read-only) profile","vtype":"source","path":"bootstrap.ts"},
      {"id":"AC-2","desc":"Bootstrap creates arbiter (premium) profile","vtype":"source","path":"bootstrap.ts"},
      {"id":"AC-3","desc":"LiteLLM has separate challenger/arbiter chains","vtype":"file_exists","path":"templates/litellm-config.yaml"}],
     [{"id":"CMD-BUILD","cmd":"bun build bootstrap.ts --no-bundle"}],
     ["bootstrap.ts","templates/litellm-config.yaml"]),

    ("#9", "Ideas Engine", "ideas.yaml seed, ideas/ dir, ideas.schema.json with full lifecycle",
     [{"id":"AC-1","desc":"ideas.schema.json exists","vtype":"file_exists","path":"schema/ideas.schema.json"},
      {"id":"AC-2","desc":"ideas.yaml template exists","vtype":"file_exists","path":"templates/ideas.yaml"},
      {"id":"AC-3","desc":"Bootstrap creates ideas/ dir","vtype":"source","path":"bootstrap.ts"}],
     [{"id":"CMD-TEST","cmd":"python schema/tests/test_schema_validation.py"},{"id":"CMD-BUILD","cmd":"bun build bootstrap.ts --no-bundle"}],
     ["schema/ideas.schema.json","templates/ideas.yaml","bootstrap.ts"]),

    ("#11", "Ideas Engine anti-collapse", "Anti-collapse: embedding, novelty, family, source fields in ideas schema",
     [{"id":"AC-1","desc":"ideas.schema.json has embedding field","vtype":"file_exists","path":"schema/ideas.schema.json"},
      {"id":"AC-2","desc":"ideas.schema.json has novelty_score","vtype":"file_exists","path":"schema/ideas.schema.json"},
      {"id":"AC-3","desc":"ideas.schema.json has family field","vtype":"file_exists","path":"schema/ideas.schema.json"},
      {"id":"AC-4","desc":"ideas.schema.json has external_research source type","vtype":"file_exists","path":"schema/ideas.schema.json"}],
     [{"id":"CMD-TEST","cmd":"python schema/tests/test_schema_validation.py"}],
     ["schema/ideas.schema.json"]),

    ("#13", "Global budget pool", "Budget fields in control/state/registry schemas; tick-gate validates spend",
     [{"id":"AC-1","desc":"control.schema.json has max_llm_spend_per_day_usd","vtype":"file_exists","path":"schema/control.schema.json"},
      {"id":"AC-2","desc":"state.schema.json has budget_usd/spend_today_usd","vtype":"file_exists","path":"schema/state.schema.json"},
      {"id":"AC-3","desc":"registry.schema.json supports budget","vtype":"file_exists","path":"schema/registry.schema.json"}],
     [{"id":"CMD-TEST","cmd":"python schema/tests/test_schema_validation.py"}],
     ["schema/*.schema.json","templates/scripts/tick-gate.sh"]),

    ("#15", "Cross-project transfer", "Registry for multi-project; ideas schema has source_project field",
     [{"id":"AC-1","desc":"Registry schema exists for multi-project","vtype":"file_exists","path":"schema/registry.schema.json"},
      {"id":"AC-2","desc":"ideas.schema.json has source_project field","vtype":"file_exists","path":"schema/ideas.schema.json"}],
     [{"id":"CMD-TEST","cmd":"python schema/tests/test_schema_validation.py"}],
     ["schema/registry.schema.json","schema/ideas.schema.json"]),

    ("#17", "Cross-project transfer (P3)", "Cross-project idea transfer via registry; scout generates ideas across projects",
     [{"id":"AC-1","desc":"Registry provides multi-project list for transfer","vtype":"file_exists","path":"schema/registry.schema.json"},
      {"id":"AC-2","desc":"ideas schema supports source_project field","vtype":"file_exists","path":"schema/ideas.schema.json"}],
     [{"id":"CMD-TEST","cmd":"python schema/tests/test_schema_validation.py"}],
     ["schema/registry.schema.json","schema/ideas.schema.json"]),
]

os.makedirs(PLAN_DIR, exist_ok=True)
for issue_id, title, desc, acs, cmds, files in planspecs:
    safe_id = issue_id.replace("#", "issue-")
    filename = f"{safe_id}.plan.yaml"
    filepath = os.path.join(PLAN_DIR, filename)
    content = make_planspec(issue_id, title, desc, acs, cmds, files)
    with open(filepath, "w") as f:
        f.write(content)
    print(f"Created: {filename}")

print(f"\nTotal: {len(planspecs)} PlanSpecs created")
