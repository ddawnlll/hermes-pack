# Promotion Mechanism Table (A-3)

**Issue:** #78 (Track A, P1)
**Status:** Accepted — v0.6
**Consumed by:** BE-1 (#82), BE-2 (#85), GA-1 (#99)
**Completion gates:** #3 (Candidate-only mutation), #5 (Atomic promotion)
**Why:** Design-lock audit finding F3 (P1)
**Depends on:** A-1 (effect_class) — `effect_class` informs which mechanism is allowed to run unattended

## 1. What this contract locks

An asset-type → promotion mechanism table. For each asset type, a deterministic mechanism executes the promotion, plus a `merge_policy` enum that the Promotion Engine (BE-2) reads.

## 2. Promotion mechanism table

| `asset_type` | Promotion mechanism | Notes |
|---|---|---|
| `code` | Auto-merged PR — PR is opened for **audit trail** (record of intent, scope, and target), but the merge is executed by the Promotion Engine once preconditions PASS, not by a human clicking "merge". | Audit trail invariant: every code promotion leaves a PR with intent metadata, even if merged unattended. |
| `config` | Pointer switch — atomic swap of a config file pointer (e.g. beliefs.yaml → beliefs.yaml.next), no in-place mutation. | Pointer is replaced by a single `rename(2)`; readers either see old or new, never a partial file. |
| `db` | Schema/view switch — new schema/view becomes canonical via a `pg_class` swap or `CREATE VIEW … WITH (security_invoker)` redirection. | Old schema retained for rollback window (7 days default). |
| `belief` | Status transition — belief `state` field transitions through DRAFT → EVALUATING → … → PROMOTED via Orchestrator; journal entry appended. | No file pointer swap; mutation is in the belief record itself. |

## 3. `merge_policy` enum bump

**Old value** (pre-v0.6, current in `schema/control.schema.json`, `tick.md`, `control.yaml`, `project.yaml`):

```yaml
merge_policy: pr_only   # every merge waits for a human to click "merge" on the PR
```

**New value** (v0.6):

```yaml
merge_policy: pr_gated_auto   # PR opens for audit, merge executes once preconditions PASS
```

### When `pr_gated_auto` is allowed

A Promotion Engine gate may execute the merge unattended if **all** of the following hold:

1. `effect_class` ∈ {`reversible_internal`, `compensable_external`} (from A-1 #76). `irreversible_external` is **never** auto-merged, even with `pr_gated_auto`.
2. For `compensable_external`: a non-empty `compensation_plan` AND a non-empty `standing_policy` reference are present on the candidate manifest.
3. `human_always: true` is **not** set on the candidate (A-1 invariant — only `irreversible_external` carries it).
4. The preconditions in `promotion-engine.py` (BE-2 #85) all PASS: `base_state_current` (A-5 #80), kill/pause/freeze clear, lock acquired.
5. The decision is recorded in `tick-journal.py` with `merge_policy: pr_gated_auto` and the relevant `precondition_evidence` (for audit).

### When `pr_only` is still required

`pr_only` remains the **default** for any case that does not satisfy the above five conditions. Operators can also force `pr_only` per candidate (override) via Cockpit.

## 4. Schema bump (consumed by BE-1)

`schema/control.schema.json` gains:

```jsonc
{
  "merge_policy": {
    "type": "string",
    "enum": ["pr_only", "pr_gated_auto"],
    "default": "pr_only",
    "description": "Promotion Engine gate behavior. pr_gated_auto requires effect_class != irreversible_external AND a non-empty compensation_plan for compensable_external candidates."
  }
}
```

Per-adapter `project.yaml` files (e.g. `adapters/v7-alphaforge/project.yaml`) are bumped to allow `pr_gated_auto` per asset_type.

## 5. Consumed by

- **BE-1** (#82): candidate manifest schema — `merge_policy` field, asset_type-driven mechanism choice.
- **BE-2** (#85): Promotion Engine — reads `merge_policy` and runs the corresponding mechanism.
- **GA-1** (#99): AFK autonomy feature-flag — `pr_gated_auto` is the path AFK T4 uses; `pr_only` is a hard AFK block.
- **A-1** (#76): effect_class gates which `merge_policy` is even legal per candidate.

## 6. Why this is P1 (audit finding F3)

`merge_policy: pr_only` (pre-v0.6 wording) and v0.6's atomic-pointer-switch promotion are two different, uncoordinated mutation models. AFK autonomy needs *something* to execute a merge without a human clicking a button, but `pr_only` as currently worded forbids that. The enum bump resolves the conflict by introducing a second, gated mode that is **only** active when safety preconditions (effect_class, compensation_plan, kill/pause/freeze) are met. `pr_only` is **not** removed — it remains the safe default and the only legal option for `irreversible_external`.

## 7. Failure modes

- **Precondition PASS, but human override pending**: the Cockpit attention queue (CP-2 #90) surfaces a "human override window" item for `compensable_external` candidates even when the gate would auto-merge; the override is honored if it arrives before the merge is executed.
- **Lock contention with another promotion**: BE-2's global promotion serialization (A-5 #80) queues; the auto-merge waits. No double-merge possible.
- **Schema/view swap fails after pointer switch**: BE-3 (#86) rollback pointer restores the previous canonical; candidate → ROLLED_BACK.

## 8. Gates satisfied

- **Gate #3** (Candidate-only mutation): every promotion flows through the candidate manifest; the mechanism is selected per asset_type, not per actor.
- **Gate #5** (Atomic promotion): pointer switch + `pg_class` swap are atomic; merge happens once preconditions PASS or does not happen at all.

## 9. Reference

- Design-lock audit finding F3 (P1)
- A-1 (#76): Effect Taxonomy
- A-5 (#80): Candidate Concurrency (lock scope)
- `schema/control.schema.json` (3.5K) — current schema
- `templates/control.yaml` (619B) — current control file
