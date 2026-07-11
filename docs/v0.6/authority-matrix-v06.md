# Authority Matrix v0.6 Extension (A-6)

**Issue:** #81 (Track A, P1)
**Status:** Accepted — v0.6
**Consumed by:** `templates/scripts/containment-engine.py` (30K, merged from #61) and the existing matrix-coverage test.
**Completion gate:** #8 (Authority completeness)
**Why:** #61's own acceptance criterion is "test fails when a new profile is added without a matrix entry" — v0.6 adds exactly such profiles.
**Pure extension, not new design:** Same invariant as #61; this issue adds v0.6 roles and pairs.

## 1. What this contract locks

Three new roles enter the v0.6 system and need terminal referees for every pair they form with existing roles:

| New role | Identity | Notes |
|---|---|---|
| `promotion_engine` | The Promotion Engine (BE-2 #85) is a new actor in v0.6 — it executes merges and atomic switches. | Authoritative on candidate promotion; never party to its own conflict. |
| `autonomous_t4` | The T4 (Tier-4) disposition engine (BE-5 #87) running in `AFK_AUTONOMOUS` mode. | Distinct from the regular `t4` (which is gated on human approval). |
| `dreamer` | The Dreamer channel (already merged from a previous v0.5 wave — `f8e30df feat Phase 4 channels`). | In the v0.5 channel set, but **not yet in the matrix** — this issue brings it in. |
| `cockpit_intent` | (sub-role of `human`) | Cockpit UI actions are human-authoritative; they map onto the existing `human` role in the matrix. **No new role needed** — but call this out explicitly so consumers don't add a duplicate. |

## 2. New pairs to add (matrix extension)

For each new role, every pair with the existing 8 base roles (`worker`, `orchestrator`, `challenger`, `arbiter`, `red_team`, `explorer`, `reflector`, `human`) needs a terminal referee. Sorted-pair form (the matrix is keyed by `sorted(a, b)` tuples).

### `promotion_engine` pairs

| Pair | Referee | Why |
|---|---|---|
| `(promotion_engine, worker)` | `arbiter` | The engine touching a worker's output is a content dispute; arbiter is the content referee. |
| `(promotion_engine, orchestrator)` | `arbiter` | Engine vs. orchestrator on a candidate is a content dispute. |
| `(promotion_engine, challenger)` | `arbiter` | Engine vs. challenger is a content dispute. |
| `(promotion_engine, arbiter)` | `human` | Engine's output being arbitrated → human. |
| `(promotion_engine, red_team)` | `arbiter` | Engine vs. red-team is content dispute. |
| `(promotion_engine, explorer)` | `arbiter` | Engine vs. explorer is content dispute. |
| `(promotion_engine, reflector)` | `arbiter` | Engine vs. reflector is content dispute. |
| `(promotion_engine, human)` | `human` | Engine overriding a human override is impossible; human wins. |

### `autonomous_t4` pairs

| Pair | Referee | Why |
|---|---|---|
| `(autonomous_t4, worker)` | `human` | T4 in autonomous mode affecting a worker is escalated to human (AFK safety floor). |
| `(autonomous_t4, orchestrator)` | `human` | Same. |
| `(autonomous_t4, challenger)` | `arbiter` | T4 vs. challenger is content dispute. |
| `(autonomous_t4, arbiter)` | `human` | T4 in autonomous mode being arbitrated → human. |
| `(autonomous_t4, red_team)` | `arbiter` | Content dispute. |
| `(autonomous_t4, explorer)` | `arbiter` | Content dispute. |
| `(autonomous_t4, reflector)` | `arbiter` | Content dispute. |
| `(autonomous_t4, human)` | `human` | Human wins; AFK T4 cannot override a human action. |
| `(autonomous_t4, promotion_engine)` | `human` | AFK T4's decision being executed by the engine → human (the AFK safety floor says AFK T4 cannot execute irreversible_external via the engine, so its decisions escalate). |

### `dreamer` pairs

| Pair | Referee | Why |
|---|---|---|
| `(dreamer, worker)` | `arbiter` | Dreamer proposing what a worker should do is a content dispute. |
| `(dreamer, orchestrator)` | `arbiter` | Same. |
| `(dreamer, challenger)` | `arbiter` | Same. |
| `(dreamer, arbiter)` | `human` | Dreamer's output being arbitrated → human. |
| `(dreamer, red_team)` | `arbiter` | Content dispute. |
| `(dreamer, explorer)` | `arbiter` | Content dispute. |
| `(dreamer, reflector)` | `arbiter` | Content dispute (reflector and dreamer both produce narrative; arbiter decides). |
| `(dreamer, human)` | `human` | Dreamer cannot override human. |

### `cockpit_intent` — no new role

`cockpit_intent` is the human operator acting through the Cockpit UI. It maps to the existing `human` role in the matrix. **No new pairs are added** for `cockpit_intent`; the existing `(human, *)` pairs cover it. The Cockpit wiring (CP-3 #91) emits `actor: human` in workspace intents (A-2 #77), and the matrix treats those as human.

## 3. Referee-invariant (carried forward, NOT relaxed)

The #61 invariant is: **no referee sits in a pair it is party to.** Every referee named above is third-party to the pair. This issue does not change the invariant; it only extends the matrix.

## 4. Where the matrix lives

The matrix is a Python dict `AUTHORITY_MATRIX` at `templates/scripts/containment-engine.py:54`. The extension is a pure addition of `(role_a, role_b): referee` entries. The existing helper `check_authority(conflicting_roles, roles_dir=None)` already does symmetric lookup (`AUTHORITY_MATRIX.get(key) or AUTHORITY_MATRIX.get((roles[1], roles[0]))`), so adding entries in sorted-pair form is sufficient.

## 5. Test extension (consumed by #61's existing test)

`schema/tests/test_phase2_containment.py` already has the acceptance test:
> "test fails when a new profile is added without a matrix entry."

The v0.6 extension requires that test to also pass for `promotion_engine`, `autonomous_t4`, and `dreamer`. The existing test harness picks up roles via `discover_roles_from_bootstrap()` (line 97 of `containment-engine.py`), which scans `templates/SOUL.*.md`, `templates/config.*.yaml`, and `adapters/*/project.yaml`. For the test to pick up the new roles, the v0.6 implementation must:

- Add `SOUL.promotion_engine.md`, `SOUL.autonomous_t4.md`, `SOUL.dreamer.md` (or a single combined `SOUL.dreamer.md` if Dreamer was not already present).
- Add corresponding `config.*.yaml` files.
- Add `promotion_engine`, `autonomous_t4`, `dreamer` to the matrix (per §2).

## 6. Consumed by

- **Containment Engine** (`templates/scripts/containment-engine.py`): adds new pairs.
- **BE-2** (#85): the Promotion Engine role; every cross-role conflict involving the engine is resolved through the matrix.
- **BE-5** (#87): the T4 disposition engine; `autonomous_t4` is a sub-mode of T4.
- **CP-3** (#91): Cockpit intervention grammar — emits `actor: human` so existing human pairs apply; no new role needed for cockpit_intent.
- **`schema/tests/test_phase2_containment.py`**: the matrix-coverage test must pass for the new roles.

## 7. Why this is P1

#61's own acceptance criterion is: "the test fails when a new profile is added without a matrix entry." v0.6 adds exactly such profiles (`promotion_engine`, `autonomous_t4`, `dreamer`). Without the matrix extension, the test will fail at integration time and the v0.6 milestones will be blocked.

## 8. Gates satisfied

- **Gate #8** (Authority completeness): every v0.6 role has a terminal referee for every pair; no referee is party to its own pair.

## 9. Reference

- #61 (merged): Containment Engine + authority matrix + the matrix-coverage test
- A-1 (#76): Effect Taxonomy — `irreversible_external` candidates must escalate to human even in autonomous T4 mode
- A-2 (#77): Workspace Intent contract — `actor: human` is the canonical type for cockpit-driven intents
- BE-2 (#85): Promotion Engine — the new `promotion_engine` role
- BE-5 (#87): T4 disposition engine — the new `autonomous_t4` role
- `f8e30df` (v0.5 commit): Dreamer channel — the new `dreamer` role
