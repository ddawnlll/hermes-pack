# Changelog

All notable changes to this project are documented here.

## [0.4.0-planning] — 2026-07-08

Rebrand + design phase for the adversarial council architecture. **No new runtime behavior
ships in this release** — this is documentation, naming, and repo scaffolding. The actual
implementation is tracked in [milestone v0.4](https://github.com/ddawnlll/hephaestus/milestone/5)
(issues #21–#32) and has not landed yet.

### Changed
- Repository renamed `hermes-pack` → `hephaestus`. Local install directory convention changed
  from `~/.hermes-pack` to `~/.hephaestus`; env var `HERMES_PACK_DIR` → `HEPHAESTUS_DIR`.
- `package.json` name `hermes-orchestrator-pack` → `hephaestus`, version bumped to
  `0.4.0-planning`.
- GitHub repo description, topics, and motto ("Explore freely. Prove ruthlessly.") updated.
- `schema/*.schema.json` `$id` URLs updated to the new repo path.
- README rewritten: new name/motto, and a new "v0.4 — Adversarial Council (Hephaestus)" section
  describing the Janus design (Explorer + Red Team), the three \$0 deterministic gates, and the
  escalation/AFK policy — explicitly marked as design/roadmap, not implemented.

### Added
- `templates/SOUL.redteam.md` — Red Team persona (strategy-layer adversary, falsifiability
  contract, scar-tissue memory). Not yet wired into bootstrap.
- New GitHub milestone "v0.4 — Adversarial Council (Hephaestus)" and 12 tracking issues
  (#21–#32) covering: orchestrator/merge conflict-of-interest separation, provider-chain
  decorrelation, scar-tissue memory in the Hindsight bridge, Red Team + Explorer wiring,
  adaptive ratchet, pre-registration lock gate, self-grade diff gate, ROI/exploitation-throttle
  gate, curiosity budget, and escalation/AFK policy.
- New labels: `adversarial-council`, `escalation`.

### Not changed (intentionally)
- `.praxis/**` (plans, locks, runs, repairs) and `reports/**` — historical audit trail,
  left untouched. Rewriting evidence history would violate Praxis's own no-tampering principle.
- The existing v0.2/v0.3 milestone roadmap (desktop app, Ideas Engine, events ticker, etc.) —
  unrelated to this rebrand, not touched.

## [1.0.0] — prior to this changelog

Initial `hermes-pack` releases: Praxis Truth Kernel integration, versioned schema contract
(state/control/goal/ideas/events), LiteLLM provider fallback router, v1→v2 ledger migration.
Not tracked in detail retroactively.
