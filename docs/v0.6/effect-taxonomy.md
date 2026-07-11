# Effect Taxonomy Contract (A-1)

**Issue:** #76 (Track A, P0)
**Status:** Accepted — v0.6
**Consumed by:** BE-1 (candidate manifest), BE-2 (Promotion Engine), GA-1 (AFK autonomy gate), gate #15 (Effect honesty)

## 1. What this contract locks

A required `effect_class` field on every candidate manifest, drawn from a closed
enum of three values:

| Value | Meaning | AFK T4 may auto-promote? |
|---|---|---|
| `reversible_internal` | Change stays inside the Hermes/Hephaestus surface (beliefs, hypotheses, internal pointers, derived state). No external side effect, no human-visible artifact. | **Yes**, with standing policy + Praxis pass. |
| `compensable_external` | Change touches an external surface (push a comment, open a PR, write a non-canonical file in a user repo, send a draft email) but is reversible in practice (PR closed, email recalled, file reverted) and a `compensation_plan` is recorded before promotion. | **No** without a documented `compensation_plan` *and* an explicit standing policy reference. With both, a T4 in `AFK_AUTONOMOUS` mode may promote. |
| `irreversible_external` | Change that cannot be undone by Hephaestus (sending a real email, executing a real trade, deleting a resource, closing a paid account, publishing a public post). | **Never.** `human_always: true` is enforced for this class by the schema and per-adapter `project.yaml`; this is a kept invariant, not a new one. |

## 2. Rule statement (verbatim, normative)

> A T4 running in any mode may PROMOTE a candidate only if its `effect_class`
> is `reversible_internal`, or — for `compensable_external` — both
> `compensation_plan` (non-empty) and `standing_policy` (non-empty, adapter-
> scoped) are present. `irreversible_external` is reserved for human execution;
> the schema field `human_always: true` and any per-adapter setting of the
> same name remain **in force** for this class and must not be weakened.

## 3. Why this is P0 (design-lock audit finding F1)

The v0.6 AFK autonomy argument ("reversible autonomy is safe autonomy") is
**only** defensible if the system can prove at promotion time which side
effects a candidate will have. Without `effect_class` on the manifest, the
Promotion Engine has no signal to distinguish "writes a new belief" from
"sends a real email to a real address" — and the safety story collapses
into a vibes-based gate, not an evidence-based one.

## 4. Manifest field schema (consumed by BE-1)

```jsonc
{
  "candidate_id": "cand_…",
  "asset_type": "belief | config | code | db | …",
  "effect_class": "reversible_internal | compensable_external | irreversible_external",  // REQUIRED
  "compensation_plan": {  // REQUIRED iff effect_class == compensable_external
    "compensator": "<role or component name>",
    "steps": ["…", "…"],
    "max_window_minutes": 60
  },
  "standing_policy": "policy://…",   // REQUIRED iff effect_class != reversible_internal
  "human_always": true                // REQUIRED and MUST be true iff effect_class == irreversible_external
}
```

**Validation:** `effect_class` is required; the schema rejects the candidate
at ingest time if missing. `compensation_plan` and `standing_policy` are
required exactly when the rules above say so; absent them, the Promotion
Engine refuses with `reason: effect_class_policy_violation`.

## 5. Interaction with existing surfaces

- `schema/control.schema.json` — the enum value is added; `human_always`
  stays as a top-level field and is *additionally* enforced when
  `effect_class == irreversible_external`.
- `adapters/*/project.yaml` — per-adapter `human_always: true` (already set
  on the v7-alphaforge adapter) is the per-adapter override and is preserved.
  No adapter is allowed to set `human_always: false` for an
  `irreversible_external` candidate. The Promotion Engine fails-closed on
  this.
- `templates/scripts/containment-engine.py` — adds an `effect-class-check`
  command that the gate #15 verifier calls per candidate at promotion time.

## 6. Effect-class assignment rules (deterministic)

The Reflector (in v0.5) and the Promotion Engine (in v0.6) must apply the
same default-class table to a candidate, derived from `asset_type` and
proposed `target`. Defaults are conservative — i.e. if a candidate's actual
effects could span classes, the **higher-class wins** (irreversible >
compensable > reversible). Adapters may tighten an asset-type's default up
the scale but never loosen it down.

| `asset_type` | Default `effect_class` | Notes |
|---|---|---|
| `belief` | `reversible_internal` | Beliefs are workspace-resident. |
| `hypothesis` | `reversible_internal` | Hypotheses are workspace-resident. |
| `config` (Hephaestus internal) | `reversible_internal` | Internal config files. |
| `code` (PR opened) | `compensable_external` | PR can be closed. |
| `code` (auto-merge) | `compensable_external` | Merge can be reverted. |
| `db` (view/pointer switch) | `reversible_internal` | Pointer is reversible. |
| `db` (DDL with destructive migration) | `irreversible_external` | Schema change is not auto-reversible. |
| `external.email` | `irreversible_external` | Always human. |
| `external.publish` | `irreversible_external` | Always human. |

## 7. Failure modes & how the engine reacts

- **Missing `effect_class` on ingest** → schema reject at BE-1.
- **`effect_class == irreversible_external` and T4 is in `AFK_AUTONOMOUS`** →
  Promotion Engine refuses; gate #15 fails; orchestrator emits
  `park_reason: effect_class_irreversible` and the candidate is held
  pending human.
- **`effect_class == compensable_external` without `compensation_plan`** →
  Promotion Engine refuses; gate #15 fails; orchestrator emits
  `park_reason: missing_compensation_plan`.
- **Adapter override says `human_always: false` for an
  `irreversible_external` candidate** → Promotion Engine fails-closed;
  the adapter file is treated as a misconfiguration and the engine
  logs a `config_violation` audit event.

## 8. Test fixtures (gating evidence for #15)

- `templates/tests/effect_class_reversible_ok.json` — passes promotion in
  `AFK_AUTONOMOUS` mode.
- `templates/tests/effect_class_compensable_no_plan.json` — fails
  promotion with `missing_compensation_plan`.
- `templates/tests/effect_class_irreversible_in_afk.json` — fails
  promotion with `effect_class_irreversible`, candidate held.
- `templates/tests/effect_class_adapter_override_misconfigured.json` —
  fails promotion with `config_violation` and does not weaken
  `human_always`.

## 9. Out of scope for A-1

- The actual Promotion Engine implementation (BE-2).
- The AFK flag plumbing (GA-1).
- The gate #15 verifier implementation (sits in `containment-engine.py`,
  delivered as a follow-up when BE-2 lands).

## 10. Completion gate

This contract is the design-time half of gate #15 ("Effect honesty"). It
is accepted only when BE-2's promotion path enforces it on the runtime
side; until then it is documentation only and the AFK gate (GA-1) must
not be opened.
