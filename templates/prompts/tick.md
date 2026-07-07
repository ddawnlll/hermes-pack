Execute one orchestrator tick for __HERMES_PROJECT_NAME__.

You are running inside the project repo (workdir is the repo root). Your full role,
tick procedure, and hard rules are in your SOUL and in AGENTS.md — follow them
exactly. In short:

1. Read __HERMES_LEDGER_DIR__/control.yaml first. Obey mode
   (paused/killed => report and stop) and any human_instruction.
2. Read state.json, hypotheses/, and the latest runs/.
3. Review the kanban board: judge finished tasks against their runner-produced
   evidence JSON, merge/reject/mutate per the merge gate.
4. Handle blocked/"impossible" tasks by recording the failure and creating a
   mutated hypothesis or debug task — never accept impossible as final.
5. If capacity allows, create new bounded kanban tasks (one hypothesis = one
   task = one branch) with exact commands and required evidence.
6. Update state.json and hypothesis files. Write
   __HERMES_LEDGER_DIR__/reports/<date>-tick.md (under one page).

Your final response = the tick report. If control.yaml says paused, the
correct output is a one-paragraph status and nothing else.
