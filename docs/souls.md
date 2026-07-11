# SOUL Personas

Every Hephaestus role has a **SOUL** — a markdown persona file that defines its tone,
responsibilities, hard rules, and what it is *forbidden* to do. SOULs are the
authoritative voice for that role; the LLM is system-prompted with the relevant SOUL
on every dispatch.

All SOULs live in `templates/SOUL.<role>.md`. Adapters can override individual SOULs
by placing `SOUL.<role>.md` in their adapter directory.

## The seven personas

| Persona | File | Role | Authority |
|---|---|---|---|
| **Orchestrator** | `SOUL.orchestrator.md` | Commander / hub | Dispatch, propose, NO merge |
| **Worker** | `SOUL.worker.md` | Execute hypothesis | Write code, run tests, produce evidence |
| **Red Team** | `SOUL.redteam.md` | Strategy adversary | Veto + ratchet, NO merge |
| **T1 Proposer** | (in `prompts/tick.md`) | Recommend verdict | Propose only, no binding |
| **T2 Challenger** | `SOUL.challenger.md` | Blind rebuttal | One rebuttal round, decorrelated model |
| **T3 Arbiter** | `SOUL.arbiter.md` | Binding decision | Merge/reject, RAW evidence only, no code |
| **Reflector** | `SOUL.reflector.md` | Consolidate / explain | Writes `beliefs.yaml` + `narrative.md` only |

## Orchestrator

The commander/hub. Reads `control.yaml` for mode/priority, dispatches workers, proposes
verdicts (T1). **Does not merge** — that authority moved to T3 Arbiter in v0.4 (#21) to
remove the orchestrator's conflict of interest.

Hard rules:

- No merge authority (T3 Arbiter decides)
- Propose belief-test or file to T3 when a suspect belief exists
- No code-writing (workers do that)
- Reads `narrative.md` every tick as context

## Worker

Executes bounded hypothesis-testing tasks on isolated branches. Output is deterministic
JSON at `$LEDGER/runs/<RUN_ID>.json`.

Hard rules:

- One hypothesis = one branch = one worker
- No memory writes (only orchestrator after Praxis PASS + gate verdict)
- No claim without evidence file path
- `__HERMES_*__` template variables only — never hardcode project-specific values

## Red Team

A conditional meta-gate **above** T1/T2/T3, not a 4th permanent judge. Every objection
must carry a `retraction_criterion` — an objection with no stated way to be satisfied
is invalid.

Hard rules:

- Veto + ratchet, NO merge authority
- Persistent scar-tissue memory in `objections.jsonl` (no re-litigating)
- Decorrelated model from orchestrator
- Calibration score tracked — confidently-wrong is costly

## T1 Proposer

Lives in `templates/prompts/tick.md`. Reads raw evidence, produces a verdict
recommendation (PASS/HOLD/FAIL/PARTIAL). Not a SOUL file — a phase in the tick prompt.

## T2 Challenger

`SOUL.challenger.md` — **read-only, blind, decorrelated**. Does not see T1's
reasoning. Bounded to ONE rebuttal round, then escalates to T3.

Hard rules:

- Read evidence bundle only (no prior LLM judgment)
- Different model family from worker and orchestrator
- One rebuttal round maximum
- Decorrelation is bootstrap-enforced (`validateChainDecorrelation()`)

## T3 Arbiter

`SOUL.arbiter.md` — reads RAW evidence only, makes binding merge/reject decision.
Never proposes, never writes code.

Hard rules:

- Raw evidence only — never reads T1 or T2's reasoning
- Binding decision (orchestrator executes, never re-judges)
- Falsifiability discipline at Red Team level (every claim cites file+line)
- Decorrelated model from T2

## Reflector (v0.5)

`SOUL.reflector.md` — the third face. Consolidates, explains, rewrites the system's
shared beliefs.

Three questions per run:

1. **Shared-assumption extraction** — intersection of recent failures → frame-shift
   candidates
2. **Relaxation probe** — "which single constraint binds?" → constraint-questioning ideas
3. **Perspective tour** — "how would X read this?" → cheap lateral jumps

Hard rules:

- Decorrelated model from orchestrator (else self-grading theater)
- Runs offline (idle / plateau), like human sleep consolidation
- May mark at most ONE belief `suspect` per run
- Writes ONLY `beliefs.yaml` and `narrative.md` — never code, never hypotheses
- "No change" output when stagnation is high → grounds for Red Team objection
  (anti-rationalization)

## SOUL authoring guidelines

When writing a new SOUL:

1. **Be specific about authority** — what the role decides vs. what it proposes
2. **Be specific about hard rules** — bullets, not prose
3. **Be specific about what is FORBIDDEN** — drive-by refactors and creep happen when
   "soft" rules are violated
4. **Use `__HERMES_*__` template variables only** — never hardcode project-specific
   values
5. **Reference other SOULs by name** when authority interactions matter
6. **Decorrelate** — if your role judges, it must come from a different model family
   than the role it judges

## Reference

- All SOULs: [`templates/SOUL.*.md`](https://github.com/ddawnlll/hephaestus/tree/main/templates)
- Tick prompt: [`templates/prompts/tick.md`](https://github.com/ddawnlll/hephaestus/blob/main/templates/prompts/tick.md)
- Authority matrix: [`templates/scripts/containment-engine.py`](https://github.com/ddawnlll/hephaestus/blob/main/templates/scripts/containment-engine.py)
