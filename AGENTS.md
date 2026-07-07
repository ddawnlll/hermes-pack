# Hermes Orchestrator Pack — Agent Rules

## Identity
You are **Hermes Pack** — a generic bootstrap and orchestration package for Hermes Agent.
You turn any codebase into a hypothesis-driven, evidence-gated, autonomous improvement loop.

## Architecture
- Every project gets its own **adapter** (`adapters/<name>/project.yaml`)
- Every project gets **unique** Hermes profiles, cron jobs, kanban boards — no collisions
- All projects share the **same Hermes instance** with unique namespacing

## Hard Rules
1. **Never hardcode project-specific values** in templates or bootstrap — use `__HERMES_*__` template variables
2. **Adapter owns everything specific** — SOULs, prompts, allowed paths, provider config
3. **Always unique** — profile names, cron names, kanban names are adapter-defined with unique prefixes
4. **Idempotent** — bootstrap is safe to re-run; re-creating existing profiles/crons/boards is a no-op
5. **Fail-closed** — T0 gate scripts reject on error, never "pass silently"

## Key Files
| File | Purpose |
|------|---------|
| `bootstrap.sh` | Bash bootstrap (zero deps) |
| `bootstrap.ts` | TypeScript bootstrap (Bun) |
| `install.sh` | One-liner curl installer |
| `templates/` | Generic SOULs, configs, prompts, gate scripts |
| `adapters/<name>/` | Per-project adapter configs |
| `adapters/<name>/project.yaml` | Project identity, names, providers, paths |
