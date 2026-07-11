# State-of-Record Cutover Plan (A-4)

**Issue:** #79 (Track A, P1)
**Status:** Accepted — v0.6
**Consumed by:** DL-1 (#95), DL-2 (#97), DL-3 (#96), DL-4 (#98)
**Completion gate:** #17 (Kill supremacy)
**Why:** Design-lock audit finding F4 (P1)
**Permanent invariant:** Yes — kill/pause/freeze OR'ling is a defense-in-depth property, **not** a transitional hack.

## 1. What this contract locks

A field-by-field canonical-ownership table for the JSON/YAML → Postgres migration, executed in two phases, plus the kill/pause/freeze OR'ling rule that survives the migration.

## 2. Canonical-ownership table

| Field (path) | Phase A canonical | Phase B canonical | Notes |
|---|---|---|---|
| `control.yaml: mode` (kill/pause/freeze) | `templates/control.yaml` | `db.control_state` (Postgres) | **OR'd in BOTH phases** (see §3). Defense in depth. |
| `beliefs.yaml: beliefs[]` | `templates/beliefs.yaml` | `db.beliefs` (Postgres) | Phase A: file authoritative, DB mirrors via `tick-journal.py`. Phase B: DB authoritative, file is export. |
| `goal.yaml: goals[]` | `templates/goal.yaml` | `db.goals` (Postgres) | Same as beliefs. |
| `hypothesis.yaml: hypotheses[]` | `templates/hypothesis.yaml` | `db.hypotheses` (Postgres) | Same as beliefs. |
| `tick-journal.py` entries | `templates/scripts/tick-journal.py` (file) | `db.tick_journal` (Postgres) | Append-only; Phase A file is canonical, Phase B DB is canonical. File export in Phase B for offline replay. |
| `config.*.yaml` (per-agent) | `templates/config.*.yaml` | `db.agent_configs` (Postgres) | Same as beliefs. |
| `SOUL.*.md` (per-agent) | `templates/SOUL.*.md` | `db.agent_souls` (Postgres) | Read-only after init; migration is one-way export. |
| `state.schema.json` registry | `schema/state.schema.json` | `db.schema_registry` (Postgres) | Schema versions are append-only. |
| `candidate` manifest (new in v0.6) | `db.candidates` (Postgres only) | `db.candidates` (Postgres only) | v0.6 introduces this field; no Phase A file. |

## 3. The kill/pause/freeze OR rule (PERMANENT)

**Statement (verbatim, normative):**

> At every tick, the system reads `mode` (one of: `live`, `paused`, `frozen`, `killed`) from BOTH `templates/control.yaml` AND `db.control_state`. The effective mode is the **OR** of the two values, evaluated in the precedence order `killed > frozen > paused > live`. If **either** surface reports `killed`, the effective mode is `killed`. The system must reach a killed-state within one tick of either surface reporting it.

**Why permanent, not transitional:** during migration, the documented kill switch (README "Controls" table) must not silently stop working from one of the two surfaces. A split-brain window is exactly when operators reach for the kill switch; the OR'ling makes the kill switch monotonic with respect to the migration. The cost (one extra read per tick) is negligible; the safety gain is permanent. Even after Phase B is complete and the file is "export only," the OR'ling remains in force as defense in depth.

## 4. Phase A: file canonical + DB mirror

**Window:** Phase A spans DL-1 (#95) bootstrap through DL-2 (#97) initial migration. DL-3 (#96) pointer convention is available to route file-writes to DB-shadow where useful.

**During Phase A:**

- Each canonical file is the source of truth.
- `tick-journal.py` appends a shadow entry to `db.control_state`, `db.beliefs`, etc. on every write.
- DL-2 migration job: periodic reconciliation compares file → DB; mismatches trigger `pause_reason: file_db_drift`.
- Operators can read either surface; writes go to the file (Phase A invariant).
- Kill/pause/freeze: OR'd (per §3). Either surface killable.

**Exit criterion for Phase A → Phase B:**

- DL-2 has run without drift for **30 consecutive days** in production-equivalent load.
- Reconciliation job reports `0 mismatches` for the trailing 7 days.
- A documented rollback path exists: switching back to file-canonical within 24 hours is a single config flag.

## 5. Phase B: DB canonical + file export

**During Phase B:**

- Postgres tables are the source of truth.
- `tick-journal.py` writes the canonical state to DB; file export runs as a background job (DL-3 pointer convention; DL-4 episodic layer can cache exports).
- Operators read from DB; the file is a "what the DB looked like at last export" snapshot.
- Writes go to DB.
- Kill/pause/freeze: OR'd (per §3, still in force).

**Rollback to Phase A:**

- Single config flag (`templates/control.yaml: phase = A`).
- File shadow is treated as canonical again; DB writes queue.

## 6. Consumed by

- **DL-1** (#95): Postgres + pgvector bootstrap — sets up `db.*` tables.
- **DL-2** (#97): JSONB relational core — implements the canonical tables.
- **DL-3** (#96): object storage pointer convention — file export goes here.
- **DL-4** (#98): memory layers — episodic layer caches file exports.
- **Containment Engine** (`templates/scripts/containment-engine.py`, 30K, merged from #61): implements the OR'ling in step 1 of the promotion pipeline.
- **README "Controls" table**: the documented kill switch; this contract is what makes that switch durable.

## 7. Failure modes

- **File and DB disagree on `mode` during Phase A**: OR resolves to the more restrictive. The less restrictive surface is logged as `shadowed_invariant_violation` and surfaced in CP-2 (#90) attention queue.
- **DB unavailable in Phase B**: fallback to last-known file export. System pauses with `pause_reason: db_unavailable` rather than running without the canonical.
- **Reconciliation drift in Phase A**: drift > 0.1% over 24h triggers auto-pause + human escalation (CP-2 critical).

## 8. Gates satisfied

- **Gate #17** (Kill supremacy): any surface reporting `killed` is honored within one tick. OR'ling is permanent.

## 9. Reference

- Design-lock audit finding F4 (P1)
- `templates/control.yaml` (619B) — current file
- `schema/control.schema.json` (3.5K) — current schema
- #61 (merged): Containment Engine — implements the OR'ling
- README "Controls" table — the documented kill switch that must remain durable
