# Blocker Registry — Hermes Orchestrator Pack

Items that could not be verified in this environment.

## Runtime verification — resolved

| Item | Status |
|------|--------|
| `hermes --version` | ✅ v0.18.0 confirmed |
| Profile installation | ✅ `hermes profile create` works, config/SOUL injected |
| `hermes cron status` | ✅ Gateway not running (expected) |
| `hermes kanban boards create` | ✅ Board 'alphaforge' created |
| `hermes cron create` | ✅ Job 'af-orchestrator-tick' created |
| Tick gate script installation | ✅ Installed to `~/.hermes/scripts/` |
| Idempotent re-run | ✅ No duplicate profiles/boards/jobs |

## Remaining — require API keys

| Item | Requires | Status |
|------|----------|--------|
| Tick gate script runtime behavior | Active cron with script execution | ⏳ needs API keys |
| Full autonomous loop test | `mode: running` in control.yaml + API keys | ⏳ needs API keys |
| Worker kanban task dispatch | Profile model configured + API keys | ⏳ needs API keys |
| `hermes cron run` manual tick | Agent with provider access | ⏳ needs API keys |

## Provider/model values

- `__NEEDS_LOCAL_VERIFICATION__` markers appear in:
  - `adapters/v7-alphaforge/project.yaml` (orchestrator_model, worker_model)
  - `bootstrap.sh` default values (DF_ORCH_MODEL, DF_WORKER_MODEL)
- These must be set by the user via `project.yaml`, env vars (`HERMES_ORCH_MODEL`, etc.), or `hermes model` command.
- Current profiles show `__NEEDS_LOCAL_VERIFICATION__` as the model — expected until configured.

## Hermes CLI flags

- `--script`, `--deliver`, `--workdir` flags confirmed working with `hermes cron create` in v0.18.0.
- `hermes profile create <name>` confirmed working — profiles created with full skill bundles.
