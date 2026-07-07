# Hermes Orchestrator Pack

A generic, reusable bootstrap and orchestration package for [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Turns any codebase into a hypothesis-driven, evidence-gated, autonomous improvement loop.
All projects share the **same Hermes instance** with unique namespacing.

## Architecture

```
hermes-pack/
  install.sh               # One-liner curl installer
  bootstrap.sh             # Bash bootstrap (zero deps) — orchestrator mode
  bootstrap.ts             # TypeScript bootstrap (Bun)
  templates/               # Generic template files (SOULs, configs, prompts)
  adapters/                # Project-specific adapters
    v7-alphaforge/         # V7/AlphaForge adapter (orchestrator mode)
    designforge/           # DesignForge adapter (custom mode)
    money-radar/           # Money Radar stub (custom mode, coming soon)
```

### Two setup modes

| Mode | Adapter | Creates | Use case |
|------|---------|---------|----------|
| `orchestrator` | `v7-alphaforge` | 1 orchestrator + N worker profiles, 1 cron tick, gate script, hypotheses ledger | Hypothesis-driven alpha research |
| `custom` | `designforge`, `money-radar` | Adapter-defined profiles, multiple cron jobs, kanban | Non-orchestrator pipelines |

## How it works (orchestrator mode)

1. **Bootstrap** creates Hermes profiles, a project ledger, and a cron tick.
2. **Orchestrator** runs on a cron schedule, reads hypotheses, dispatches work via Kanban, judges results.
3. **Workers** execute bounded hypothesis-testing tasks on isolated branches.
4. **Evidence** must come from deterministic runner JSON — never agent prose.
5. **Tick gate** pre-flight checks before waking the LLM.

## Quick Start

### 1. Install via one-liner

```bash
curl -fsSL https://raw.githubusercontent.com/ddawnlll/hermes-pack/main/install.sh | bash
```

Or clone directly:

```bash
git clone https://github.com/ddawnlll/hermes-pack.git ~/.hermes-pack
```

### 2. Bootstrap a project

```bash
# Orchestrator project (AlphaForge):
bash ~/.hermes-pack/bootstrap.sh /path/to/alphaforge-infa --adapter v7-alphaforge

# Custom project (DesignForge):
bash ~/.hermes-pack/bootstrap.sh /path/to/designforge --adapter designforge
```

### 3. Dry-run first (no changes made)

```bash
bash ~/.hermes-pack/bootstrap.sh --dry-run /path/to/repo --adapter v7-alphaforge
```

## Multi-Project Setup (Single Hermes Instance)

All projects share the **same Hermes** with unique naming. Each adapter defines its own:

| Project | Profile Names | Cron Jobs | Kanban Board |
|---------|--------------|-----------|--------------|
| **AlphaForge** | `af-orchestrator`, `af-worker-1..3` | `af-orchestrator-tick` (every 45m) | `alphaforge` |
| **DesignForge** | `designforge-designer`, `designforge-judge` | `designforge-lead-discovery` (daily 09:00) | `designforge` |
| | | `designforge-draft-create` (daily 10:00) | |
| | | `designforge-reply-monitor` (every 2h weekdays) | |

```bash
# Install ALL on one Hermes:
bash ~/.hermes-pack/bootstrap.sh ~/Documents/alphaforge-infa --adapter v7-alphaforge
bash ~/.hermes-pack/bootstrap.sh ~/Documents/designforge --adapter designforge
```

No naming collisions. Each project is independent.

## Adapter System

Each adapter lives in `adapters/<name>/`:

```
adapters/<name>/
  project.yaml          # Project identity, names, providers, paths
  setup.sh              # Custom setup script (for custom mode)
  AGENTS.adapter.md     # Project-specific AGENTS.md (copied to repo)
  SOUL.*.md             # Profile SOUL overrides
  prompts/              # Cron job prompts
  hypotheses.seed.yaml  # Initial hypothesis families (orchestrator mode)
```

### Creating a new adapter

**For orchestrator projects** (hypothesis-driven, with T0/T1/T2/T3 gates):

Create `adapters/<name>/project.yaml`:

```yaml
project:
  name: "MyProject"
  objective: "Improve the project in measurable ways."
  board_name: "myproject-board"
  board_desc: "MyProject orchestration"

hermes:
  setup_mode: "orchestrator"           # default, can omit
  profile_orchestrator: "myproject-orch"
  profile_worker_prefix: "myproject-worker"
  worker_count: 3
  tick_name: "myproject-tick"
  tick_schedule: "every 45m"
  delivery: "local"
  provider:
    orchestrator: "anthropic"
    orchestrator_model: "claude-opus-4"
    worker: "openrouter"
    worker_model: "deepseek/deepseek-v4-flash"

paths:
  ledger: ".orchestrator"

boundaries:
  allowed:
    - "src/"
  forbidden:
    - "vendor/"

merge_policy: "pr_only"
max_parallel_workers: 3
max_llm_spend_per_day_usd: 25
```

**For custom projects** (non-orchestrator, with own setup script):

```yaml
project:
  name: "MyCustomProject"
  board_name: "myproject-board"

hermes:
  setup_mode: "custom"
  provider:
    default: "opencode-go"
    default_model: "deepseek-v4-flash"

paths:
  ledger: ".myproject"
```

Then create `adapters/<name>/setup.sh` with the custom profile/cron/kanban logic (see `adapters/designforge/setup.sh` as reference).

## Environment Overrides

```bash
# Override provider/model at bootstrap time:
HERMES_ORCH_MODEL="claude-sonnet-4" bash bootstrap.sh /repo --adapter v7-alphaforge
```

## Controls (orchestrator mode)

| Control | File | Action |
|---------|------|--------|
| Pause | `$LEDGER/control.yaml` → `mode: paused` | Orchestrator stops, writes one-paragraph report |
| Resume | `$LEDGER/control.yaml` → `mode: running` | Next tick proceeds normally |
| Kill | `$LEDGER/control.yaml` → `mode: killed` | Blocks all tasks, stops |
| Human directive | `human_instruction: "..."` | Treated as top priority next tick |
| Emergency stop | `hermes cron pause <tick-name>` | Master off switch |

## Commands

```bash
# Dry-run (no changes, no API keys needed)
bash bootstrap.sh --dry-run /path/to/repo --adapter v7-alphaforge

# Real bootstrap
bash bootstrap.sh /path/to/repo --adapter v7-alphaforge

# One-liner install + bootstrap
curl -fsSL https://raw.githubusercontent.com/ddawnlll/hermes-pack/main/install.sh | bash -s -- --adapter designforge
```

## Available Adapters

| Adapter | Setup Mode | Repo | Status |
|---------|-----------|------|--------|
| `v7-alphaforge` | orchestrator | `ddawnlll/alphaforge-infa` | Active |
| `designforge` | custom | `ddawnlll/designforge` | Active |
| `money-radar` | custom | (coming soon) | Stub |

## Known limitations

- Provider/model names are configured in the adapter but not validated at bootstrap time.
- The tick gate (`templates/scripts/tick-gate.sh`) is a shell script — Hermes cron requires `.sh` for the `--script` flag.
- Hermes CLI flags (`--script`, `--deliver`, `--workdir`) confirmed working with Hermes v0.18.0+.
