# Schemas

All stateful data in Hephaestus follows a **versioned JSON Schema** contract. Every
schema lives in `schema/`, has a `schema_version` field, and is validated by the
tick gate before any LLM wakes.

## Current schemas

| Schema | File | Added | Purpose |
|---|---|---|---|
| **State** | `state.schema.json` | v0.1 | Orchestrator state.json — tick counters, worker status, budget, gate counters, **v2: beliefs summary, features, channel budgets, calibration, run/phase** |
| **Control** | `control.schema.json` | v0.1 | Control plane — mode, paths, budget, risk gating |
| **Goal** | `goal.schema.json` | v0.1 | Eternal/metric/gate_target goal definition with success criteria |
| **Ideas** | `ideas.schema.json` | v0.1 | Idea lifecycle — spark, triage, hypothesis, verdict |
| **Events** | `events.schema.json` | v0.1 | Append-only event log — tick/worker/gate/budget events |
| **Beliefs** | `beliefs.schema.json` | v0.5 | Narrow, capacity-limited workspace (GWT core) — maxItems 12, kill_criterion, blamed_by |
| **Hypothesis** | `hypothesis.schema.json` | v0.5 | Mandatory `relies_on` and `provenance` fields |
| **Provenance** | `provenance.schema.json` | v0.5 | Channel tracking — elimination/analogy/replay/whisper/external/relaxation |

All schemas have `$id` URLs pointing to the repo path for stable referencing.

## Schema version bump procedure

When making backward-incompatible changes to any schema:

1. **Increment `schema_version`** in the affected schema file(s) — e.g., `1 → 2`.
2. **Create a migration script** `migrate-ledger-<from>to<to>.sh` or update
   `migrate-ledger.sh` with a version router.
3. **Update templates** — `templates/state.json`, `templates/control.yaml`,
   `templates/goal.yaml`, `templates/ideas.yaml`, `templates/beliefs.yaml`,
   `templates/hypothesis.yaml` to match the new schema.
4. **Update `tick-gate.sh`** if the validation logic needs updating for the new fields.
5. **Update the tick prompt** at `templates/prompts/tick.md` if schema changes affect
   orchestrator behavior.
6. **Run the test suite:** `python3 schema/tests/test_schema_validation.py`.
7. **Document the change** in the schema file's `description` field and in the commit
   message.

!!! tip "Backward-compatible additions don't need a bump"
    New optional fields, wider enums — do update templates and tests, but no schema
    version bump or migration script is required.

## Validation gate

The pre-tick gate (`templates/scripts/tick-gate.sh`) validates `state.json` against
`state.schema.json` before waking the orchestrator. If validation fails, the gate emits:

```json
{"wakeAgent": false, "error": "state.json failed schema validation"}
```

The LLM never reads or writes garbage state.

## Migration

Use `migrate-ledger.sh` to convert v1 ledger state to v2 (or v2 to v3, etc.):

```bash
bash migrate-ledger.sh .alphaforge/orchestrator/state.json --backup
```

The `--backup` flag creates a `.bak` copy before mutation. The script auto-detects
the source version and applies the correct migration path.

## Schema examples

### State (v2)

```json
{
  "schema_version": 2,
  "tick": 47,
  "mode": "running",
  "budget_usd": 25.0,
  "spend_today_usd": 3.42,
  "curiosity_budget_usd": 5.0,
  "channel_spend_today": {
    "analogy": 0.12,
    "whisper": 0.04,
    "calibration": 0.08
  },
  "beliefs_summary": {
    "active": 8,
    "suspect": 1,
    "evicted_total": 3
  },
  "stagnation": 0.14,
  "momentum": 3,
  "current_run": {
    "run_id": "uuid",
    "phase": "dispatch",
    "status": "running"
  }
}
```

### Hypothesis (v0.5)

```json
{
  "schema_version": 1,
  "id": "H-042",
  "statement": "Volatility regime shift at 14:30 UTC predicts 15m direction",
  "metric": "sharpe",
  "threshold": 1.4,
  "direction": ">=",
  "relies_on": ["B-007", "B-003"],
  "provenance": "elimination",
  "status": "hypothesis"
}
```

!!! warning "`relies_on` is required"
    From v0.5 forward. May be empty `[]` but must be present. The pre-registration lock
    hashes this field, so changing it after dispatch is a LockGate FAIL.

### Belief (v0.5)

```json
{
  "schema_version": 1,
  "id": "B-007",
  "statement": "Current dataset has sufficient statistical power for sharpe>=1.4",
  "confidence": 0.35,
  "blamed_by": ["H-012", "H-015"],
  "tested_directly": false,
  "suspect": false,
  "kill_criterion": "Sharpe < 1.0 across 200+ hypotheses in any 30-day window",
  "evicted_at": null,
  "eviction_evidence": null
}
```

## Reference

- All schemas: [`schema/`](https://github.com/ddawnlll/hephaestus/tree/main/schema)
- Test suite: [`schema/tests/`](https://github.com/ddawnlll/hephaestus/tree/main/schema/tests)
- Migration script: [`migrate-ledger.sh`](https://github.com/ddawnlll/hephaestus/blob/main/migrate-ledger.sh)
