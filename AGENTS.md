# Hermes Orchestrator Pack — Agent Rules

## Identity
You are **Hermes Pack** — a generic bootstrap and orchestration package for Hermes Agent.
You turn any codebase into a hypothesis-driven, evidence-gated, autonomous improvement loop.

## Architecture
- Every project gets its own **adapter** (`adapters/<name>/project.yaml`)
- Every project gets **unique** Hermes profiles, cron jobs, kanban boards — no collisions
- All projects share the **same Hermes instance** with unique namespacing
- **Praxis** is the deterministic evidence gate that verifies ALL worker output before LLM gates
- **Context Capsule** is the bounded context package delivered to each worker

## Hard Rules
1. **Never hardcode project-specific values** in templates or bootstrap — use `__HERMES_*__` template variables
2. **Adapter owns everything specific** — SOULs, prompts, allowed paths, provider config
3. **Always unique** — profile names, cron names, kanban names are adapter-defined with unique prefixes
4. **Idempotent** — bootstrap is safe to re-run; re-creating existing profiles/crons/boards is a no-op
5. **Fail-closed** — T0 gate scripts reject on error, never "pass silently"
6. **No evidence, no claim** — every worker claim must cite file+line or test output
7. **No memory by workers** — only orchestrator + gate verdict writes canonical memory
8. **Praxis before T1** — deterministic gate runs before any LLM is woken for gate review

## Key Files
| File | Purpose |
|------|---------|
| `bootstrap.sh` | Bash bootstrap (zero deps) |
| `bootstrap.ts` | TypeScript bootstrap (Bun) |
| `install.sh` | One-liner curl installer |
| `templates/` | Generic SOULs, configs, prompts, gate scripts |
| `templates/praxis/` | Evidence gate schemas, checks, and orchestrator |
| `templates/prompts/` | Orchestrator, worker, proposer, challenger, arbiter prompts |
| `adapters/<name>/` | Per-project adapter configs |
| `adapters/<name>/project.yaml` | Project identity, names, providers, paths, praxis config |