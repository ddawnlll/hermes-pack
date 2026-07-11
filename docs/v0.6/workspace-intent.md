# Workspace Intent Contract (A-2)

**Issue:** #77 (Track A, P1)
**Status:** Accepted — v0.6
**Consumed by:** BE-1 (#82), BE-2 (#85), CP-3 (#91)
**Completion gates:** #10 (Human override applies next tick), #11 (Shared workspace)
**Why:** Design-lock audit finding F2 (P1)

## 1. What this contract locks

`beliefs.yaml` (introduced in #56, merged) gets a new ownership model for v0.6:

- **Single physical writer**: Orchestrator core (deterministic intent-applier) is the only process that writes `beliefs.yaml`.
- **Typed intents**: All other actors (Reflector, T4, human via Cockpit) append typed intents to `workspace_intents.jsonl`. The Orchestrator consumes the stream and applies each intent in priority order.
- **Priority order**: `human > T4 > Reflector`. A higher-priority intent overrides a lower-priority one if they target the same belief in the same tick. Lower-priority intents are logged as `shadowed` in the tick journal — they are not lost, but they are not applied.

## 2. Rule (verbatim, normative)

> The Orchestrator core is the sole physical writer to `beliefs.yaml`. All
> mutations to the belief set flow as typed intents appended to
> `workspace_intents.jsonl`. The Orchestrator consumes the intent stream at
> each tick start and applies each intent in priority order
> (`human < T4 < Reflector` numerically; `0 = human, 1 = T4, 2 = Reflector`).
> A human PIN or EVICT intent applies unconditionally at the next tick
> start regardless of evidence; this is the defined exception to #63's
> eviction-evidence requirement and is logged as `evicted_by: human` in
> `beliefs-evictions.jsonl`.

## 3. Why this is P1 (audit finding F2)

#56 says "Written by: Reflector ONLY" but the v0.6 cockpit needs humans and T4 to PIN, MARK_SUSPECT, and EVICT beliefs directly through the Cockpit UI (CP-3). Two uncoordinated writers to a 12-slot capacity-capped workspace produces silent data loss: a low-priority Reflector eviction can wipe a human PIN before the human's intent is observed.

This contract resolves the collision **without breaking single-writer**: the Orchestrator remains the only writer; everyone else submits intents. The intents are then deterministically ordered by priority and applied.

## 4. Typed intent schema (consumed by BE work + CP-3)

```jsonc
{
  "intent_id": "uuid",                        // unique per intent
  "tick_id": <number>,                        // tick the intent was emitted in
  "actor": "human | t4 | reflector",
  "priority": 0 | 1 | 2,                      // 0=human, 1=T4, 2=Reflector
  "operation": "PIN | EVICT | MARK_SUSPECT | ADD_WHISPER | UNMARK_SUSPECT",
  "target": "<belief_id>",                    // belief being acted on
  "evidence": "...",                          // free-form, required for EVICT unless actor=human
  "timestamp": "ISO-8601",                    // intent emission time
  "applied": true | false,                    // set by Orchestrator after apply
  "shadowed_by": "<intent_id>"                // set if a higher-priority intent overrode this one
}
```

`workspace_intents.jsonl` is append-only. Each line is one intent. The Orchestrator
processes intents in `(tick_id asc, priority asc, intent_id asc)` order to guarantee
determinism.

## 5. Human override exception

A human PIN or EVICT intent applies at the next tick start regardless of evidence
requirements. This is the explicit, named exception to #63's eviction-evidence rule.
The Orchestrator logs each human override in `beliefs-evictions.jsonl`:

```json
{
  "belief_id": "...",
  "evicted_by": "human",
  "intent_id": "...",
  "tick_id": <number>,
  "timestamp": "ISO-8601",
  "reason": "human override (A-2)"
}
```

## 6. Failure modes

- **Intent queue overflow** (capacity = 12 beliefs, but intent queue is unbounded): if the same belief receives more than one EVICT intent in the same tick, the highest-priority one wins; the rest are `shadowed`.
- **Conflicting intents on different beliefs**: independent; no collision.
- **Reflector writes beliefs directly** (regression of #56's invariant): the Orchestrator detects this on the next tick (file hash mismatch) and pauses the system with a `pause_reason: writer_invariant_violated` flag, escalating to human.

## 7. Consumed by

- **BE-1** (#82): candidate manifest may reference belief state.
- **BE-2** (#85): Promotion Engine reads `beliefs.yaml` for candidate context; mutations only via Orchestrator.
- **CP-3** (#91): Cockpit intervention grammar wiring — sends typed intents (not direct writes).
- **Orchestrator core**: applies intents in priority order; only physical writer.

## 8. Gates satisfied

- **Gate #10** (Human override applies next tick): human PIN/EVICT unconditional, no evidence wait, applied at next tick start.
- **Gate #11** (Shared workspace): cockpit + T4 + Orchestrator observe the same state because all writes route through the Orchestrator's intent queue (see also CP-6 local realtime adapter).

## 9. Reference

- #56 (merged): beliefs.yaml initial writer model
- #63 (merged): eviction-evidence requirement
- Design-lock audit finding F2 (P1)
- `templates/beliefs.yaml` (268B) — file format reference
- CP-6 (#94): local realtime adapter, the transport for intents from cockpit to Orchestrator
