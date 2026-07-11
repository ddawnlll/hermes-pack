# Changelog

All notable changes to Hephaestus are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.5.0-kaizen] — 2026-07-11

The **Kaizen Engine** — turning the loop into a self-improving system by adding a
third face (Reflector), a belief workspace (Global Workspace analog), containment for
new deadlock modes, four idea channels that supply diversity at volume, and
crash-safe runtime infrastructure. All 21 v0.5 issues (#52–#72) closed via
[PR #73](https://github.com/ddawnlll/hephaestus/pull/73). 191 tests pass. Praxis
evidence bundle: `.praxis/runs/v05-full-evidence.jsonl`.

### Phase 0 — debt cleared (#52, #53, #54, #55)

- T2 Challenger / T3 Arbiter personas — `templates/SOUL.challenger.md` and
  `templates/SOUL.arbiter.md`. Bootstrap wiring.
- `self-grade-diff.py` — orchestrator verdict cannot be more optimistic than
  mechanical evidence verdict.
- `prereg-lock.py` — locks metric, threshold, direction, `relies_on` at dispatch.
- `schema/tests_tmp/` removed; `.gitignore` tripwires for Windows path artifacts.

### Phase 1 — Belief workspace + Reflector (#56, #57, #58, #59, #60)

- `schema/beliefs.schema.json` — capacity cap 12, mandatory `kill_criterion`,
  `blamed_by`, `historical_beliefs[]`.
- `relies_on` on hypotheses → blame propagation → suspect detection.
- `narrative.md` — one-page project story, rewritten each consolidation.
- Reflector agent — `SOUL.reflector.md` + `reflector-dispatch.sh`. Three questions
  per run.
- Stagnation / momentum signals; suspect-belief hard rule in orchestrator SOUL.

### Phase 2 — Containment (#61, #62, #63, #64)

- Authority matrix — 28 role pairs, terminal referee for every pair.
- Suspect TTL — no permanent frame lockout.
- Curiosity exemption — Red Team blocks MERGE, never RUN.
- Belief min-residency + eviction evidence.
- Frame-shift cooldown + ratchet hysteresis.

### Phase 3 — Idea channels (#65, #66, #67, #68)

- **Analogy** — `~/.hermes/lessons.jsonl` cross-project corpus + casting sessions.
- **Random-leap** — bisociation replay, dream mode, external entropy.
- **Affect** — Brier calibration, mood modulation, family rotation.
- **Context** — whisper inbox, morning briefing, regime detector.

All channels are independently feature-flagged, default disabled, separate daily
budgets. Disabled = zero spend, zero artifacts.

### Phase 4 — Provenance + measurement (#69)

- `provenance` field on hypothesis + merge records.
- Per-channel hit-rate reports. A merge without provenance fails schema validation.

### Phase 5 — Runtime reliability (#70, #71, #72)

- `feature-flags.py` — gradual rollout with safe defaults.
- `tick-journal.py` — durable transaction journal, atomic, idempotent.
- `channel-budget.py` — atomic daily idempotent accounting.
- `tick-runtime.py` + `channel-dispatch.py` — deterministic dispatchers.
- `.github/workflows/v05-ci.yml` — full test matrix on every PR.
- Canary suite — 11 scenarios, 19 assertions.

### Bootstrap integration

- `bootstrap.sh` and `bootstrap.ts` install v0.5 scripts and create extra ledger
  dirs.
- `adapters/v7-alphaforge/project.yaml` — `reflector_model`/`reflector_chain` added.
- `templates/prompts/tick.md` — Phase 4 channel dispatch + reflector dispatch.

## [0.4.0-planning] — 2026-07-08

Rebrand + design phase for the adversarial council architecture. No new runtime
behavior — this is documentation, naming, and repo scaffolding. The actual
implementation is tracked in
[milestone v0.4](https://github.com/ddawnlll/hephaestus/milestone/5) (issues
#21–#32) and has not landed yet.

### Changed

- Repository renamed `hermes-pack` → `hephaestus`. Local install directory
  convention changed from `~/.hermes-pack` to `~/.hephaestus`; env var
  `HERMES_PACK_DIR` → `HEPHAESTUS_DIR`.
- `package.json` name `hermes-orchestrator-pack` → `hephaestus`, version bumped
  to `0.4.0-planning`.
- GitHub repo description, topics, and motto ("Explore freely. Prove ruthlessly.")
  updated.
- `schema/*.schema.json` `$id` URLs updated to the new repo path.
- README rewritten: new name/motto, and a new "v0.4 — Adversarial Council
  (Hephaestus)" section describing the Janus design.

### Added

- `templates/SOUL.redteam.md` — Red Team persona. Not yet wired into bootstrap.
- New GitHub milestone "v0.4 — Adversarial Council (Hephaestus)" and 12 tracking
  issues (#21–#32).
- New labels: `adversarial-council`, `escalation`.

### Not changed (intentionally)

- `.praxis/**` (plans, locks, runs, repairs) and `reports/**` — historical audit
  trail, left untouched.
- The existing v0.2/v0.3 milestone roadmap — unrelated to this rebrand, not
  touched.

## [1.0.0] — prior to this changelog

Initial `hermes-pack` releases: Praxis Truth Kernel integration, versioned schema
contract (state/control/goal/ideas/events), LiteLLM provider fallback router,
v1→v2 ledger migration. Not tracked in detail retroactively.

---

**Full changelog source**: [`CHANGELOG.md`](https://github.com/ddawnlll/hephaestus/blob/main/CHANGELOG.md)
