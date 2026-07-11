# Candidate Concurrency Contract (A-5)

**Issue:** #80 (Track A, P1)
**Status:** Accepted — v0.6
**Consumed by:** BE-1 (#82), BE-2 (#85)
**Completion gate:** #16 (Rebase safety)
**Why:** Design-lock audit finding F5 (P1) — without a freshness check, multiple candidates can produce silent lost-update bugs.
**Builds on:** A-3 (#78) — defines what "promotion" atomically means before defining concurrency around it.

## 1. What this contract locks

Three rules that together eliminate the lost-update class of bugs the v0.6 cockpit would otherwise expose:

1. **`base_state_current` precondition** — every promotion's base must still equal the current active state at promotion time.
2. **`REBASE_REQUIRED` lifecycle state** — candidates whose base has shifted out from under them move to a new state and stop trying to promote.
3. **Global promotion serialization** — exactly one promotion runs in the engine at any moment, with a lock scope that covers the full decision + freshness-check + switch sequence.

## 2. `base_state_current` precondition (rule, normative)

> At the moment the Promotion Engine (BE-2 #85) takes the global promotion lock for a candidate, it MUST verify that `candidate.base_state_hash == current_active_state.hash`. If they differ, the candidate MUST transition to `REBASE_REQUIRED` (per §3) and the promotion MUST abort. No retry, no override — the candidate must be re-authored against the new base.

The base state hash is computed over the canonical fields the candidate depends on (per `asset_type`, see A-3 #78 §2). For `code`, this is the target ref + base commit SHA. For `config`, this is the canonical config hash. For `db`, this is the schema version. For `belief`, this is the belief state at intent time.

## 3. `REBASE_REQUIRED` lifecycle state

A new state in the candidate lifecycle (consumed by BE-1 #82 schema):

```
DRAFT → EVALUATING → REBASE_REQUIRED
              ↓
           QUEUED → PROMOTING → PROMOTED
              ↓         ↓
           FAILED   ROLLED_BACK
              ↓
           DEAD (terminal failure, requires re-author)
```

### Behavior of `REBASE_REQUIRED`

- The candidate does **not** block other candidates. It is removed from the active promotion queue (Gate #14, no global stall).
- The candidate is surfaced in the Cockpit candidate pipeline view (CP-5 #93) as a card in the `REBASE_REQUIRED` column.
- A human can drag-to-rebase the candidate (CP-5 interaction) — this recomputes the base and transitions the candidate back to `DRAFT`.
- An autonomous T4 may not rebase. Only humans (or a human-approved policy) can rebase.
- The transition to `REBASE_REQUIRED` is logged in `tick-journal.py` with `reason: base_state_drift`.

## 4. Global promotion serialization

**Statement (verbatim, normative):**

> The Promotion Engine admits exactly **one** candidate into the active promotion pipeline at any moment. The lock scope covers (a) the decision to admit, (b) the `base_state_current` check, and (c) the atomic switch. No other promotion may run, and no other candidate's `base_state_current` check may be evaluated, while the lock is held. The lock is released on PROMOTED, ROLLED_BACK, FAILED, or DEAD.

### Why a single global lock (not per-candidate)

A per-candidate lock would not protect against the case where two candidates claim the same base state and one of them moves the active pointer between the other's check and switch. The single global lock makes the check-and-switch atomic from the system's perspective.

### Why this does not produce global stall (Gate #14)

A candidate in `REBASE_REQUIRED` does **not** hold the global lock; it is removed from the queue. A failed or rolled-back candidate releases the lock immediately. The lock is per-promotion-attempt, not per-candidate. Multiple candidates with disjoint bases can pipeline through the engine sequentially without holding up unrelated work.

## 5. Consumed by

- **BE-1** (#82): candidate manifest schema — adds `base_state_hash`, `REBASE_REQUIRED` state, state machine extension.
- **BE-2** (#85): Promotion Engine — implements the precondition, the lock, and the REBASE_REQUIRED transition.
- **CP-5** (#93): candidate pipeline view — surfaces `REBASE_REQUIRED` cards and supports drag-to-rebase.
- **Containment Engine** (`templates/scripts/containment-engine.py`, 30K, merged from #61): provides the lock primitive.

## 6. Failure modes

- **Stale `base_state_hash` due to a non-canonical write** (e.g. Reflector bypassing the Orchestrator and writing beliefs directly): the precondition catches it; candidate → `REBASE_REQUIRED`; CP-2 (#90) attention queue surfaces `pause_reason: writer_invariant_violated`.
- **Lock holder dies mid-promotion** (SIGKILL, OOM): the next promotion's lock acquisition detects the stale lock (file age > timeout) and force-clears with a `lock_recovered_after_crash` journal entry. BE-2 idempotency keys prevent double-promotion (Gate #9 crash recovery, see BE-7 #88).
- **Multiple candidates with the same base**: only the first admitted one promotes; the rest transition to `REBASE_REQUIRED` and wait for human rebase.

## 7. Why this is P1 (audit finding F5)

The v0.6 cockpit design assumes multiple concurrent candidates visible at once (SHADOW / awaiting-Praxis / ready-to-promote shown side by side, per CP-5). Without a freshness check, promoting candidate B *after* candidate A already moved the active pointer silently overwrites A's changes — a real lost-update bug, not a hypothetical. This contract makes the bug structurally impossible: either B's base is still current (safe to promote) or B transitions to `REBASE_REQUIRED` (no overwrite).

## 8. Gates satisfied

- **Gate #14** (No global stall): `REBASE_REQUIRED` candidates leave the queue; the lock is per-promotion, not per-candidate.
- **Gate #16** (Rebase safety): `base_state_current` precondition + `REBASE_REQUIRED` transition together guarantee that a stale candidate cannot be promoted.

## 9. Reference

- Design-lock audit finding F5 (P1)
- A-3 (#78): Promotion Mechanism (defines what "promotion" means atomically)
- A-1 (#76): Effect Taxonomy (some candidates can be auto-rolled-back; some need human)
- BE-7 (#88): Golden replay senaryo 1 (stale-base) + senaryo 5 (deadlock: unresolved candidate blocks sibling) verify this contract
- #61 (merged): Containment Engine (lock primitive)
