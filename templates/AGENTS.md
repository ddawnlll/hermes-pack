# __HERMES_PROJECT_NAME__ — agent rules (starter; FILL THIS IN)

## Architecture boundaries (hard)
- *Fill in your project's module/package boundaries here.*
- Agents MUST NOT modify code outside their allowed paths.
- Orchestrator enforces these boundaries on every tick.

## Deterministic runner (fill in the real commands)
- Tests:            `<pytest command>`
- Experiment run:   `<runner command that produces JSON at __HERMES_LEDGER_DIR__/runs/<RUN_ID>.json>`
- Robustness suite: `<command>`
- Negative control: `<shuffled-label / permutation command>`
All metrics used for decisions MUST come from the JSON these commands emit.

## Orchestration
- Control plane: `__HERMES_LEDGER_DIR__/control.yaml` (read it first, always).
- Ledger: hypotheses/, runs/, reports/ under `__HERMES_LEDGER_DIR__/`.
- Branch naming: `<prefix>/<hypothesis-id>-<slug>`. One hypothesis = one branch.
- Merges to main: PR-only, evidence-gated, orchestrator-approved. No exceptions.
