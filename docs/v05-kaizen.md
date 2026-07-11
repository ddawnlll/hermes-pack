# v0.5 — Kaizen Engine

> **Shipped in [v0.5.0-kaizen](https://github.com/ddawnlll/hephaestus/releases/tag/v0.5.0-kaizen)**
> via PR [#73](https://github.com/ddawnlll/hephaestus/pull/73).
> 21 issues closed (#52–#72). 191 tests pass. Praxis evidence:
> `.praxis/runs/v05-full-evidence.jsonl`.

The Kaizen Engine turns the loop into a self-improving system. Four additions:

1. **Belief workspace** — narrow, capacity-limited, single-writer. Global Workspace analog.
2. **Reflector** — the third face. Consolidates, explains, rewrites the system's shared
   assumptions.
3. **Idea channels** — four independent idea streams (analogy, dream, whisper, calibration)
   that supply diversity at volume.
4. **Containment** — explicit handling of the new deadlock modes the v0.5 system creates.

## What was the v0.4 deadlock?

In v0.4, the system was a clean per-bundle pipeline: worker → Praxis → T1 → T2 → T3 →
merge. But the loop never *learned* in a structured way — every tick was a fresh
hypothesis with no accumulation of *what the system believes about the world*.

In particular: when three hypotheses relying on belief B-X all FAIL, the system should
notice and mark B-X as suspect. In v0.4 there was no such mechanism. v0.5 fixes this
with `relies_on` + blame propagation.

## Phase 0 — debt cleared

[Issues #52–#55](https://github.com/ddawnlll/hephaestus/issues?q=label%3Aphase-0-debt)

| Issue | What |
|---|---|
| #52 | T2 Challenger and T3 Arbiter SOUL persona files (were missing) |
| #53 | `self-grade-diff.py` — orphan test existed but no implementation |
| #54 | `prereg-lock.py` — folded into hypothesis dispatch |
| #55 | Repo hygiene — `schema/tests_tmp/` cleanup + Windows path tripwires |

## Phase 1 — Belief workspace + Reflector

[Issues #56–#60](https://github.com/ddawnlll/hephaestus/issues?q=label%3Aphase-1-workspace)

### `relies_on` — the load-bearing change

```yaml
# schema/hypothesis.schema.json (excerpt)
hypothesis:
  id: H-042
  statement: "Volatility regime shift at 14:30 UTC predicts 15m direction"
  relies_on: [B-007, B-003]   # ← required, may be empty []
  metric: sharpe
  threshold: 1.4
  direction: ">="
```

When H-042 FAILs, blame propagates upward: both B-007 and B-003 get the FAIL appended
to `blamed_by[]` and lose confidence. **Three failures on B-X → B-X becomes `suspect`.**
This is the mechanism that produces "grow the dataset" without ever enumerating axes in
config — the system finds its own bottleneck.

### Beliefs workspace

```yaml
# schema/beliefs.schema.json
beliefs:
  - id: B-007
    statement: "Current dataset has sufficient statistical power for sharpe>=1.4"
    confidence: 0.35
    blamed_by: [H-012, H-015]
    tested_directly: false
    suspect: false
    kill_criterion: "Sharpe < 1.0 across 200+ hypotheses in any window"
```

Hard rules:

- **Cap 12 active beliefs.** Capacity limit is the mechanism, not a nicety.
- **Every belief MUST carry `kill_criterion`** (falsifiability contract).
- **Reflector is the single writer** — same principle as `objections.jsonl`.
- **Eviction requires evidence** — symmetric with entry.

### Reflector

`templates/SOUL.reflector.md` + `templates/scripts/reflector-dispatch.sh`.

Three questions per run:

1. **Shared-assumption extraction** — intersection of recent failures → frame-shift candidates
2. **Relaxation probe** — "which single constraint binds?" → constraint-questioning ideas
3. **Perspective tour** — "how would X read this?" → cheap lateral jumps

Hard rules:

- Decorrelated model family from orchestrator (else self-grading theater)
- Runs offline (idle / plateau), like human sleep consolidation
- May mark at most ONE belief `suspect` per run
- Writes ONLY `beliefs.yaml` and `narrative.md` — never code, never hypotheses

### Stagnation / momentum signals

`state.schema.json` v2 adds `stagnation` (info-gain per tick) and `momentum` (merge
streak). SOUL hard rule: while a `suspect` belief exists, **no new hypotheses inside
that frame** — either propose a belief-test or file an objection to T3.

## Phase 2 — Containment

[Issues #61–#64](https://github.com/ddawnlll/hephaestus/issues?q=label%3Aphase-2-containment)

The new v0.5 system creates deadlock modes that did not exist in v0.4. Phase 2
contains them:

| Issue | Antidote |
|---|---|
| #61 | **Authority matrix** — terminal referee for every role pair (Reflector↔Red Team → T3) |
| #62 | **Suspect TTL** — `suspect` expires after 5 ticks; Reflector must re-justify |
| #63 | **Belief min-residency** — M=3 ticks before eviction allowed; eviction requires evidence |
| #64 | **Frame-shift cooldown + ratchet hysteresis** — no suspect-marking for K=8 ticks after a frame shift |

Critical: **the curiosity exemption** (per #30, from v0.4) is reinforced — a Red Team
block prevents MERGE of a result, never the RUN of the experiment. Gates constrain
*claims*, never *curiosity*.

## Phase 3 — Idea channels

[Issues #65–#68](https://github.com/ddawnlll/hephaestus/issues?q=label%3Aphase-3-channels)

Four channels, all independently feature-flagged, default disabled, candidate-only
output. Disabled = zero spend, zero artifacts.

### Analogy channel (#65)

`templates/scripts/analogy-channel.py` — `~/.hermes/lessons.jsonl` cross-project corpus
with **dual writing**: every lesson stored twice — concrete
("AlphaForge dataset was too small") + denominalized abstract
("the resource shared by all local mutations was the unquestioned bottleneck").
Domain nouns → role variables. Retrieval runs on the abstract form only.

**Casting sessions:** when stuck, force-fit the top-5 abstract lessons from OTHER
projects: "if this lesson applied here, what would it say?" Most casts fail; survivors
become hypotheses via the curiosity budget. Tagged `provenance: analogy`.

### Random-leap channel (#66)

`templates/scripts/dream-channel.py` — three mechanisms:

1. **Bisociation replay** — sample ledger-entry PAIRS at MID embedding distance
   (Koestler's intersection of two frames; too close = trivial, too far = noise).
2. **Dream mode** — on idle ticks, generate deliberately absurd recombinations
   (constraint inversion: "what if the goal were reversed?"). Generation and filtering
   are **temporally separated** — judgment happens at the NEXT Reflector consolidation
   (sleep, then morning filter).
3. **External entropy** — one random arXiv/HN item per day injected into Explorer
   context. Zettelkasten serendipity.

### Affect channel (#67)

`templates/scripts/calibration-channel.py` — copy affect's FUNCTION, not its feeling:

1. **Calibration score = mechanical shame.** Every role attaches a probability to every
   verdict. Brier scores in `$LEDGER/calibration.json`. Confidently-wrong is costly.
   **CRITICAL:** score CALIBRATION, never agreement — otherwise the Red Team stops
   blocking to protect its score and the system turns sycophantic.
2. **Mood as parameter modulation, never decision gating:** momentum/frustration
   scalars modulate hypothesis ambition and exploration ratio. Merge streak → raise
   ambition; losing streak → small-wins mode to recalibrate.
3. **Boredom → rotation:** low info-gain triggers switching hypothesis FAMILY
   (interleaving/spacing effect), not just frame shifts.

### Context channel (#68)

`templates/scripts/whisper-channel.py` — three mechanisms:

1. **Whisper inbox** (`$LEDGER/whispers/`) — highest-leverage. Unstructured one-line
   human impressions. No format, no justification, 30 seconds. Reflector reads whispers
   as WEAK evidence. Human intuition becomes an input stream instead of a bottleneck gate.
2. **Morning briefing:** adapter-defined external feeds (alphaforge: vol regime, macro
   calendar; org: commit/PR discussion digest) summarized daily into workspace CONTEXT,
   never commands.
3. **Regime detector:** deterministic statistical nose — correlation breaks, vol
   clustering.

**Security invariant (non-negotiable):** every external stream must EARN workspace
entry through the capacity cap + competitive entry. Nothing external writes to
`beliefs.yaml` directly. Widening the sensorium widens the prompt-injection surface;
the workspace bottleneck IS the defense.

## Phase 4 — Provenance + measurement

[Issue #69](https://github.com/ddawnlll/hephaestus/issues/69)

Every merged improvement carries a `provenance` tag:

```yaml
provenance:
  - elimination
  - analogy
  - replay
  - whisper
  - external
  - relaxation
```

Tick reports aggregate per-channel hit rates (ideas generated → hypotheses dispatched →
merges). After ~6 months of provenance data, the system itself answers
"which channel produces merges" and investment shifts accordingly.

A merge without `provenance` fails schema validation.

## Phase 5 — Runtime reliability

[Issues #70–#72](https://github.com/ddawnlll/hephaestus/issues?q=is%3Aissue+kaizen-engine)

| Issue | What |
|---|---|
| #70 | Feature flags + Reflector shadow rollout (default disabled, gradual rollout) |
| #71 | Tick transaction journal + crash recovery/idempotency (durable, atomic) |
| #72 | End-to-end adversarial replay/canary suite (11 scenarios, 19 assertions) |

### Tick transaction journal

```python
# templates/scripts/tick-journal.py
{
  "tick_id": "uuid",
  "run_id": "uuid",
  "phase": "dispatch | reflect | merge | ...",
  "status": "pending | running | completed | failed",
  "started_at": "timestamp",
  "completed_at": "timestamp",
  "side_effects": ["worker:H-042", "merge:PR-77", ...]
}
```

Invariant: `already_applied(run_id, operation) → skip`. Proves idempotent across worker
dispatch, blame propagation, merges, lessons, provenance, spend accounting, channel
output, and reflector consolidation.

### Canary suite

11 end-to-end scenarios:

1. Belief capacity 12/13 (cap enforcement)
2. TTL expiry (suspect expires correctly)
3. Direct blame (3 failures on B-X → suspect)
4. Authority coverage failure (role pair missing → FAIL closed)
5. Ratchet restart (durable across process death)
6. Prompt injection isolation (whisper cannot mutate beliefs)
7. Disabled channel zero side effects
8. Deadlock recovery (suspect + Red Team block → experiment still runs)
9. Eviction (evidence-backed, audit logged)
10. Reflector shadow isolation (proposals file, real beliefs untouched)
11. Duplicate tick idempotency + crash recovery

## Migration from v0.4

```bash
bash migrate-ledger.sh .alphaforge/orchestrator/state.json --backup
```

`migrate-ledger.sh` converts v1 hypothesis files (empty `relies_on`) into v0.5 schema.
The `relies_on` field is required (may be empty `[]`) on all new hypotheses from this
release forward.

## What's next

v0.6 candidates:

- Channel dispatch hardening (deterministic pre-commit + cron-side enforcement)
- Reflector active-mode rollout (default shadow until readiness passes for 30 consecutive
  ticks across all deployed projects)
- Cross-project lessons.jsonl consolidation endpoint
- Quantitative hit-rate analysis from provenance data

## Reference

- [CHANGELOG.md](https://github.com/ddawnlll/hephaestus/blob/v0.5.0-kaizen/CHANGELOG.md)
- [PR #73](https://github.com/ddawnlll/hephaestus/pull/73)
- [Release v0.5.0-kaizen](https://github.com/ddawnlll/hephaestus/releases/tag/v0.5.0-kaizen)
- [Praxis evidence bundle](https://github.com/ddawnlll/hephaestus/blob/v0.5.0-kaizen/.praxis/runs/v05-full-evidence.jsonl)
