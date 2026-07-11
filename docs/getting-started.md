# Getting Started

Get Hephaestus running on any project in under five minutes.

## 1. Install

### One-liner (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/ddawnlll/hephaestus/main/install.sh | bash
```

This clones Hephaestus to `~/.hephaestus` and adds it to your PATH.

### Manual

```bash
git clone https://github.com/ddawnlll/hephaestus.git ~/.hephaestus
```

## 2. Bootstrap a project

Hephaestus ships with three adapters:

| Adapter | Mode | Target | Use case |
|---|---|---|---|
| [`v7-alphaforge`](https://github.com/ddawnlll/hephaestus/tree/main/adapters/v7-alphaforge) | orchestrator | `ddawnlll/alphaforge-infa` | Hypothesis-driven alpha research |
| [`designforge`](https://github.com/ddawnlll/hephaestus/tree/main/adapters/designforge) | custom | `ddawnlll/designforge` | Design pipeline |
| `money-radar` | custom | (stub) | Coming soon |

### Orchestrator project (AlphaForge)

```bash
bash ~/.hephaestus/bootstrap.sh ~/path/to/alphaforge-infa --adapter v7-alphaforge
```

This creates:

- 1 orchestrator profile + N worker profiles
- 1 cron tick (`af-orchestrator-tick` every 45 min)
- Gate script + Praxis bridge
- `beliefs.yaml`, `narrative.md` (Reflector artifacts)
- Extra ledger dirs: `beliefs/`, `provenance/`, `reflector/`, `whispers/`, `analogies/`, `dreams/`
- v0.5 channel scripts installed to `~/.hermes/scripts/`

### Custom project (DesignForge)

```bash
bash ~/.hephaestus/bootstrap.sh ~/path/to/designforge --adapter designforge
```

## 3. Dry-run first

Always dry-run before the real thing:

```bash
bash ~/.hephaestus/bootstrap.sh --dry-run ~/path/to/repo --adapter v7-alphaforge
```

Dry-run reports what would be created without making any changes.

## 4. Verify

After bootstrap, run the canary suite to confirm v0.5 integration:

```bash
cd ~/path/to/project
python3 .orchestrator/schema/tests/test_correction_pass.py    # 41 tests
python3 .orchestrator/schema/tests/test_canary_suite.py         # 11 scenarios
```

Or run the full test matrix:

```bash
python3 -m pytest .orchestrator/schema/tests/ -v
```

## 5. Watch it run

```bash
hermes cron list
tail -f ~/.hermes/projects/alphaforge/runs/*.jsonl
```

The orchestrator ticks every 45 minutes, dispatches hypotheses, verifies evidence, and
either merges (via T3 Arbiter) or rejects. Results land in the kanban board.

## Next steps

- [Architecture →](architecture.md) — understand the org chart
- [v0.5 Kaizen Engine →](v05-kaizen.md) — Reflector, beliefs, channels
- [Adapters →](adapters.md) — write your own adapter
- [Schemas →](schemas.md) — versioned contract for all state

## Troubleshooting

### "praxis: command not found"

Install the Praxis Truth Kernel CLI:

```bash
cd tools/praxis && bun install
```

Or globally:

```bash
npm install -g @praxis/cli
```

### Bootstrap fails on registry update

Pre-existing bash heredoc issue in `bootstrap.sh` line 627. Workaround: use
`bootstrap.ts` (Bun) or run the Python snippet from the error message manually.

### Reflector not dispatching

Default is shadow mode. To activate, set `features.reflector: active` in your adapter's
`project.yaml` and run `readiness-check.py` first.

### Channels produce no output

All v0.5 channels are **default disabled**. Enable per-channel in your adapter's
`project.yaml`:

```yaml
features:
  reflector: shadow
  channels:
    analogy: enabled
    dream: disabled       # safe-by-default
    whisper: enabled
    calibration: enabled
```

Each enabled channel consumes its own daily budget — see `state.channel_spend_today`.
