# Hephaestus

> **Explore freely. Prove ruthlessly.**

A generic, reusable bootstrap and orchestration package for [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Turns any codebase into a hypothesis-driven, evidence-gated, autonomous improvement loop.
All projects share the **same Hermes instance** with unique namespacing.

> Formerly `hermes-pack`. Renamed to Hephaestus — the forge/automaton god — to give this
> orchestration+verification layer its own identity, separate from the Hermes Agent runtime
> it bootstraps. See [milestone v0.4](https://github.com/ddawnlll/hephaestus/milestone/5).

## Architecture

```
hephaestus/
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

---

## Praxis Truth Kernel Integration

Hermes Pack integrates with the **[Praxis Truth Kernel](https://github.com/ddawnlll/praxis)** (`ddawnlll/praxis`) — an independent, deterministic verification layer for agent outputs. Praxis is **not** reimplemented here; it lives in its own repo and is called as a CLI tool via `tools/praxis-bridge.sh`.

### Architecture

```
Worker produces evidence bundle
        │
        ▼
┌──────────────────────────────────┐
│  praxis verify --plan planspec   │  ◄── 6 deterministic gates
│  • SchemaGate  — evidence format │       (NO LLM involved)
│  • LockGate    — plan integrity  │
│  • EvidenceGate — claims backed? │
│  • WiringGate  — contracts kept? │
│  • ExecGate    — tests actually  │
│                  ran?            │
│  • FinalGate   — criteria met?   │
└───────┬──────────────────────────┘
        │
    PASS/HOLD/FAIL
        │
    ┌───┴───┐
  FAIL     PASS/HOLD
    │        │
    ▼        ▼
Reject   Proceed to T1/T2/T3/T4
(no LLM)  (evidence-informed LLM gates)
```

### Integration Points

| Hermes Pack | Praxis Repo | Purpose |
|-------------|-------------|---------|
| `tools/praxis/` (submodule) | `ddawnlll/praxis` | Full Truth Kernel, CLI, plugin |
| `tools/praxis-bridge.sh` | — | Thin wrapper calling `praxis verify` |
| `adapters/*/project.yaml → praxis:` block | — | Adapter-level Praxis configuration |

### Key Rules

- **Praxis before T1.** No LLM gate runs before deterministic verification.
- **No evidence = no claim.** Worker output without evidence is invalid.
- **Workers don't write memory.** Only orchestrator after Praxis PASS + gate verdict.
- **Merge policy:** PR-only, never direct.

### Flow

```
cron tick → pre_tick_gate.sh → orchestrator wakes
  → dispatch worker (context capsule)
  → worker produces evidence
  → praxis verify (6 gates, deterministic)
  → T1 Proposer → T2 Challenger → T3 Arbiter → T4 Human
  → PR / reject / memory retain
```

See [`ddawnlll/praxis`](https://github.com/ddawnlll/praxis) for full Truth Kernel documentation.

## How it works (orchestrator mode)

1. **Bootstrap** creates Hermes profiles, a project ledger, and a cron tick.
2. **Orchestrator** runs on a cron schedule, reads hypotheses, dispatches work via Kanban, judges results.
3. **Workers** execute bounded hypothesis-testing tasks on isolated branches.
4. **Evidence** must come from deterministic runner JSON — never agent prose.
5. **Tick gate** pre-flight checks before waking the LLM.

## Quick Start

### 1. Install via one-liner

```bash
curl -fsSL https://raw.githubusercontent.com/ddawnlll/hephaestus/main/install.sh | bash
```

Or clone directly:

```bash
git clone https://github.com/ddawnlll/hephaestus.git ~/.hephaestus
```

### 2. Bootstrap a project

```bash
# Orchestrator project (AlphaForge):
bash ~/.hephaestus/bootstrap.sh /path/to/alphaforge-infa --adapter v7-alphaforge

# Custom project (DesignForge):
bash ~/.hephaestus/bootstrap.sh /path/to/designforge --adapter designforge
```

### 3. Dry-run first (no changes made)

```bash
bash ~/.hephaestus/bootstrap.sh --dry-run /path/to/repo --adapter v7-alphaforge
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
bash ~/.hephaestus/bootstrap.sh ~/Documents/alphaforge-infa --adapter v7-alphaforge
bash ~/.hephaestus/bootstrap.sh ~/Documents/designforge --adapter designforge
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
curl -fsSL https://raw.githubusercontent.com/ddawnlll/hephaestus/main/install.sh | bash -s -- --adapter designforge
```

## Available Adapters

| Adapter | Setup Mode | Target Repo | Status |
|---------|-----------|-------------|--------|
| `v7-alphaforge` | orchestrator | `ddawnlll/alphaforge-infa` | Active |
| `designforge` | custom | `ddawnlll/designforge` | Active |
| `money-radar` | custom | (coming soon) | Stub |

## Versioned Schema Contract

All stateful data in Hermes Pack follows a versioned JSON Schema contract. Five schema files live in `schema/`:

| Schema | File | Purpose |
|--------|------|---------|
| State | `schema/state.schema.json` | Orchestrator state.json — tick counters, worker status, budget, gate counters |
| Control | `schema/control.schema.json` | Control plane configuration — mode, paths, budget, risk gating |
| Goal | `schema/goal.schema.json` | Eternal/metric/gate_target goal definition with success criteria |
| Ideas | `schema/ideas.schema.json` | Idea lifecycle — spark, triage, hypothesis, verdict |
| Events | `schema/events.schema.json` | Append-only event log — tick/worker/gate/budget events |

### Schema Version Bump Procedure

When making backward-incompatible changes to any schema:

1. **Increment `schema_version`** in the affected schema file(s) — e.g., `1 → 2`.
2. **Create a migration script** `migrate-ledger-<from>to<to>.sh` or update `migrate-ledger.sh` with a version router.
3. **Update templates** — `templates/state.json`, `templates/control.yaml`, `goal.yaml`, `ideas/*.yaml`, `events.jsonl` to match the new schema.
4. **Update `tick-gate.sh`** if the validation logic needs updating for the new fields.
5. **Update the tick prompt** at `templates/prompts/tick.md` if schema changes affect orchestrator behavior.
6. **Run the test suite:** `python schema/tests/test_schema_validation.py`.
7. **Document the change** in the schema file's `description` field and in commit message.

> Backward-compatible additions (new optional fields, wider enums) do not require a schema bump or migration — but do update templates and tests.

### Validation Gate

The pre-tick gate (`templates/scripts/tick-gate.sh`) validates `state.json` against `state.schema.json` before waking the orchestrator. If validation fails, the gate emits `{"wakeAgent": false}` with an error context, preventing the LLM from reading or writing garbage state.

### Migration

Use `migrate-ledger.sh` to convert v1 ledger state (from the Lightning.ai era) to the v2 unified format:

```bash
bash migrate-ledger.sh .alphaforge/orchestrator/state.json --backup
```

## Provider Fallback Router (LiteLLM Proxy)

Hermes Pack includes a **LiteLLM proxy configuration** that provides the "never-dies" guarantee for all profiles.

### Architecture

```
Orchestrator → proxy → [claude-opus → deepseek-v3 → local-qwen]   ← never dies
Worker       → proxy → [deepseek-flash → openrouter-free → local-llama]
Challenger   → proxy → [mid → cheap → local]                       ← different model from orchestrator
Arbiter      → proxy → [premium → mid → local]                     ← different model from challenger
```

Every profile chain ends with a **local model** (Ollama/LM Studio). If all cloud providers are down, the system continues running locally.

### Configuration

Provider chains are defined in the adapter's `project.yaml`:

```yaml
hermes:
  provider:
    orchestrator_chain:
      - "claude-sonnet-4-20250514"
      - "deepseek/deepseek-chat"
      - "ollama/llama3"            # local fallback — never dies
    worker_chain:
      - "deepseek/deepseek-chat"
      - "ollama/llama3"
    challenger_chain:
      - "deepseek/deepseek-chat"
      - "ollama/llama3"
    arbiter_chain:
      - "claude-sonnet-4-20250514"
      - "deepseek/deepseek-chat"
      - "ollama/llama3"
```

### Bootstrap

During bootstrap, the LiteLLM config is generated at `~/.hermes/scripts/litellm-config.yaml`. Start the proxy:

```bash
litellm --config ~/.hermes/scripts/litellm-config.yaml
```

Then configure Hermes profiles to point to `http://localhost:4000` (the default LiteLLM proxy endpoint).

### Key Properties

- **No fork required.** LiteLLM is a standalone proxy; Hermes sees a single OpenAI-compatible endpoint.
- **Per-profile chains.** Orchestrator, worker, challenger, and arbiter each have their own fallback chain.
- **Challenger/arbiter diversity.** Different models are guaranteed for challenger (read-only, blind evaluation) and arbiter (binding decision).
- **Sequential fallback.** On primary provider failure, the chain drops to the next model automatically.
- **Local last resort.** Every chain ends with a local Ollama/LM Studio model.

## v0.4 — Adversarial Council (Hephaestus)

> **Status: design/roadmap.** Everything in this section is specified but **not yet implemented** —
> tracked in [milestone v0.4](https://github.com/ddawnlll/hephaestus/milestone/5), issues
> [#21–#32](https://github.com/ddawnlll/hephaestus/issues?q=milestone%3A%22v0.4%20%E2%80%94%20Adversarial%20Council%20(Hephaestus)%22).
> Do not assume any of this runs today — the existing Praxis + T1/T2/T3 flow described above is
> the only part that's real.

The core problem this milestone addresses: the existing verification stack judges *one worker's
evidence bundle at a time*, and the orchestrator both proposes (T1) and merges — a conflict of
interest. Nothing red-teams the strategy, the goal, or the spend; nothing distinguishes "explore
freely" from "prove ruthlessly."

**Janus** — the two-faced role that fixes this, sitting outside the per-evidence tier system.
Full request/response flow, end to end:

```
                        ┌───────────────────────────┐
                        │   HUMAN  (T4)             │  ← only disputes +
                        │   final arbiter / veto    │    Red Team blocking escalation
                        └─────────────┬─────────────┘
                                      │ (disputes only)
        control.yaml ┌────────────────┴────────────────┐ goal.yaml
        (mode/priority)│                                 │(target + ratchet)
                       ▼                                 ▲
   ╔═══════════╗   ┌───────────────────────────────┐    │
   ║ EXPLORER  ║──►│                               │    │
   ║ divergence║   │        ORCHESTRATOR           │    │
   ║           ║   │     (commander / hub)         │    │
   ║ "what if?"║   │  dispatch • decide • merge    │    │
   ║ no veto   ║   └───┬───────────────────────▲───┘    │
   ╚═════▲═════╝       │ dispatch               │ verdict│
         │             ▼                        │        │
         │        ┌─────────┐  evidence   ┌─────┴──────┐ │
         │        │ WORKERS │────────────►│  PRAXIS    │ │
         │        │ (N)     │  bundle     │ 6 gates    │ │
         │        │ execute │             │ determ.    │ │
         │        └─────────┘             │ FAIL=hard  │ │
         │                                └─────┬──────┘ │
         │                                 PASS │        │
         │                                      ▼        │
         │                            ┌──────────────┐   │
         │                            │ T1→T2→T3     │   │  per-evidence
         │                            │ LLM gates    │   │  judgment (existing)
         │                            │ (blind/diff) │   │
         │                            └──────┬───────┘   │
         │                            tier verdict │     │
         │                                   ▼           │
         │                        ╔══════════════════╗   │
         │   objections.jsonl     ║   RED TEAM       ║───┘ ratchet.json
         └────────────────────────║   convergence    ║   (raises the bar)
            "don't re-propose      ║ strategy-adversary║
             this dead hypothesis" ║ VETO + ratchet   ║
                                   ║ no merge          ║
                                   ╚════════╤═════════╝
                                            │
                                 BLOCK ◄────┼────► CONCEDE
                                    │              │
                          escalate to      Orchestrator MERGEs
                          T4 Human         → writes to Hindsight memory (PASS)
```

- **Explorer** ([#25](https://github.com/ddawnlll/hephaestus/issues/25)) — upstream feeder, zero veto/merge authority, triggered on idle capacity, not every tick. Complements the existing Ideas Engine anti-collapse work (#11).
- **Red Team** ([#24](https://github.com/ddawnlll/hephaestus/issues/24), persona already drafted in `templates/SOUL.redteam.md`) — a conditional meta-gate *above* T1/T2/T3, not a 4th permanent judge. Every objection must carry a `retraction_criterion` (falsifiability contract) — an objection with no stated way to be satisfied is invalid. Persistent scar-tissue memory (`objections.jsonl`, [#23](https://github.com/ddawnlll/hephaestus/issues/23)) blocks re-litigating refuted hypotheses.
- **Decorrelation is load-bearing** ([#22](https://github.com/ddawnlll/hephaestus/issues/22)): the current fallback chains let challenger and worker collapse to the same base model, making "independent verification" theater. Every judge role must come from a distinct model family.
- **Merge authority moves to Arbiter (T3)** ([#21](https://github.com/ddawnlll/hephaestus/issues/21)) — the orchestrator no longer grades its own homework.

**Three \$0 deterministic gates** (no LLM — the same philosophy as Praxis, applied to strategy-layer rigor instead of per-bundle evidence):

| Gate | Blocks | Issue |
|------|--------|-------|
| Pre-registration lock | metric/threshold changed after seeing results (p-hacking) | [#27](https://github.com/ddawnlll/hephaestus/issues/27) |
| Self-grade diff | orchestrator verdict more optimistic than raw evidence allows | [#28](https://github.com/ddawnlll/hephaestus/issues/28) |
| ROI / exploitation-throttle | re-mining a refuted hypothesis family — **never** throttles novel exploration | [#29](https://github.com/ddawnlll/hephaestus/issues/29) |

**Curiosity budget** ([#30](https://github.com/ddawnlll/hephaestus/issues/30)) — a protected slice of daily spend (floor 20%) that no gate above may throttle. The guiding principle: gates constrain *claims*, never *curiosity*.

**Escalation policy + AFK mode** ([#31](https://github.com/ddawnlll/hephaestus/issues/31)) — T4 (human) is the rarest, most expensive path; disputes should die at Arbiter/Red Team almost always. Critically: **when no human is available, the system never waits on T4.** Human-required work is parked with a safe default of HOLD (never auto-merge something critical), and the loop keeps working on other hypotheses. The existing `human_gate_pending>72h` hard-stop in `goal.yaml` is being removed for exactly this reason — a global stall is worse than a parked decision.

## Known limitations

- Provider/model names are configured in the adapter but not validated at bootstrap time.
- The tick gate (`templates/scripts/tick-gate.sh`) is a shell script — Hermes cron requires `.sh` for the `--script` flag.
- Hermes CLI flags (`--script`, `--deliver`, `--workdir`) confirmed working with Hermes v0.18.0+.
- **v0.4 (Hephaestus adversarial council) is design-only as of this writing** — see the section above. Nothing under "Janus", "Red Team", "Explorer", or the three $0 gates is wired into `bootstrap.sh`/`bootstrap.ts` yet.
