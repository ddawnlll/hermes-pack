# Adapters

An **adapter** is a per-project configuration that tells Hephaestus which profiles to
create, which cron jobs to schedule, which kanban boards to set up, and which paths
to treat as the project ledger.

Every project gets unique namespacing. All projects share the **same Hermes instance**
with unique names, cron names, and kanban names — no collisions.

## Layout

```
adapters/<name>/
  project.yaml          # Project identity, names, providers, paths
  setup.sh              # Custom setup script (for custom mode)
  AGENTS.adapter.md     # Project-specific AGENTS.md (copied to repo)
  SOUL.*.md             # Profile SOUL overrides
  prompts/              # Cron job prompts
  hypotheses.seed.yaml  # Initial hypothesis families (orchestrator mode)
```

## Two setup modes

| Mode | Adapter | Creates | Use case |
|---|---|---|---|
| `orchestrator` | `v7-alphaforge` | 1 orchestrator + N worker profiles, 1 cron tick, gate script, hypotheses ledger | Hypothesis-driven alpha research |
| `custom` | `designforge`, `money-radar` | Adapter-defined profiles, multiple cron jobs, kanban | Non-orchestrator pipelines |

## v7-alphaforge (orchestrator mode)

`adapters/v7-alphaforge/project.yaml`:

```yaml
project:
  name: "AlphaForge"
  objective: "Improve the project in measurable ways."
  board_name: "alphaforge-board"
  board_desc: "AlphaForge orchestration"

hermes:
  setup_mode: "orchestrator"
  profile_orchestrator: "af-orchestrator"
  profile_worker_prefix: "af-worker"
  worker_count: 3
  tick_name: "af-orchestrator-tick"
  tick_schedule: "every 45m"
  delivery: "local"
  provider:
    orchestrator: "anthropic"
    orchestrator_model: "claude-opus-4"
    worker: "openrouter"
    worker_model: "deepseek/deepseek-v4-flash"
  reflector_model: "deepseek"           # v0.5: decorrelated from orchestrator
  reflector_chain:
    - "deepseek/deepseek-v4-flash"
    - "openrouter/deepseek-chat"
    - "ollama/llama3"
  features:
    reflector: shadow                   # v0.5: default shadow
    channels:
      analogy: enabled
      dream: disabled
      whisper: enabled
      calibration: enabled

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

## designforge (custom mode)

`adapters/designforge/project.yaml`:

```yaml
project:
  name: "DesignForge"
  board_name: "designforge-board"

hermes:
  setup_mode: "custom"
  provider:
    default: "opencode-go"
    default_model: "deepseek-v4-flash"

paths:
  ledger: ".designforge"
```

Custom mode requires a `setup.sh` script. See `adapters/designforge/setup.sh` for the
full example.

## Creating a new adapter

### 1. Create the directory

```bash
mkdir -p adapters/myproject
```

### 2. Write `project.yaml`

See `adapters/v7-alphaforge/project.yaml` for the full schema. Required keys:

- `project.name`, `project.board_name`
- `hermes.setup_mode` (`orchestrator` or `custom`)
- `hermes.profile_*` or adapter-specific names
- `paths.ledger`

### 3. Add provider config

Every profile chain should end with a local fallback (Ollama/LM Studio) — the
"never-dies" guarantee.

```yaml
hermes:
  provider:
    orchestrator_chain:
      - "claude-sonnet-4-20250514"
      - "deepseek/deepseek-chat"
      - "ollama/llama3"            # local fallback — never dies
```

### 4. Decorrelate judge roles

Critical invariant (from v0.4 #22): every judge role must come from a distinct model
family. Otherwise "independent verification" is theater.

```yaml
# CORRECT — different model families
orchestrator_chain: [claude-sonnet-4, deepseek, ollama]
worker_chain:       [deepseek, ollama]
challenger_chain:   [gpt-4o, ollama]            # ≠ orchestrator
arbiter_chain:      [claude-sonnet-4, gpt-4o, ollama]   # ≠ challenger
reflector_chain:    [deepseek, ollama]          # ≠ orchestrator (v0.5)

# WRONG — all collapse to deepseek
orchestrator_chain: [claude-sonnet-4, deepseek, ollama]
worker_chain:       [deepseek, ollama]
challenger_chain:   [deepseek, ollama]          # ← SAME as worker
arbiter_chain:      [deepseek, ollama]          # ← SAME as worker
```

`bootstrap.ts` has `validateChainDecorrelation()` that fails closed on violation.

### 5. Add the v0.5 features block

```yaml
hermes:
  features:
    reflector: shadow              # or "active" (requires readiness check)
    channels:
      analogy: enabled
      dream: disabled              # safe-by-default
      whisper: enabled
      calibration: enabled
```

Disabled channels = zero spend, zero artifacts.

### 6. Optional: SOUL overrides

Drop a `SOUL.<role>.md` in your adapter directory and it will override the default
template during bootstrap. Useful for project-specific tone or domain knowledge.

### 7. Test

```bash
bash bootstrap.sh --dry-run /path/to/repo --adapter myproject
```

If everything looks right:

```bash
bash bootstrap.sh /path/to/repo --adapter myproject
```

## Authority matrix contribution

The authority matrix in `templates/scripts/containment-engine.py` is the source of
truth for "who decides what" in role-pair conflicts. When you add a new profile, you
**must** add an entry. The matrix bootstrap validator will fail otherwise.

Current 28 role-pair entries cover:

- All LLM judge pairs (Worker/Orchestrator/Challenger/Arbiter/RedTeam/Reflector)
- Cross-channel arbitration
- Resource competition (channel budget vs curiosity budget)
- T4 human escalation paths

## Reference

- [v7-alphaforge on GitHub](https://github.com/ddawnlll/hephaestus/tree/main/adapters/v7-alphaforge)
- [designforge on GitHub](https://github.com/ddawnlll/hephaestus/tree/main/adapters/designforge)
- [Praxis integration →](praxis.md) — for adapter-level Praxis config
